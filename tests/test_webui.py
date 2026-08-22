import base64
import errno
import unittest
from pathlib import Path

from generator.api_calls.text_prompt_by_language import prompt_by_language
from generator.config import A1, A2, C1, Config, GREEK
from generator.webui.input_parser import InputError, parse_text, parse_uploaded_file
from generator.webui.jobs import JobError, JobManager
from generator.webui.server import create_server_with_fallback


class InputParserTests(unittest.TestCase):
    def test_parses_semicolon_csv(self):
        cards = parse_text('word;context\n"free will";philosophy\nhello;greeting')

        self.assertEqual(
            cards,
            [
                {"word": "free will", "context": "philosophy"},
                {"word": "hello", "context": "greeting"},
            ],
        )

    def test_parses_plain_lines_with_optional_context(self):
        cards = parse_text("consciousness\npurchasing power;economics")

        self.assertEqual(cards[0], {"word": "consciousness", "context": ""})
        self.assertEqual(cards[1], {"word": "purchasing power", "context": "economics"})

    def test_parses_base64_uploaded_csv(self):
        encoded = base64.b64encode("word;context\nHaus;building".encode()).decode()

        cards = parse_uploaded_file("german.csv", encoded)

        self.assertEqual(cards, [{"word": "Haus", "context": "building"}])

    def test_rejects_empty_input(self):
        with self.assertRaises(InputError):
            parse_text("  \n  ")


class JobManagerTests(unittest.TestCase):
    def setUp(self):
        self.manager = JobManager()

    def test_snapshot_never_exposes_api_keys(self):
        job = self.manager.create(
            [{"word": "hello", "context": "greeting"}],
            {"openai_api_key": "secret", "replicate_api_key": "another-secret"},
        )

        self.assertNotIn("openai_api_key", job["settings"])
        self.assertNotIn("replicate_api_key", job["settings"])
        self.assertEqual(self.manager.private_settings(job["id"])["openai_api_key"], "secret")

    def test_progress_counts_terminal_card_states(self):
        job = self.manager.create(
            [{"word": "one"}, {"word": "two"}],
            {"processing_directory": "/tmp/cards"},
        )
        self.manager.update_card(job["id"], "1", status="generated")

        snapshot = self.manager.snapshot(job["id"])

        self.assertEqual(snapshot["progress"], {"finished": 1, "total": 2, "percent": 50})

    def test_api_keys_are_removed_after_job_finishes(self):
        job = self.manager.create(
            [{"word": "hello"}],
            {"openai_api_key": "secret", "processing_directory": "/tmp/cards"},
        )

        self.manager.set_job(job["id"], status="completed")

        self.assertNotIn("openai_api_key", self.manager.private_settings(job["id"]))

    def test_unknown_job_is_rejected(self):
        with self.assertRaises(JobError):
            self.manager.snapshot("missing")


class GreekLanguageTests(unittest.TestCase):
    def tearDown(self):
        Config.LANGUAGE = Config.DEFAULT_LANGUAGE
        Config.LEVEL = Config.DEFAULT_LEVEL

    def test_greek_supports_only_a1_and_a2(self):
        Config.set_language_or_use_default(GREEK)

        self.assertEqual(Config.supported_levels_for_language(), [A1, A2])
        Config.set_level_or_use_default(A2)
        self.assertEqual(Config.LEVEL, A2)
        with self.assertRaises(Exception):
            Config.set_level_or_use_default(C1)

    def test_greek_defaults_to_a1(self):
        Config.set_language_or_use_default(GREEK)

        Config.set_level_or_use_default(None)

        self.assertEqual(Config.LEVEL, A1)

    def test_greek_prompt_is_routed(self):
        Config.LANGUAGE = GREEK
        Config.LEVEL = A1

        prompt = prompt_by_language.get_system_prompt_by_language()

        self.assertIn("σύγχρονης ελληνικής", prompt)
        self.assertIn("Επίπεδο A1", prompt)

    def test_web_interface_contains_greek_option(self):
        html = (Path(__file__).parents[1] / "generator" / "webui" / "templates" / "index.html").read_text()

        self.assertIn('value="greek"', html)


class ServerStartupTests(unittest.TestCase):
    def test_uses_next_port_when_preferred_port_is_busy(self):
        attempts = []
        expected_server = object()

        def fake_server_factory(host, port):
            attempts.append((host, port))
            if port == 8766:
                raise OSError(errno.EADDRINUSE, "Address already in use")
            return expected_server

        server, port = create_server_with_fallback(
            "127.0.0.1",
            8766,
            server_factory=fake_server_factory,
        )

        self.assertIs(server, expected_server)
        self.assertEqual(port, 8767)
        self.assertEqual(attempts, [("127.0.0.1", 8766), ("127.0.0.1", 8767)])

    def test_does_not_hide_unrelated_socket_errors(self):
        def fake_server_factory(_host, _port):
            raise OSError(errno.EACCES, "Permission denied")

        with self.assertRaises(OSError) as raised:
            create_server_with_fallback(
                "127.0.0.1",
                8766,
                server_factory=fake_server_factory,
            )

        self.assertEqual(raised.exception.errno, errno.EACCES)


class CardPreviewTests(unittest.TestCase):
    def test_interface_has_front_and_back_card_faces(self):
        project_root = Path(__file__).parents[1]
        html = (project_root / "generator" / "webui" / "templates" / "index.html").read_text()
        javascript = (project_root / "generator" / "webui" / "static" / "app.js").read_text()

        self.assertIn('id="preview-front"', html)
        self.assertIn('id="preview-back"', html)
        self.assertIn('id="preview-back-word"', html)
        self.assertIn("function setPreviewSide", javascript)


if __name__ == "__main__":
    unittest.main()
