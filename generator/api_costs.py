import math
from contextlib import contextmanager
from contextvars import ContextVar


# Standard API rates in USD as of 2026-08-22. Keep these in sync with the
# pricing table in generator/webui/static/app.js.
TEXT_PRICES_PER_MILLION = {
    "gpt-5.6-luna": {"input": 0.20, "cached": 0.02, "output": 1.20},
    "gpt-5.6-terra": {"input": 2.00, "cached": 0.20, "output": 12.00},
    "gpt-5.6-sol": {"input": 4.00, "cached": 0.40, "output": 20.00},
    "gpt-5.4-nano": {"input": 0.20, "cached": 0.02, "output": 1.25},
    "gpt-5.4-mini": {"input": 0.75, "cached": 0.075, "output": 4.50},
    "gpt-4.1-mini": {"input": 0.40, "cached": 0.10, "output": 1.60},
    "gpt-4.1": {"input": 2.00, "cached": 0.50, "output": 8.00},
    "gpt-4o-mini": {"input": 0.15, "cached": 0.075, "output": 0.60},
    "gpt-4o": {"input": 2.50, "cached": 1.25, "output": 10.00},
}

IMAGE_TOKEN_PRICES_PER_MILLION = {
    "gpt-image-2": {"text_input": 5.00, "image_input": 8.00, "output": 30.00},
}
IMAGE_OUTPUT_FALLBACK_USD = {
    ("gpt-image-2", "1024x1024", "low"): 0.006,
}
AUDIO_PRICES_PER_MILLION_CHARACTERS = {
    "tts-1-hd": 30.00,
    "tts-1": 15.00,
}


def _value(obj, name: str, default=None):
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


class ApiCostTracker:
    def __init__(self):
        self._entries: list[dict] = []

    def record(
            self,
            component: str,
            model: str,
            cost_usd: float | None,
            *,
            estimated: bool = False,
            unknown_label: str | None = None,
    ) -> None:
        self._entries.append({
            "component": component,
            "model": model,
            "cost_usd": cost_usd,
            "estimated": estimated,
            "unknown_label": unknown_label,
        })

    def summary(
            self,
            *,
            generated_items: int = 0,
            cached_items: int = 0,
            skipped_items: int = 0,
    ) -> dict:
        component_totals = {"text": 0.0, "image": 0.0, "audio": 0.0}
        unknown_components = set()
        estimated = False
        for entry in self._entries:
            component = entry["component"]
            cost = entry["cost_usd"]
            if cost is not None:
                component_totals[component] = component_totals.get(component, 0.0) + cost
            if entry["unknown_label"]:
                unknown_components.add(entry["unknown_label"])
            estimated = estimated or entry["estimated"]

        total = sum(component_totals.values())
        average = total / generated_items if generated_items else 0.0
        return {
            "currency": "USD",
            "total_usd": round(total, 10),
            "average_usd": round(average, 10),
            "generated_items": generated_items,
            "cached_items": cached_items,
            "skipped_items": skipped_items,
            "request_count": len(self._entries),
            "components": {
                name: round(value, 10)
                for name, value in component_totals.items()
            },
            "complete": not unknown_components,
            "estimated": estimated or bool(self._entries),
            "unknown_components": sorted(unknown_components),
        }


_ACTIVE_TRACKER: ContextVar[ApiCostTracker | None] = ContextVar(
    "anki_api_cost_tracker",
    default=None,
)


@contextmanager
def tracking_api_costs(tracker: ApiCostTracker):
    token = _ACTIVE_TRACKER.set(tracker)
    try:
        yield tracker
    finally:
        _ACTIVE_TRACKER.reset(token)


def _active_tracker() -> ApiCostTracker | None:
    return _ACTIVE_TRACKER.get()


def record_text_response(response, model: str) -> None:
    tracker = _active_tracker()
    if tracker is None:
        return

    prices = TEXT_PRICES_PER_MILLION.get(model)
    usage = _value(response, "usage")
    if prices is None or usage is None:
        tracker.record(
            "text",
            model,
            None,
            unknown_label=f"текст · {model}",
        )
        return

    input_tokens = int(_value(usage, "input_tokens", 0) or 0)
    output_tokens = int(_value(usage, "output_tokens", 0) or 0)
    details = _value(usage, "input_tokens_details")
    cached_tokens = int(_value(details, "cached_tokens", 0) or 0)
    uncached_tokens = max(0, input_tokens - cached_tokens)
    cost = (
        uncached_tokens * prices["input"]
        + cached_tokens * prices["cached"]
        + output_tokens * prices["output"]
    ) / 1_000_000

    service_tier = _value(response, "service_tier")
    nonstandard_tier = service_tier not in (None, "auto", "default")
    tracker.record(
        "text",
        model,
        cost,
        estimated=nonstandard_tier,
        unknown_label=(
            f"нестандартный service tier · {service_tier}"
            if nonstandard_tier
            else None
        ),
    )


def record_image_response(response, model: str, size: str, quality: str, prompt: str) -> None:
    tracker = _active_tracker()
    if tracker is None:
        return

    prices = IMAGE_TOKEN_PRICES_PER_MILLION.get(model)
    if prices is None:
        tracker.record(
            "image",
            model,
            None,
            unknown_label=f"изображение · {model}",
        )
        return

    usage = _value(response, "usage")
    if usage is not None:
        details = _value(usage, "input_tokens_details")
        total_input = int(_value(usage, "input_tokens", 0) or 0)
        text_input = int(_value(details, "text_tokens", total_input) or 0)
        image_input = int(_value(details, "image_tokens", 0) or 0)
        output = int(_value(usage, "output_tokens", 0) or 0)
        cost = (
            text_input * prices["text_input"]
            + image_input * prices["image_input"]
            + output * prices["output"]
        ) / 1_000_000
        tracker.record("image", model, cost)
        return

    fallback_output = IMAGE_OUTPUT_FALLBACK_USD.get((model, size, quality))
    if fallback_output is None:
        tracker.record(
            "image",
            model,
            None,
            unknown_label=f"изображение · {model} · {size} · {quality}",
        )
        return

    estimated_prompt_tokens = max(1, math.ceil(len(prompt) / 4))
    cost = fallback_output + estimated_prompt_tokens * prices["text_input"] / 1_000_000
    tracker.record("image", model, cost, estimated=True)


def record_audio_speech(text: str, model: str) -> None:
    tracker = _active_tracker()
    if tracker is None:
        return

    price = AUDIO_PRICES_PER_MILLION_CHARACTERS.get(model)
    if price is None:
        tracker.record(
            "audio",
            model,
            None,
            unknown_label=f"аудио · {model}",
        )
        return
    tracker.record("audio", model, len(text) * price / 1_000_000)


def record_unknown_cost(component: str, label: str) -> None:
    tracker = _active_tracker()
    if tracker is not None:
        tracker.record(component, label, None, unknown_label=label)


def empty_cost_summary() -> dict:
    return ApiCostTracker().summary()
