from openai import OpenAI

from ..config import Config


def generate_text(instructions: str, user_input: str, max_output_tokens: int) -> str:
    client = OpenAI(api_key=Config.OPENAI_API_KEY)
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

    response = client.responses.create(**request)
    generated_text = response.output_text
    if not generated_text:
        raise RuntimeError("OpenAI returned an empty text response")
    return generated_text
