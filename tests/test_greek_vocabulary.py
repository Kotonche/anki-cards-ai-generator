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
from generator.generate_cards import _normalized_greek_context, _normalized_greek_distractors


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
        "distractor1": "η καρέκλα",
        "distractor1_transcription": "и карЭкла",
        "distractor2": "η κουζίνα",
        "distractor2_transcription": "и кузИна",
        "distractor3": "η τσάντα",
        "distractor3_transcription": "и цАнда",
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
            "distractor1": "η καρέκλα",
            "distractor1_transcription": "и карЭкла",
            "distractor2": "η κουζίνα",
            "distractor2_transcription": "и кузИна",
            "distractor3": "η τσάντα",
            "distractor3_transcription": "и цАнда",
            "image_prompt": "A wooden door, no text.",
        }
        response = SimpleNamespace(output_text=json.dumps(payload, ensure_ascii=False))

        with mock.patch.object(openai_response, "OpenAI") as client_class:
            client_class.return_value.responses.create.return_value = response
            result = greek_vocabulary.chat_generate_vocabulary(
                WordWithContext("дверь", "дом", "Открой дверь, пожалуйста.")
            )

        request = client_class.return_value.responses.create.call_args.kwargs
        self.assertEqual(result["word"], "πόρτα")
        self.assertIn("RUSSIAN WORD: [дверь]", request["input"])
        self.assertIn("RUSSIAN EXAMPLE PHRASE: [Открой дверь, пожалуйста.]", request["input"])
        self.assertIn("переведи именно эту фразу", request["instructions"])
        self.assertEqual(request["text"]["format"]["type"], "json_schema")
        self.assertTrue(request["text"]["format"]["strict"])
        self.assertIn("distractor3_transcription", request["text"]["format"]["schema"]["required"])

    def test_empty_phrase_requests_automatic_example(self):
        response = SimpleNamespace(output_text="{}")
        with mock.patch.object(openai_response, "OpenAI") as client_class:
            client_class.return_value.responses.create.return_value = response
            greek_vocabulary.chat_generate_vocabulary(WordWithContext("дверь", "дом"))

        request = client_class.return_value.responses.create.call_args.kwargs
        self.assertIn("RUSSIAN EXAMPLE PHRASE: []", request["input"])
        self.assertIn("самостоятельно создай", request["instructions"])

    def test_custom_phrase_gets_a_distinct_cache_filename(self):
        automatic = WordWithContext("дверь", "дом")
        custom = WordWithContext("дверь", "дом", "Открой дверь.")

        self.assertEqual(generate_cards.generate_card_data_path("/tmp", automatic), "/tmp/дверь.json")
        self.assertNotEqual(
            generate_cards.generate_card_data_path("/tmp", automatic),
            generate_cards.generate_card_data_path("/tmp", custom),
        )

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

    def test_invalid_distractors_are_discarded_as_one_block(self):
        distractors = _normalized_greek_distractors({
            "distractor1": "η καρέκλα",
            "distractor1_transcription": "и карЭкла",
            "distractor2": "η καρέκλα",
            "distractor2_transcription": "и карЭкла",
            "distractor3": "η τσάντα",
            "distractor3_transcription": "и цАнда",
        }, "η", "πόρτα")

        self.assertTrue(all(value == "" for value in distractors.values()))

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
            "distractor1": "η καρέκλα",
            "distractor1_transcription": "и карЭкла",
            "distractor2": "η κουζίνα",
            "distractor2_transcription": "и кузИна",
            "distractor3": "η τσάντα",
            "distractor3_transcription": "и цАнда",
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
        self.assertTrue(card.has_multiple_choice)
        self.assertEqual(card.distractor2, "η κουζίνα")


class GreekAnkiModelTests(unittest.TestCase):
    def test_creates_versioned_model_with_four_named_templates(self):
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
            [
                "01 · Recognition Boost · Multiple Choice",
                "02 · Recognition · Comprehension",
                "03 · Context Recall · Usage",
                "04 · Active Recall · Production",
            ],
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
        self.assertEqual(note["fields"]["Distractor1"], "η καρέκλα")
        self.assertEqual(note["fields"]["Distractor3Transcription"], "и цАнда")
        self.assertIn("source::дверь", note["tags"])
        self.assertIn("level::a1", note["tags"])

    def test_multiple_choice_template_is_conditional_and_interactive(self):
        template = greek_vocabulary_model.CARD_TEMPLATES[0]

        self.assertEqual(template["Name"], "01 · Recognition Boost · Multiple Choice")
        self.assertIn("RECOGNITION BOOST · MULTIPLE CHOICE", template["Front"])
        self.assertIn("{{#Distractor1}}", template["Front"])
        self.assertIn("{{#Distractor2}}", template["Front"])
        self.assertIn("{{#Distractor3}}", template["Front"])
        self.assertIn("Math.random()", template["Front"])
        self.assertIn('data-correct="true"', template["Front"])
        self.assertIn('classList.add(isCorrect ? "is-correct" : "is-wrong")', template["Front"])
        self.assertNotIn("alert(", template["Front"])
        self.assertIn("{{Audio}}", template["Back"])
        self.assertIn("{{ContextAudio}}", template["Back"])
        self.assertIn(".gv-choice .gv-article { color: inherit; }", greek_vocabulary_model.STYLING)
        self.assertIn("box-sizing: border-box;", greek_vocabulary_model.STYLING)

    def test_model_without_multiple_choice_context_audio_is_versioned(self):
        old_templates = {
            name: {"Front": "front", "Back": "back"}
            for name in greek_vocabulary_model.TEMPLATE_NAMES
        }

        def fake_invoke(action, params=None):
            if action == "modelNames":
                return {"result": ["Greek Vocabulary v1"], "error": None}
            if action == "modelFieldNames":
                return {"result": greek_vocabulary_model.FIELD_NAMES, "error": None}
            if action == "modelTemplates":
                return {"result": old_templates, "error": None}
            if action == "createModel":
                return {"result": {"id": 2}, "error": None}
            raise AssertionError(action)

        with mock.patch.object(greek_vocabulary_model.anki_operations, "invoke", side_effect=fake_invoke) as invoke:
            name = greek_vocabulary_model.ensure_model()

        self.assertEqual(name, "Greek Vocabulary v2")
        create_params = next(call.args[1] for call in invoke.call_args_list if call.args[0] == "createModel")
        self.assertIn(
            "{{ContextAudio}}",
            create_params["cardTemplates"][0]["Back"],
        )

    def test_all_templates_have_unified_skill_badges(self):
        expected_badges = [
            "RECOGNITION BOOST · MULTIPLE CHOICE",
            "RECOGNITION · COMPREHENSION",
            "CONTEXT RECALL · USAGE",
            "ACTIVE RECALL · PRODUCTION",
        ]

        for template, badge in zip(greek_vocabulary_model.CARD_TEMPLATES, expected_badges):
            self.assertIn(badge, template["Front"])

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


class GreekSiblingSpacingTests(unittest.TestCase):
    def test_existing_sibling_spacing_is_left_unchanged(self):
        config = {"id": 1, "name": "Default", "new": {"bury": True}, "newSortOrder": 0}
        with mock.patch.object(anki_operations, "invoke", return_value={"result": config, "error": None}) as invoke:
            changed = anki_operations.ensure_new_sibling_spacing("Greek A1")

        self.assertFalse(changed)
        invoke.assert_called_once_with("getDeckConfig", {"deck": "Greek A1"})

    def test_clones_shared_preset_before_enabling_sibling_spacing(self):
        original = {"id": 1, "name": "Default", "new": {"bury": False}, "newSortOrder": 4}
        cloned = {"id": 77, "name": "Anki Generator · spaced siblings · Greek A1", "new": {"bury": False}, "newSortOrder": 4}
        responses = [
            {"result": original, "error": None},
            {"result": 77, "error": None},
            {"result": True, "error": None},
            {"result": cloned, "error": None},
            {"result": True, "error": None},
        ]
        with mock.patch.object(anki_operations, "invoke", side_effect=responses) as invoke:
            changed = anki_operations.ensure_new_sibling_spacing("Greek A1")

        self.assertTrue(changed)
        self.assertEqual(invoke.call_args_list[1].args[0], "cloneDeckConfigId")
        self.assertEqual(invoke.call_args_list[2].args, ("setDeckConfigId", {"decks": ["Greek A1"], "configId": 77}))
        saved_config = invoke.call_args_list[4].args[1]["config"]
        self.assertTrue(saved_config["new"]["bury"])
        self.assertEqual(saved_config["newSortOrder"], 0)


if __name__ == "__main__":
    unittest.main()
