import base64
import unittest

from generator.webui.input_parser import InputError, parse_text, parse_uploaded_file
from generator.webui.jobs import JobError, JobManager


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


if __name__ == "__main__":
    unittest.main()
