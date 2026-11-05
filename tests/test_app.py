"""Streamlit behavior checks with uploads and extraction mocked; no model requests."""

import json
import os
import types
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from scripts.credential import FIELDS
from scripts.extract import DEFAULT_MODEL
from scripts.evaluate import ROOT


NON_CREDENTIAL = {field: False if field == "is_credential" else None for field in FIELDS}
APP_PATH = Path(__file__).resolve().parents[1] / "deploy" / "app.py"


class InterfaceTests(unittest.TestCase):
    def setUp(self):
        self.env_patch = patch.dict(os.environ, {"OPENROUTER_API_KEY": "synthetic-key",
                                                "OPENROUTER_MODEL": DEFAULT_MODEL})
        self.env_patch.start()
        self.addCleanup(self.env_patch.stop)
        self.extract_patch = patch("deploy.upload_service.extract", return_value=NON_CREDENTIAL)
        self.extract = self.extract_patch.start()
        self.addCleanup(self.extract_patch.stop)
        self.upload_patch = patch("streamlit.file_uploader", return_value=None)
        self.upload = self.upload_patch.start()
        self.addCleanup(self.upload_patch.stop)
        report = json.loads((ROOT / "results/v02-image-quality/evaluation.json").read_text(encoding="utf-8"))
        self.evaluation_result = {"report": report, "run": {
            "documents": [{"document": row["document"], "status": "returned_output"} for row in report["documents"]],
            "cost_usd": None, "reported_cost_usd": None,
        }}
        self.evaluation_patch = patch("deploy.evaluation_service.evaluate_samples", return_value=self.evaluation_result)
        self.evaluate_samples = self.evaluation_patch.start()
        self.addCleanup(self.evaluation_patch.stop)

    def app(self):
        app = AppTest.from_file(str(APP_PATH), default_timeout=10)
        app.secrets["OPENROUTER_API_KEY"] = "synthetic-key"
        return app

    def test_initial_page_does_not_call_model(self):
        app = self.app().run()
        self.assertFalse(app.exception)
        self.assertEqual(app.title[0].value, "Credential extractor")
        self.assertTrue(app.button[0].disabled)
        self.assertEqual(app.date_input[0].value, date(2026, 11, 1))
        self.extract.assert_not_called()
        self.evaluate_samples.assert_not_called()

    def test_upload_submit_shows_json_without_automatic_repeat(self):
        self.upload.return_value = types.SimpleNamespace(name="sample.pdf", getvalue=lambda: b"synthetic bytes")
        app = self.app().run()
        self.extract.assert_not_called()
        self.assertFalse(app.button[0].disabled)
        app.button[0].click().run()
        self.assertFalse(app.exception)
        self.assertEqual(json.loads(app.json[0].value), NON_CREDENTIAL)
        self.assertTrue(app.button[0].disabled)
        self.assertTrue(any("not a license" in element.value for element in app.info))
        app.run()
        self.extract.assert_called_once()
        app.date_input[0].set_value(date(2030, 1, 2)).run()
        self.assertFalse(app.exception)
        self.assertEqual(len(app.json), 0)
        self.assertFalse(app.button[0].disabled)
        self.extract.assert_called_once()

    def test_changed_document_clears_previous_json_without_model_call(self):
        self.upload.return_value = types.SimpleNamespace(name="first.pdf", getvalue=lambda: b"first document")
        app = self.app().run()
        app.button[0].click().run()
        self.upload.return_value = types.SimpleNamespace(name="second.pdf", getvalue=lambda: b"second document")
        app.run()
        self.assertFalse(app.exception)
        self.assertEqual(len(app.json), 0)
        self.extract.assert_called_once()

    def test_provider_failure_shows_controlled_error_without_raw_body(self):
        self.upload.return_value = types.SimpleNamespace(name="sample.pdf", getvalue=lambda: b"synthetic bytes")
        self.extract.return_value = {"error": "invalid JSON", "raw": "private provider body"}
        app = self.app().run()
        app.button[0].click().run()
        self.assertFalse(app.exception)
        self.assertEqual(len(app.json), 0)
        self.assertTrue(any("reliably" in element.value for element in app.error))
        self.assertFalse(any("private provider" in element.value for element in app.error))

    def test_missing_key_disables_submission(self):
        self.upload.return_value = types.SimpleNamespace(name="sample.pdf", getvalue=lambda: b"synthetic bytes")
        app = self.app()
        app.secrets["OPENROUTER_API_KEY"] = ""
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": ""}):
            app.run()
        self.assertFalse(app.exception)
        self.assertTrue(app.button[0].disabled)
        self.assertTrue(app.button[1].disabled)
        self.assertTrue(app.warning)
        self.extract.assert_not_called()

    def test_explicit_evaluation_displays_accuracy_and_persists_without_repeating_calls(self):
        app = self.app().run()
        self.evaluate_samples.assert_not_called()
        app.button[1].click().run()
        self.assertFalse(app.exception)
        self.assertEqual(app.metric[0].label, "Field accuracy")
        self.assertEqual(app.metric[0].value, "100.00%")
        self.assertEqual(len(app.dataframe[0].value), 8)
        self.assertEqual(len(app.dataframe[1].value), 8)
        app.run()
        app.date_input[0].set_value(date(2030, 1, 2)).run()
        self.assertFalse(app.exception)
        self.assertEqual(app.metric[0].value, "100.00%")
        self.evaluate_samples.assert_called_once_with()
        self.extract.assert_not_called()

    def test_changed_server_model_clears_sample_report_without_new_calls(self):
        app = self.app().run()
        app.button[1].click().run()
        with patch.dict(os.environ, {"OPENROUTER_MODEL": "synthetic/other-model"}):
            app.run()
        self.assertFalse(app.exception)
        self.assertEqual(len(app.metric), 0)
        self.evaluate_samples.assert_called_once()

    def test_evaluation_error_is_shown_without_claiming_accuracy(self):
        from deploy.evaluation_service import EvaluationError
        self.evaluate_samples.side_effect = EvaluationError("Sample evaluation unavailable.")
        app = self.app().run()
        app.button[1].click().run()
        self.assertFalse(app.exception)
        self.assertEqual(len(app.metric), 0)
        self.assertTrue(any("unavailable" in row.value for row in app.error))

    def test_streamlit_server_secret_enables_upload_without_exposing_key(self):
        self.upload.return_value = types.SimpleNamespace(name="sample.pdf", getvalue=lambda: b"synthetic bytes")
        app = self.app()
        app.secrets["OPENROUTER_API_KEY"] = "synthetic-server-secret"
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": ""}):
            app.run()
        self.assertFalse(app.exception)
        self.assertFalse(app.button[0].disabled)
        self.assertFalse(app.warning)
        self.assertFalse(any("synthetic-server-secret" in element.value for element in app.markdown))
        self.extract.assert_not_called()


if __name__ == "__main__":
    unittest.main()
