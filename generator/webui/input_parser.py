import base64
import csv
import io
from pathlib import Path


class InputError(ValueError):
    pass


def _clean_rows(rows) -> list[dict[str, str]]:
    cards: list[dict[str, str]] = []
    for row in rows:
        word = str(row.get("word", "")).strip()
        context = str(row.get("context", "")).strip()
        if word:
            cards.append({"word": word, "context": context})

    if not cards:
        raise InputError("Не найдено ни одного непустого слова")
    if len(cards) > 1000:
        raise InputError("За один раз можно загрузить не более 1000 слов")
    return cards


def parse_text(content: str) -> list[dict[str, str]]:
    content = content.lstrip("\ufeff").strip()
    if not content:
        raise InputError("Введите слова или выберите файл")

    first_line = content.splitlines()[0].strip().lower()
    if ";" in first_line and "word" in first_line:
        reader = csv.DictReader(io.StringIO(content), delimiter=";")
        if not reader.fieldnames:
            raise InputError("CSV-файл не содержит заголовок")
        normalized = {name.strip().lower(): name for name in reader.fieldnames if name}
        if "word" not in normalized:
            raise InputError("В CSV нужна колонка word")
        rows = (
            {
                "word": row.get(normalized["word"], ""),
                "context": row.get(normalized.get("context", ""), ""),
            }
            for row in reader
        )
        return _clean_rows(rows)

    rows = []
    for line in content.splitlines():
        line = line.strip()
        if not line:
            continue
        word, separator, context = line.partition(";")
        rows.append({"word": word, "context": context if separator else ""})
    return _clean_rows(rows)


def _decode_text_file(raw: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-16", "cp1251"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise InputError("Не удалось определить кодировку текстового файла")


def parse_uploaded_file(filename: str, encoded_content: str) -> list[dict[str, str]]:
    try:
        raw = base64.b64decode(encoded_content, validate=True)
    except (ValueError, TypeError) as error:
        raise InputError("Файл передан в некорректном формате") from error

    if len(raw) > 10 * 1024 * 1024:
        raise InputError("Размер файла не должен превышать 10 МБ")

    extension = Path(filename).suffix.lower()
    if extension in {".csv", ".txt"}:
        return parse_text(_decode_text_file(raw))
    if extension in {".xls", ".xlsx"}:
        try:
            import pandas as pd
        except ImportError as error:
            raise InputError("Для Excel-файлов установите зависимости из requirements.txt") from error

        try:
            dataframe = pd.read_excel(io.BytesIO(raw))
        except Exception as error:
            raise InputError(f"Не удалось прочитать Excel-файл: {error}") from error

        dataframe.columns = [str(column).strip().lower() for column in dataframe.columns]
        if "word" not in dataframe.columns:
            raise InputError("В Excel нужна колонка word")
        if "context" not in dataframe.columns:
            dataframe["context"] = ""
        dataframe = dataframe.fillna("")
        return _clean_rows(dataframe[["word", "context"]].to_dict("records"))

    raise InputError("Поддерживаются CSV, TXT, XLS и XLSX")
