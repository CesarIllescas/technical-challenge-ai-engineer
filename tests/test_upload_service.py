"""Upload lifecycle and error checks with no provider requests."""

import os
import types
import unittest
from pathlib import Path
from unittest.mock import patch

import requests

from scripts.credential import FIELDS
from scripts.extract import DEFAULT_MODEL
from deploy.upload_service import MAX_UPLOAD_BYTES, UploadError, extract_upload


NON_CREDENTIAL = {field: False if field == "is_credential" else None for field in FIELDS}


class UploadServiceTests(unittest.TestCase):
    def setUp(self):
        self.env_patch = patch.dict(os.environ, {"OPENROUTER_API_KEY": "synthetic-key",
                                                "OPENROUTER_MODEL": DEFAULT_MODEL})
        self.env_patch.start()
        self.addCleanup(self.env_patch.stop)
        self.extract_patch = patch("deploy.upload_service.extract", return_value=NON_CREDENTIAL)
        self.extract = self.extract_patch.start()
        self.addCleanup(self.extract_patch.stop)

    def test_upload_uses_safe_temporary_path_and_cleans_up_after_success(self):
        used_paths = []
        def check_file(path, model, **kwargs):
            used_paths.append(path)
            self.assertEqual(path.name, "document.pdf")
            self.assertEqual(path.read_bytes(), b"synthetic uploaded bytes")
            self.assertEqual(model, DEFAULT_MODEL)
            self.assertEqual(kwargs, {"reference_date": "2030-01-02", "expiring_soon_window_days": 30})
            return NON_CREDENTIAL
        self.extract.side_effect = check_file
        result = extract_upload("../../untrusted.PDF", b"synthetic uploaded bytes", "2030-01-02", 30)
        self.assertEqual(result, NON_CREDENTIAL)
        self.assertFalse(used_paths[0].exists())
        self.assertFalse(used_paths[0].parent.exists())
        self.extract.assert_called_once()

    def test_invalid_uploads_do_not_call_extractor(self):
        for filename, content in [("file.txt", b"text"), ("file.pdf", b""),
                                  ("file.png", b"x" * (MAX_UPLOAD_BYTES + 1))]:
            with self.subTest(filename=filename):
                with self.assertRaises(UploadError):
                    extract_upload(filename, content, "2026-11-01", 60)
        self.extract.assert_not_called()

    def test_missing_key_is_a_controlled_error_without_call(self):
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": ""}):
            with self.assertRaises(UploadError):
                extract_upload("file.pdf", b"content", "2026-11-01", 60)
        self.extract.assert_not_called()

    def test_temporary_file_is_removed_after_timeout_without_retry(self):
        used_paths = []
        def timeout(path, *args, **kwargs):
            used_paths.append(path)
            raise requests.Timeout("private provider response")
        self.extract.side_effect = timeout
        with self.assertRaisesRegex(UploadError, "timed out") as error:
            extract_upload("file.pdf", b"content", "2026-11-01", 60)
        self.assertNotIn("private", str(error.exception))
        self.assertFalse(used_paths[0].parent.exists())
        self.extract.assert_called_once()

    def test_provider_errors_are_sanitized(self):
        for status, expected in [(401, "authenticate"), (402, "credit"), (429, "busy"), (500, "provider")]:
            with self.subTest(status=status):
                failure = requests.HTTPError("private response with synthetic-key")
                failure.response = types.SimpleNamespace(status_code=status)
                self.extract.side_effect = failure
                with self.assertRaisesRegex(UploadError, expected) as error:
                    extract_upload("file.pdf", b"content", "2026-11-01", 60)
                self.assertNotIn("synthetic-key", str(error.exception))
                self.assertNotIn("private response", str(error.exception))

    def test_invalid_model_output_is_not_exposed_as_json(self):
        self.extract.return_value = {"error": "invalid JSON from model", "raw": "private document data"}
        with self.assertRaisesRegex(UploadError, "reliably") as error:
            extract_upload("file.pdf", b"content", "2026-11-01", 60)
        self.assertNotIn("private", str(error.exception))


if __name__ == "__main__":
    unittest.main()
