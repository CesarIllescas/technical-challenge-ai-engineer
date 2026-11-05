"""Validate response metadata with mocked HTTP responses; no API calls."""

import copy
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import extract


class ExtractionMetadataTests(unittest.TestCase):
    def setUp(self):
        self.payload = {
            "id": "synthetic-generation", "model": "test/served", "provider": "test-provider",
            "created": 1793900000,
            "choices": [{"finish_reason": "stop", "native_finish_reason": "stop",
                         "message": {"content": '{"is_credential": false}',
                                     "reasoning": "private model reasoning"}}],
            "usage": {"prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120,
                      "cost": 0.0003, "is_byok": False,
                      "prompt_tokens_details": {"cached_tokens": 10},
                      "completion_tokens_details": {"reasoning_tokens": 5},
                      "cost_details": {"upstream_inference_cost": None}},
            "unexpected": "not accounting metadata",
        }
        self.post_patch = patch.object(extract.requests, "post")
        self.post = self.post_patch.start()
        self.addCleanup(self.post_patch.stop)
        self.response = Mock()
        self.response.json.return_value = self.payload
        self.post.return_value = self.response
        self.env_patch = patch.dict(os.environ, {"OPENROUTER_API_KEY": "synthetic-api-key"})
        self.env_patch.start()
        self.addCleanup(self.env_patch.stop)
        self.image_patch = patch.object(extract, "load_image", return_value=("image/png", "synthetic-image"))
        self.image_patch.start()
        self.addCleanup(self.image_patch.stop)

    def test_call_model_retains_response_and_does_not_change_request(self):
        returned = extract.call_model("image/png", "synthetic-image", "test/requested")
        self.assertEqual(returned, self.payload)
        self.response.raise_for_status.assert_called_once()
        self.response.json.assert_called_once()
        self.post.assert_called_once_with(
            extract.OPENROUTER_URL,
            headers={"Authorization": "Bearer synthetic-api-key"},
            json={"model": "test/requested", "messages": [{"role": "user", "content": [
                {"type": "text", "text": extract.PROMPT},
                {"type": "image_url", "image_url": {"url": "data:image/png;base64,synthetic-image"}},
            ]}]}, timeout=120,
        )

    def test_extract_preserves_prediction_interface_and_selects_metadata(self):
        metadata = {"stale": "must be cleared"}
        prediction = extract.extract(Path("synthetic.pdf"), "test/requested", metadata=metadata)
        self.assertEqual(prediction, {"is_credential": False})
        self.assertEqual(metadata, {
            "response_id": "synthetic-generation", "model": "test/served", "provider": "test-provider",
            "created": 1793900000, "finish_reason": "stop", "native_finish_reason": "stop",
            "usage": self.payload["usage"],
        })
        serialized = json.dumps(metadata)
        self.assertNotIn("private model reasoning", serialized)
        self.assertNotIn("synthetic-api-key", serialized)
        self.assertNotIn("is_credential", serialized)
        self.assertEqual(extract.extract(Path("synthetic.pdf"), "test/requested"), prediction)

    def test_invalid_json_content_still_captures_cost_and_finish_reason(self):
        self.payload["choices"][0]["message"]["content"] = "not JSON"
        self.payload["choices"][0]["finish_reason"] = "length"
        metadata = {}
        prediction = extract.extract(Path("synthetic.pdf"), "test/requested", metadata=metadata)
        self.assertEqual(prediction, {"error": "invalid JSON from model", "raw": "not JSON"})
        self.assertEqual(metadata["usage"]["cost"], 0.0003)
        self.assertEqual(metadata["finish_reason"], "length")

    def test_absent_optional_fields_do_not_break_extraction(self):
        self.response.json.return_value = {"choices": copy.deepcopy(self.payload["choices"])}
        metadata = {}
        self.assertEqual(extract.extract(Path("synthetic.pdf"), "test/requested", metadata=metadata),
                         {"is_credential": False})
        self.assertIsNone(metadata["usage"])
        self.assertIsNone(metadata["model"])
        self.assertIsNone(metadata["response_id"])

    def test_malformed_response_preserves_accounting_before_content_error(self):
        self.payload["choices"] = []
        metadata = {}
        with self.assertRaises(IndexError):
            extract.extract(Path("synthetic.pdf"), "test/requested", metadata=metadata)
        self.assertEqual(metadata["usage"]["cost"], 0.0003)

    def test_http_error_propagates_without_retry(self):
        self.response.raise_for_status.side_effect = extract.requests.HTTPError("synthetic error")
        metadata = {"stale": "must be cleared"}
        with self.assertRaises(extract.requests.HTTPError):
            extract.extract(Path("synthetic.pdf"), "test/requested", metadata=metadata)
        self.assertEqual(metadata, {})
        self.post.assert_called_once()
        self.response.json.assert_not_called()

    def test_cli_saves_metadata_separately_from_prediction(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            args = ["extract.py", "synthetic.pdf", "--out-dir", str(root / "predictions"),
                    "--metadata-dir", str(root / "metadata")]
            with patch("sys.argv", args), patch("sys.stdout"):
                extract.main()
            prediction = json.loads((root / "predictions/synthetic.json").read_text(encoding="utf-8"))
            metadata = json.loads((root / "metadata/synthetic.json").read_text(encoding="utf-8"))
            self.assertEqual(prediction, {"is_credential": False})
            self.assertEqual(metadata["response_id"], "synthetic-generation")
            self.assertEqual(metadata["usage"], self.payload["usage"])

    def test_cli_rejects_metadata_directory_that_would_overwrite_predictions(self):
        with tempfile.TemporaryDirectory() as directory:
            args = ["extract.py", "synthetic.pdf", "--out-dir", directory,
                    "--metadata-dir", directory]
            with patch("sys.argv", args), patch("sys.stderr"):
                with self.assertRaises(SystemExit) as error:
                    extract.main()
            self.assertEqual(error.exception.code, 2)
            self.post.assert_not_called()


if __name__ == "__main__":
    unittest.main()
