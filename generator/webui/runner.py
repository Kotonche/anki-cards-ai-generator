import json
import logging
import time
from pathlib import Path


def _load_cached_card(processing_directory, word_with_context):
    from generator.entities import CardRawDataV1
    from generator.input.file_operations import (
        all_files_exist_and_are_not_empty,
        generate_card_data_path,
    )

    card_path = Path(generate_card_data_path(processing_directory, word_with_context))
    if not card_path.is_file():
        return None

    try:
        data = json.loads(card_path.read_text(encoding="utf-8"))
        card = CardRawDataV1(**data)
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return None

    if not all_files_exist_and_are_not_empty([card.image_path, card.audio_path]):
        return None
    return card


def _configure(settings: dict, needs_anki: bool) -> None:
    from generator.config import Config
    from generator.webui.defaults import default_anki_media_directory

    Config.setup_logging()
    Config.set_openai_key_or_use_default(settings.get("openai_api_key") or None)
    Config.set_text_model_or_use_default(settings.get("text_model") or None)
    Config.set_image_generation_mode_or_use_default(settings.get("image_generation_mode", "openai"))
    Config.set_replicate_token_and_url_if_replicate_mode_used(
        settings.get("replicate_api_key") or None,
        settings.get("replicate_model_url") or None,
    )
    Config.set_anki_deck_name_or_use_default(settings.get("deck_name") or None)
    Config.set_processing_directory_path(settings["processing_directory"])
    Config.set_language_or_use_default(settings.get("language"))
    Config.set_level_or_use_default(settings.get("level"))
    Config.set_card_model_or_use_default(settings.get("card_model") or None)

    media_directory = settings.get("anki_media_directory") or default_anki_media_directory()
    if needs_anki:
        Config.set_anki_media_directory_or_use_default(media_directory)
    else:
        Config.ANKI_MEDIA_DIRECTORY = media_directory


def _prepare_anki(settings: dict) -> None:
    from generator import validation
    from generator.anki import anki_operations
    from generator.config import Config

    validation.check_anki_connect()
    if anki_operations.check_deck_exists(Config.DECK_NAME):
        return
    if settings.get("create_deck", True):
        anki_operations.create_deck(Config.DECK_NAME)
        return
    raise RuntimeError(f"Колода {Config.DECK_NAME} не существует")


def _handle_duplicate(settings: dict, word: str) -> str | None:
    from generator.anki import anki_operations
    from generator.config import Config

    if not anki_operations.check_card_exists(Config.DECK_NAME, word):
        return None

    policy = settings.get("duplicate_policy", "skip")
    if policy == "skip":
        return "Карточка уже есть в колоде — пропущена"
    if policy == "replace":
        if not anki_operations.delete_card_from_deck(Config.DECK_NAME, word):
            raise RuntimeError("Не удалось удалить существующую карточку")
        return None
    if policy == "allow":
        return None
    raise RuntimeError(f"Неизвестная политика дубликатов: {policy}")


def _import_card(card) -> None:
    from generator.anki import anki_importer

    result = anki_importer.format_and_import_card(card)
    if result.get("error"):
        raise RuntimeError(f"AnkiConnect: {result['error']}")


def _card_changes(card, status: str, message: str) -> dict:
    return {
        "status": status,
        "message": message,
        "card_text": card.card_text,
        "image_prompt": card.image_prompt,
        "dictionary_url": card.dictionary_url,
        "image_path": card.image_path,
        "audio_path": card.audio_path,
        "has_image": bool(card.image_path),
        "has_audio": bool(card.audio_path),
    }


def run_generation_job(manager, job_id: str) -> None:
    settings = manager.private_settings(job_id)
    processing_directory = str(Path(settings["processing_directory"]).expanduser().resolve())
    settings["processing_directory"] = processing_directory
    should_import = bool(settings.get("import_after_generation", True))

    manager.set_job(job_id, message="Проверка настроек")
    _configure(settings, needs_anki=should_import)
    if should_import:
        manager.set_job(job_id, message="Подключение к Anki")
        _prepare_anki(settings)

    from generator import generate_cards
    from generator.config import Config
    from generator.entities import WordWithContext

    cards = manager.cards_for_runner(job_id)
    errors = 0

    for index, card_record in enumerate(cards):
        if manager.is_cancel_requested(job_id):
            manager.set_job(job_id, status="cancelled", message="Задание остановлено")
            return

        card_id = card_record["id"]
        word = card_record["word"]
        word_with_context = WordWithContext(word, card_record["context"])
        manager.update_card(job_id, card_id, status="generating", message="Подготовка карточки")
        manager.set_job(job_id, message=f"Обработка: {word}")
        generated_this_card = False

        try:
            if should_import:
                duplicate_message = _handle_duplicate(settings, word)
                if duplicate_message:
                    manager.update_card(job_id, card_id, status="skipped", message=duplicate_message)
                    continue

            raw_card = _load_cached_card(processing_directory, word_with_context)
            from_cache = raw_card is not None
            if raw_card is None:
                manager.update_card(job_id, card_id, message="Генерация текста, изображения и аудио")
                raw_card = generate_cards.create_card_for_word(word_with_context)
                generated_this_card = True

            if should_import:
                manager.update_card(job_id, card_id, status="importing", message="Импорт в Anki")
                _import_card(raw_card)
                message = "Импортирована из сохранённых файлов" if from_cache else "Создана и импортирована"
                status = "imported"
            else:
                message = "Загружена из сохранённых файлов" if from_cache else "Материалы созданы"
                status = "generated"

            manager.update_card(job_id, card_id, **_card_changes(raw_card, status, message))
        except Exception as error:
            logging.exception("Failed to process card %s", word)
            manager.update_card(job_id, card_id, status="error", message=str(error))
            errors += 1

        has_more_cards = index < len(cards) - 1
        if has_more_cards and generated_this_card and Config.IMAGE_GENERATION_MODE == "openai":
            manager.set_job(job_id, message="Ожидание лимита генерации изображений")
            time.sleep(Config.SECONDS_WAIT_BETWEEN_IMAGE_CALLS)

    status = "completed_with_errors" if errors else "completed"
    message = "Готово, но некоторые карточки завершились ошибкой" if errors else "Все карточки обработаны"
    manager.set_job(job_id, status=status, message=message)
