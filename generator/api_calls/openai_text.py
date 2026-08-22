import logging

from ..config import Config
from ..entities import WordWithContext
from .openai_response import generate_text
from .text_prompt_by_language import prompt_by_language



def chat_generate_text(word_with_context: WordWithContext) -> str:
    logging.info(f"ChatGPT card text: processing word [{word_with_context.word}] with context [{word_with_context.context}] in language [{Config.LANGUAGE}]")

    system_prompt = prompt_by_language.get_system_prompt_by_language()

    user_input = f"WORD: [{word_with_context.word}]; CONTEXT: [{word_with_context.context}]"
    logging.debug(f"ChatGPT card generation input {user_input}")

    generated_text = generate_text(
        instructions=system_prompt,
        user_input=user_input,
        max_output_tokens=1024,
    )
    logging.debug(f"ChatGPT generated card text for word {word_with_context.word}")
    logging.debug(f"ChatGPT card text: {generated_text}")
    return generated_text
