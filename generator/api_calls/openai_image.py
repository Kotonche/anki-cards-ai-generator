import logging
from openai import OpenAI

from ..api_costs import record_image_response
from ..config import Config


def chat_generate_image(prompt: str) -> str:
    logging.debug(f"OpenAI image generation prompt [{prompt}]")

    client = OpenAI(api_key=Config.OPENAI_API_KEY)

    response = client.images.generate(
        model=Config.OPENAI_IMAGE_MODEL,
        prompt=prompt,
        size=Config.OPENAI_IMAGE_SIZE,
        quality=Config.OPENAI_IMAGE_QUALITY,
        n=1,
    )
    record_image_response(
        response,
        Config.OPENAI_IMAGE_MODEL,
        Config.OPENAI_IMAGE_SIZE,
        Config.OPENAI_IMAGE_QUALITY,
        prompt,
    )

    generated_image = response.data[0]
    if generated_image.b64_json:
        logging.debug("OpenAI generated image received as base64 data")
        return f"data:image/png;base64,{generated_image.b64_json}"
    if generated_image.url:
        logging.debug("OpenAI generated image received as URL")
        return generated_image.url
    raise RuntimeError("OpenAI image response contains neither base64 data nor a URL")
