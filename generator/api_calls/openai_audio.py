import logging

from openai import OpenAI

from generator.api_costs import record_audio_speech
from generator.config import Config, ENGLISH, GERMAN, GREEK


_LANGUAGE_NAMES = {
    ENGLISH: "English",
    GERMAN: "German",
    GREEK: "Modern Greek",
}


def speech_instructions(language: str | None = None) -> str:
    selected_language = language or Config.LANGUAGE or Config.DEFAULT_LANGUAGE
    language_name = _LANGUAGE_NAMES.get(selected_language, "the language in which it is written")
    learner_pace = (
        "at a slightly slower pace suitable for an A1-A2 learner"
        if selected_language == GREEK
        else "at a clear, natural pace suitable for a language learner"
    )
    return (
        f"Speak exactly the provided {language_name} text with a natural native accent, "
        f"{learner_pace}. Do not translate, spell, explain, repeat, or add any words."
    )


def chat_generate_and_save_audio(word: str, target_file_path: str):
    client = OpenAI(
        api_key=Config.OPENAI_API_KEY
    )

    speech_input = word.strip()
    if not speech_input:
        raise ValueError("Speech input must not be empty")
    instructions = speech_instructions()
    with client.audio.speech.with_streaming_response.create(
            model=Config.OPENAI_AUDIO_MODEL,
            voice=Config.OPENAI_AUDIO_VOICE,
            input=speech_input,
            instructions=instructions,
            response_format="mp3",
    ) as response:
        response.stream_to_file(target_file_path)
    record_audio_speech(
        speech_input,
        Config.OPENAI_AUDIO_MODEL,
        instructions=instructions,
    )
