import logging
import time

from generator.api_calls import greek_vocabulary, openai_image, openai_text, openai_audio, openai_image_prompt, replicate_image
from generator.dictionaries import dictionaries
from generator.config import Config, GREEK, OPENAI, REPLICATE
from generator.entities import CardData, WordWithContext, CardRawDataV1, GreekVocabularyDataV1, serialize_to_json
from generator.input.file_operations import (
    download_and_save_image,
    generate_audio_path,
    generate_card_data_path,
    generate_context_audio_path,
    generate_image_path,
    save_text,
)
from generator.input.confirm import confirm_action

def generate_text_and_image(input_words: list[WordWithContext]) -> dict[WordWithContext, CardData]:
    words_total = len(input_words)
    words_remaining = words_total

    logging.info(f"Starting generation of text and images for {words_total} words {list(map(lambda entry: entry.word, input_words))}")
    words_cards: dict[WordWithContext, CardData] = {}

    for word_with_context in input_words:
        try:
            card_raw = create_card_for_word(word_with_context)
            words_cards[word_with_context] = card_raw
            logging.info(f"Word [{word_with_context.word}] processed")
        except Exception as e:
            logging.error(f"Failed to process word [{word_with_context.word}] due to [{e}]")
            abort = confirm_action("Do you want to abort processing? If no, the processing will be resumed and this card will be skipped")
            if abort:
                raise Exception(f"Aborting processing after error: [{e}]")
            else:
                logging.warning(f"Word [{word_with_context.word}] will be skipped")
        words_remaining -= 1
        if words_remaining > 0:
            wait_after_word_processing()
    return words_cards


def create_card_for_word(word_with_context) -> CardData:
    if Config.LANGUAGE == GREEK:
        return create_greek_vocabulary_for_word(word_with_context)

    card_text = openai_text.chat_generate_text(word_with_context)
    logging.info("Card text is created")

    image_prompt = openai_image_prompt.chat_generate_image_prompt(word_with_context, card_text)
    image_source = get_image_url_depending_on_image_generation_mode(image_prompt)

    logging.info("Card Image is created")
    if image_source.startswith("data:image/"):
        logging.info("Image source: inline OpenAI image data")
    else:
        logging.info(f"Image URL: {image_source}")

    image_path = generate_image_path(Config.PROCESSING_DIRECTORY_PATH, word_with_context)
    download_and_save_image(image_source, image_path)
    logging.info(f"Card image is saved as [{image_path}]")

    audio_path = generate_audio_path(Config.PROCESSING_DIRECTORY_PATH, word_with_context)
    openai_audio.chat_generate_and_save_audio(word_with_context.word, audio_path)
    logging.info(f"Card audio is saved as [{audio_path}]")

    dictionary_url = dictionaries.create_dictionary_url_if_website_exists(word_with_context.word)
    if dictionary_url:
        logging.info(f"Dictionary url is created")
    else:
        logging.warning(f"Dictionary url is not created")

    image_reference = (
        f"openai:{Config.OPENAI_IMAGE_MODEL}"
        if image_source.startswith("data:image/")
        else image_source
    )
    card_raw: CardRawDataV1 = CardRawDataV1(word=word_with_context.word, card_text=card_text,
                                            image_prompt=image_prompt, image_url=image_reference, image_path=image_path,
                                            audio_path=audio_path,
                                            dictionary_url=dictionary_url)
    card_data_path = generate_card_data_path(Config.PROCESSING_DIRECTORY_PATH, word_with_context)
    save_text(serialize_to_json(card_raw), card_data_path)
    logging.info(f"Card data is saved as [{card_data_path}]")
    return card_raw


def _clean_generated_value(data: dict, name: str) -> str:
    value = data.get(name, "")
    return value.strip() if isinstance(value, str) else ""


def _normalized_greek_context(data: dict) -> dict[str, str]:
    names = [
        "context_greek",
        "context_transcription",
        "context_russian",
        "context_cloze",
        "context_cloze_transcription",
        "context_answer",
    ]
    context = {name: _clean_generated_value(data, name) for name in names}
    if not all(context.values()):
        logging.warning("Greek context is incomplete; only Production and Recognition cards will be created")
        return {name: "" for name in names}
    return context


def create_greek_vocabulary_for_word(word_with_context: WordWithContext) -> GreekVocabularyDataV1:
    generated = greek_vocabulary.chat_generate_vocabulary(word_with_context)
    context = _normalized_greek_context(generated)

    image_prompt = _clean_generated_value(generated, "image_prompt")
    image_source = get_image_url_depending_on_image_generation_mode(image_prompt)
    image_path = generate_image_path(Config.PROCESSING_DIRECTORY_PATH, word_with_context)
    download_and_save_image(image_source, image_path)

    article = _clean_generated_value(generated, "article")
    word = _clean_generated_value(generated, "word")
    spoken_word = " ".join(part for part in (article, word) if part)
    audio_path = generate_audio_path(Config.PROCESSING_DIRECTORY_PATH, word_with_context)
    openai_audio.chat_generate_and_save_audio(spoken_word, audio_path)

    context_audio_path = ""
    if context["context_greek"]:
        candidate_path = generate_context_audio_path(Config.PROCESSING_DIRECTORY_PATH, word_with_context)
        try:
            openai_audio.chat_generate_and_save_audio(context["context_greek"], candidate_path)
            context_audio_path = candidate_path
        except Exception:
            logging.exception("Failed to generate Greek context audio; continuing without it")

    image_reference = (
        f"openai:{Config.OPENAI_IMAGE_MODEL}"
        if image_source.startswith("data:image/")
        else image_source
    )
    card_raw = GreekVocabularyDataV1(
        source_word=word_with_context.word,
        word=word,
        article=article,
        transcription=_clean_generated_value(generated, "transcription"),
        translation=_clean_generated_value(generated, "translation"),
        image_prompt=image_prompt,
        image_url=image_reference,
        image_path=image_path,
        audio_path=audio_path,
        context_audio_path=context_audio_path,
        **context,
    )
    card_data_path = generate_card_data_path(Config.PROCESSING_DIRECTORY_PATH, word_with_context)
    save_text(serialize_to_json(card_raw), card_data_path)
    logging.info("Greek vocabulary data is saved as [%s]", card_data_path)
    return card_raw


def get_image_url_depending_on_image_generation_mode(image_prompt):
    if Config.IMAGE_GENERATION_MODE == OPENAI:
        return openai_image.chat_generate_image(image_prompt)
    elif Config.IMAGE_GENERATION_MODE == REPLICATE:
        return replicate_image.replicate_generate_image(image_prompt)
    else:
        raise Exception(f"Unsupported image generation mode: [{Config.IMAGE_GENERATION_MODE}]")


def wait_after_word_processing():
    sleep_seconds = Config.SECONDS_WAIT_BETWEEN_IMAGE_CALLS
    logging.info(f"Waiting [{sleep_seconds}] seconds after word processing (API RPM)")
    time.sleep(sleep_seconds)
