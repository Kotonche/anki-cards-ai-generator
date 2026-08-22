import json

from openai import OpenAI

from ..api_costs import record_text_response
from ..config import Config


def _request(instructions: str, user_input: str, max_output_tokens: int) -> dict:
    request = {
        "model": Config.TEXT_MODEL,
        "instructions": instructions,
        "input": user_input,
        "max_output_tokens": max_output_tokens,
        "store": False,
    }

    if Config.TEXT_MODEL.startswith(("gpt-5", "o1", "o3", "o4")):
        request["reasoning"] = {"effort": "low"}
    else:
        request["temperature"] = 0.2

    return request


def generate_text(instructions: str, user_input: str, max_output_tokens: int) -> str:
    client = OpenAI(api_key=Config.OPENAI_API_KEY)
    request = _request(instructions, user_input, max_output_tokens)

    response = client.responses.create(**request)
    record_text_response(response, Config.TEXT_MODEL)
    generated_text = response.output_text
    if not generated_text:
        raise RuntimeError("OpenAI returned an empty text response")
    return generated_text


def generate_structured_text(
        instructions: str,
        user_input: str,
        max_output_tokens: int,
        schema_name: str,
        schema: dict,
) -> dict:
    client = OpenAI(api_key=Config.OPENAI_API_KEY)
    request = _request(instructions, user_input, max_output_tokens)
    request["text"] = {
        "format": {
            "type": "json_schema",
            "name": schema_name,
            "schema": schema,
            "strict": True,
        }
    }

    response = client.responses.create(**request)
    record_text_response(response, Config.TEXT_MODEL)
    if not response.output_text:
        raise RuntimeError("OpenAI returned an empty structured response")
    try:
        return json.loads(response.output_text)
    except json.JSONDecodeError as error:
        raise RuntimeError("OpenAI returned invalid structured JSON") from error
