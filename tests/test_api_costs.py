import base64
import unittest
from types import SimpleNamespace
from unittest import mock

from generator.api_calls import openai_image, openai_response
from generator.api_costs import (
    ApiCostTracker,
    record_audio_speech,
    record_image_response,
    record_text_response,
    record_unknown_cost,
    tracking_api_costs,
)
from generator.config import Config


class ApiCostTrackerTests(unittest.TestCase):
    def test_aggregates_actual_text_image_and_audio_usage(self):
        tracker = ApiCostTracker()
        text_response = SimpleNamespace(
            usage=SimpleNamespace(
                input_tokens=1000,
                input_tokens_details=SimpleNamespace(cached_tokens=200),
                output_tokens=500,
            ),
            service_tier="default",
        )
        image_response = SimpleNamespace(
            usage=SimpleNamespace(
                input_tokens=100,
                input_tokens_details=SimpleNamespace(text_tokens=100, image_tokens=0),
                output_tokens=200,
            ),
        )

        with tracking_api_costs(tracker):
            record_text_response(text_response, "gpt-5.6-luna")
            record_image_response(
                image_response,
                "gpt-image-2",
                "1024x1024",
                "low",
                "educational image",
            )
            record_audio_speech("x" * 20, "tts-1-hd")

        summary = tracker.summary(generated_items=2, cached_items=3)

        self.assertAlmostEqual(summary["components"]["text"], 0.000764)
        self.assertAlmostEqual(summary["components"]["image"], 0.0065)
        self.assertAlmostEqual(summary["components"]["audio"], 0.0006)
        self.assertAlmostEqual(summary["total_usd"], 0.007864)
        self.assertAlmostEqual(summary["average_usd"], 0.003932)
        self.assertEqual(summary["generated_items"], 2)
        self.assertEqual(summary["cached_items"], 3)
        self.assertTrue(summary["complete"])

    def test_estimates_image_cost_when_response_has_no_usage(self):
        tracker = ApiCostTracker()

        with tracking_api_costs(tracker):
            record_image_response(
                SimpleNamespace(usage=None),
                "gpt-image-2",
                "1024x1024",
                "low",
                "x" * 400,
            )

        summary = tracker.summary(generated_items=1)

        self.assertAlmostEqual(summary["total_usd"], 0.0065)
        self.assertTrue(summary["estimated"])
        self.assertTrue(summary["complete"])

    def test_marks_unpriced_provider_as_incomplete(self):
        tracker = ApiCostTracker()

        with tracking_api_costs(tracker):
            record_unknown_cost("image", "Replicate · owner/model")

        summary = tracker.summary(generated_items=1)

        self.assertFalse(summary["complete"])
        self.assertEqual(summary["total_usd"], 0)
        self.assertEqual(summary["unknown_components"], ["Replicate · owner/model"])

    def test_calls_outside_active_job_are_ignored(self):
        tracker = ApiCostTracker()

        record_audio_speech("not part of a web job", "tts-1-hd")

        self.assertEqual(tracker.summary()["request_count"], 0)

    def test_openai_response_hook_records_text_usage(self):
        tracker = ApiCostTracker()
        response = SimpleNamespace(
            output_text="generated",
            usage=SimpleNamespace(
                input_tokens=100,
                input_tokens_details=SimpleNamespace(cached_tokens=0),
                output_tokens=50,
            ),
            service_tier="default",
        )
        previous_model = Config.TEXT_MODEL
        Config.TEXT_MODEL = "gpt-5.6-luna"
        try:
            with (
                tracking_api_costs(tracker),
                mock.patch.object(openai_response, "OpenAI") as client_class,
            ):
                client_class.return_value.responses.create.return_value = response
                openai_response.generate_text("instructions", "input", 100)
        finally:
            Config.TEXT_MODEL = previous_model

        self.assertEqual(tracker.summary()["request_count"], 1)
        self.assertGreater(tracker.summary()["components"]["text"], 0)

    def test_openai_image_hook_records_image_usage(self):
        tracker = ApiCostTracker()
        encoded_image = base64.b64encode(b"png").decode()
        response = SimpleNamespace(
            data=[SimpleNamespace(b64_json=encoded_image, url=None)],
            usage=SimpleNamespace(
                input_tokens=100,
                input_tokens_details=SimpleNamespace(text_tokens=100, image_tokens=0),
                output_tokens=200,
            ),
        )

        with (
            tracking_api_costs(tracker),
            mock.patch.object(openai_image, "OpenAI") as client_class,
        ):
            client_class.return_value.images.generate.return_value = response
            openai_image.chat_generate_image("educational image")

        self.assertEqual(tracker.summary()["request_count"], 1)
        self.assertAlmostEqual(tracker.summary()["components"]["image"], 0.0065)


if __name__ == "__main__":
    unittest.main()
