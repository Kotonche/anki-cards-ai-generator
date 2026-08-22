import json
import re
from dataclasses import dataclass, asdict


@dataclass(frozen=True)
class WordWithContext:
    word: str
    context: str

    def __post_init__(self):
        if self.word is None or self.context is None:
            raise ValueError("Attributes cannot be None")
        if self.word == "":
            raise ValueError("Word cannot be empty")


@dataclass(frozen=True)
class CardRawDataV1:
    word: str
    card_text: str
    image_prompt: str
    image_url: str
    image_path: str
    audio_path: str
    dictionary_url: str = None
    version: int = 1

    def __post_init__(self):
        not_nullable = [self.word, self.card_text, self.image_url, self.image_path]
        if None in not_nullable:
            raise ValueError(f"Attributes cannot be None: {serialize_to_json(self)}")
        if self.word == "":
            raise ValueError("Word cannot be empty")
        if self.card_text == "":
            raise ValueError("Card text cannot be empty")
        if self.image_url == "":
            raise ValueError("Image URL cannot be empty")
        if self.audio_path == "" or self.image_path == "":
            raise ValueError("Paths cannot be empty")


@dataclass(frozen=True)
class GreekVocabularyDataV1:
    source_word: str
    word: str
    article: str
    transcription: str
    translation: str
    image_prompt: str
    image_url: str
    image_path: str
    audio_path: str
    context_greek: str
    context_transcription: str
    context_russian: str
    context_cloze: str
    context_cloze_transcription: str
    context_answer: str
    context_audio_path: str = ""
    schema: str = "greek_vocabulary_v1"
    version: int = 1

    def __post_init__(self):
        required = {
            "source_word": self.source_word,
            "word": self.word,
            "transcription": self.transcription,
            "translation": self.translation,
            "image_prompt": self.image_prompt,
            "image_url": self.image_url,
            "image_path": self.image_path,
            "audio_path": self.audio_path,
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise ValueError(f"Greek vocabulary fields cannot be empty: {', '.join(missing)}")

        context_values = [
            self.context_greek,
            self.context_transcription,
            self.context_russian,
            self.context_cloze,
            self.context_cloze_transcription,
            self.context_answer,
        ]
        if any(context_values) and not all(context_values):
            raise ValueError("Greek context fields must either all be filled or all be empty")

    @property
    def has_context(self) -> bool:
        return bool(self.context_greek and self.context_cloze and self.context_answer)

    @property
    def card_text(self) -> str:
        return self.context_cloze or self.translation

    @property
    def dictionary_url(self):
        return None


CardData = CardRawDataV1 | GreekVocabularyDataV1


def serialize_to_json(data):
    # Convert dataclass to dictionary
    data_dict = asdict(data)
    # Serialize dictionary to JSON
    return json.dumps(data_dict, indent=4)


def card_data_from_dict(data: dict) -> CardData:
    if data.get("schema") == "greek_vocabulary_v1":
        return GreekVocabularyDataV1(**data)
    return CardRawDataV1(**data)


def source_word_for_card(data: CardData) -> str:
    if isinstance(data, GreekVocabularyDataV1):
        return data.source_word
    return data.word


def word_to_filename(word: WordWithContext) -> str:
    # convert to lower case
    word_cleaned = str.lower(word.word)
    # Replace all spaces with underscores
    word_cleaned = re.sub(r"\s+", "_", word_cleaned)
    # Remove all non-alphanumeric characters (except underscores)
    word_cleaned = re.sub(r"[^\w\s]", "", word_cleaned)
    return word_cleaned


def cards_to_dict(cards: list[CardData]) -> dict[WordWithContext, CardData]:
    cards_dict: dict[WordWithContext, CardData] = {}
    for card in cards:
        cards_dict[WordWithContext(source_word_for_card(card), "")] = card
    return cards_dict
