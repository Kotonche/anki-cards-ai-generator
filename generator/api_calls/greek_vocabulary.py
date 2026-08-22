import logging

from generator.config import A1, Config
from generator.entities import WordWithContext

from .openai_response import generate_structured_text


GREEK_VOCABULARY_SCHEMA = {
    "type": "object",
    "properties": {
        "word": {"type": "string"},
        "article": {"type": "string"},
        "transcription": {"type": "string"},
        "translation": {"type": "string"},
        "context_greek": {"type": "string"},
        "context_transcription": {"type": "string"},
        "context_russian": {"type": "string"},
        "context_cloze": {"type": "string"},
        "context_cloze_transcription": {"type": "string"},
        "context_answer": {"type": "string"},
        "image_prompt": {"type": "string"},
    },
    "required": [
        "word",
        "article",
        "transcription",
        "translation",
        "context_greek",
        "context_transcription",
        "context_russian",
        "context_cloze",
        "context_cloze_transcription",
        "context_answer",
        "image_prompt",
    ],
    "additionalProperties": False,
}


def _instructions() -> str:
    level_rule = (
        "Используй только очень простую лексику и грамматику уровня A1."
        if Config.LEVEL == A1
        else "Используй частотную бытовую лексику и грамматику не выше уровня A2."
    )
    return f"""Ты создаёшь структурированную заметку для изучения современного греческого языка русскоязычным начинающим.

Пользователь вводит русское слово или короткое выражение. Переведи его на современный греческий, выбрав одно самое частотное бытовое значение. Дополнительный контекст нужен только для выбора значения. {level_rule}

Правила основных полей:
- word: греческая лемма без артикля.
- article: определённый артикль в именительном падеже для существительного (ο, η или το); для других частей речи пустая строка.
- transcription: русская фонетическая запись произношения article + word. Ударную гласную обозначай ЗАГЛАВНОЙ русской буквой, например «и пОрта». Если article пуст, транскрибируй только word.
- translation: краткий русский перевод в том значении, которое выбрано для word.
- image_prompt: самостоятельное описание на английском для учебной иллюстрации без букв, подписей, логотипов и текста.

Правила контекста:
- Создай одно короткое естественное греческое предложение с word в подходящей форме.
- context_greek: полное предложение.
- context_transcription: полная русская фонетическая запись предложения с ударениями ЗАГЛАВНЫМИ гласными.
- context_russian: полный естественный перевод предложения на русский.
- context_answer: только та форма греческого слова или выражения, которая пропущена в предложении; не включай соседний артикль, если он остаётся виден.
- context_cloze: копия context_greek, где ровно одно вхождение context_answer заменено подчёркиваниями.
- context_cloze_transcription: копия context_transcription с тем же пропуском.
- Если полноценный согласованный контекст создать невозможно, верни пустые строки сразу во всех шести context_* полях. Не возвращай частичный контекст.
"""


def chat_generate_vocabulary(word_with_context: WordWithContext) -> dict:
    logging.info(
        "Greek vocabulary: translating Russian input [%s] with context [%s]",
        word_with_context.word,
        word_with_context.context,
    )
    user_input = (
        f"RUSSIAN WORD: [{word_with_context.word}]; "
        f"MEANING CONTEXT: [{word_with_context.context}]"
    )
    return generate_structured_text(
        instructions=_instructions(),
        user_input=user_input,
        max_output_tokens=1536,
        schema_name="greek_vocabulary",
        schema=GREEK_VOCABULARY_SCHEMA,
    )
