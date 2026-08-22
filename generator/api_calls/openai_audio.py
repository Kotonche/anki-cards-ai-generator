import logging

from openai import OpenAI

from generator.api_costs import record_audio_speech
from generator.config import Config


def chat_generate_and_save_audio(word: str, target_file_path: str):
    client = OpenAI(
        api_key=Config.OPENAI_API_KEY
    )

    # use period for pause
    speech_input = ". " + word + ". "
    with client.audio.speech.with_streaming_response.create(
            model=Config.OPENAI_AUDIO_MODEL,
            voice="nova",
            input=speech_input,

    ) as response:
        response.stream_to_file(target_file_path)
    record_audio_speech(speech_input, Config.OPENAI_AUDIO_MODEL)
