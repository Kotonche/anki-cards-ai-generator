import json
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock

from generator.anki import anki_operations, card_formatter, greek_vocabulary_model
from generator.api_calls import greek_vocabulary, openai_response
from generator.config import A1, Config, GREEK
from generator.entities import GreekVocabularyDataV1, WordWithContext
from generator import generate_cards
from generator.generate_cards import _normalized_greek_context


def greek_card(**overrides):
    values = {
        "source_word": "дверь",
        "word": "πόρτα",
        "article": "η",
        "transcription": "и пОрта",
        "translation": "дверь",
        "image_prompt": "A simple wooden door, no text.",
        "image_url": "openai:gpt-image-2",
        "image_path": "/tmp/door.png",
        "audio_path": "/tmp/door.mp3",
        "context_greek": "Άνοιξε την πόρτα, σε παρακαλώ.",
        "context_transcription": "Аниксе тин пОрта, се паракалО.",
        "context_russian": "Открой дверь, пожалуйста.",
        "context_cloze": "Άνοιξε την _____, σε παρακαλώ.",
        "context_cloze_transcription": "Аниксе тин _____, се паракалО.",
        "context_answer": "πόρτα",
        "context_audio_path": "/tmp/door_context.mp3",
    }
    values.update(overrides)
    return GreekVocabularyDataV1(**values)


class GreekStructuredGenerationTests(unittest.TestCase):
    def setUp(self):
        Config.LANGUAGE = GREEK
        Config.LEVEL = A1
        Config.TEXT_MODEL = "gpt-5.6-luna"

    def tearDown(self):
        Config.LANGUAGE = Config.DEFAULT_LANGUAGE
        Config.LEVEL = Config.DEFAULT_LEVEL
        Config.TEXT_MODEL = Config.DEFAULT_TEXT_MODEL

    def test_russian_input_uses_strict_structured_output(self):
        payload = {
            "word": "πόρτα",
            "article": "η",
            "transcription": "и пОрта",
            "translation": "дверь",
            "context_greek": "Άνοιξε την πόρτα.",
            "context_transcription": "Аниксе тин пОрта.",
            "context_russian": "Открой дверь.",
            "context_cloze": "Άνοιξε την _____.",
            "context_cloze_transcription": "Аниксе тин _____.",
            "context_answer": "πόρτα",
            "image_prompt": "A wooden door, no text.",
        }
        response = SimpleNamespace(output_text=json.dumps(payload, ensure_ascii=False))

        with mock.patch.object(openai_response, "OpenAI") as client_class:
            client_class.return_value.responses.create.return_value = response
            result = greek_vocabulary.chat_generate_vocabulary(WordWithContext("дверь", "дом"))

        request = client_class.return_value.responses.create.call_args.kwargs
        self.assertEqual(result["word"], "πόρτα")
        self.assertIn("RUSSIAN WORD: [дверь]", request["input"])
        self.assertEqual(request["text"]["format"]["type"], "json_schema")
        self.assertTrue(request["text"]["format"]["strict"])

    def test_partial_context_is_discarded_as_one_block(self):
        context = _normalized_greek_context({
            "context_greek": "Άνοιξε την πόρτα.",
            "context_transcription": "",
            "context_russian": "Открой дверь.",
            "context_cloze": "Άνοιξε την _____.",
            "context_cloze_transcription": "",
            "context_answer": "πόρτα",
        })

        self.assertTrue(all(value == "" for value in context.values()))

    def test_generation_creates_word_and_context_audio(self):
        generated = {
            "word": "πόρτα",
            "article": "η",
            "transcription": "и пОрта",
            "translation": "дверь",
            "context_greek": "Άνοιξε την πόρτα.",
            "context_transcription": "Аниксе тин пОрта.",
            "context_russian": "Открой дверь.",
            "context_cloze": "Άνοιξε την _____.",
            "context_cloze_transcription": "Аниксе тин _____.",
            "context_answer": "πόρτα",
            "image_prompt": "A wooden door, no text.",
        }
        previous_directory = Config.PROCESSING_DIRECTORY_PATH
        with tempfile.TemporaryDirectory() as directory:
            Config.PROCESSING_DIRECTORY_PATH = directory
            with (
                mock.patch.object(generate_cards.greek_vocabulary, "chat_generate_vocabulary", return_value=generated),
                mock.patch.object(
                    generate_cards,
                    "get_image_url_depending_on_image_generation_mode",
                    return_value="data:image/png;base64,cG5n",
                ),
                mock.patch.object(generate_cards.openai_audio, "chat_generate_and_save_audio") as audio,
            ):
                card = generate_cards.create_greek_vocabulary_for_word(WordWithContext("дверь", "дом"))
        Config.PROCESSING_DIRECTORY_PATH = previous_directory

        self.assertEqual(audio.call_args_list[0].args[0], "η πόρτα")
        self.assertEqual(audio.call_args_list[1].args[0], "Άνοιξε την πόρτα.")
        self.assertTrue(card.context_audio_path.endswith("дверь_context.mp3"))
        self.assertEqual(card.source_word, "дверь")


class GreekAnkiModelTests(unittest.TestCase):
    def test_creates_versioned_model_with_three_named_templates(self):
        responses = [
            {"result": [], "error": None},
            {"result": {"id": 1}, "error": None},
        ]
        with mock.patch.object(greek_vocabulary_model.anki_operations, "invoke", side_effect=responses) as invoke:
            name = greek_vocabulary_model.ensure_model()

        self.assertEqual(name, "Greek Vocabulary v1")
        action, params = invoke.call_args_list[1].args
        self.assertEqual(action, "createModel")
        self.assertEqual(params["inOrderFields"], greek_vocabulary_model.FIELD_NAMES)
        self.assertEqual(
            [template["Name"] for template in params["cardTemplates"]],
            greek_vocabulary_model.TEMPLATE_NAMES,
        )

    def test_incompatible_v1_is_preserved_and_v2_is_created(self):
        def fake_invoke(action, params=None):
            if action == "modelNames":
                return {"result": ["Greek Vocabulary v1"], "error": None}
            if action == "modelFieldNames":
                return {"result": ["UserField"], "error": None}
            if action == "modelTemplates":
                return {"result": {}, "error": None}
            if action == "createModel":
                return {"result": {"id": 2}, "error": None}
            raise AssertionError(action)

        with mock.patch.object(greek_vocabulary_model.anki_operations, "invoke", side_effect=fake_invoke) as invoke:
            name = greek_vocabulary_model.ensure_model()

        self.assertEqual(name, "Greek Vocabulary v2")
        create_params = next(call.args[1] for call in invoke.call_args_list if call.args[0] == "createModel")
        self.assertEqual(create_params["modelName"], "Greek Vocabulary v2")

    def test_formatter_adds_fields_media_and_shared_tags(self):
        previous_model, previous_level = Config.CARD_MODEL, Config.LEVEL
        Config.CARD_MODEL = "Greek Vocabulary v1"
        Config.LEVEL = A1
        try:
            note = card_formatter.format(greek_card(), "Greek A1")
        finally:
            Config.CARD_MODEL, Config.LEVEL = previous_model, previous_level

        self.assertEqual(note["modelName"], "Greek Vocabulary v1")
        self.assertEqual(note["fields"]["Word"], "πόρτα")
        self.assertEqual(note["fields"]["Audio"], "[sound:door.mp3]")
        self.assertEqual(note["fields"]["ContextAudio"], "[sound:door_context.mp3]")
        self.assertIn("source::дверь", note["tags"])
        self.assertIn("level::a1", note["tags"])

    def test_empty_context_does_not_populate_context_card_fields(self):
        empty = {
            "context_greek": "",
            "context_transcription": "",
            "context_russian": "",
            "context_cloze": "",
            "context_cloze_transcription": "",
            "context_answer": "",
            "context_audio_path": "",
        }
        previous_model, previous_level = Config.CARD_MODEL, Config.LEVEL
        Config.CARD_MODEL = "Greek Vocabulary v1"
        Config.LEVEL = A1
        try:
            note = card_formatter.format(greek_card(**empty), "Greek A1")
        finally:
            Config.CARD_MODEL, Config.LEVEL = previous_model, previous_level

        self.assertEqual(note["fields"]["ContextCloze"], "")
        self.assertEqual(note["fields"]["ContextAudio"], "")
        context_template = greek_vocabulary_model.CARD_TEMPLATES[2]["Front"]
        self.assertIn("{{#ContextCloze}}", context_template)

    def test_deleting_sibling_cards_resolves_their_shared_note(self):
        with mock.patch.object(anki_operations, "invoke") as invoke:
            invoke.side_effect = [
                {
                    "result": [
                        {"cardId": 11, "note": 7},
                        {"cardId": 12, "note": 7},
                        {"cardId": 13, "note": 7},
                    ],
                    "error": None,
                },
                {"result": None, "error": None},
            ]
            result = anki_operations.delete_cards_by_id([11, 12, 13])

        self.assertIsNone(result["error"])
        self.assertEqual(invoke.call_args_list[1].args, ("deleteNotes", {"notes": [7]}))


if __name__ == "__main__":
    unittest.main()
