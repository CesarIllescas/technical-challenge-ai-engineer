"""Exercise the paid-run orchestration with a fake extractor; never make API calls."""

import json
import os
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from scripts.evaluate import DOCUMENT_EXTENSIONS, ROOT, load_fixtures
from scripts.run_baseline import run_baseline


class BaselineRunnerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.run_dir = Path(self.temp.name) / "baseline"
        self.labels, _ = load_fixtures(ROOT / "docs", ROOT / "expected")
        self.fake = types.ModuleType("extract")
        self.fake.DEFAULT_MODEL = "test/default"
        self.fake.SUPPORTED_EXTENSIONS = DOCUMENT_EXTENSIONS
        self.fake.extract = Mock(side_effect=lambda path, model, **kwargs: self.labels[path.stem])
        self.module_patch = patch("scripts.extract", self.fake)
        self.module_patch.start()
        self.addCleanup(self.module_patch.stop)
        self.env_patch = patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-placeholder"}, clear=True)
        self.env_patch.start()
        self.addCleanup(self.env_patch.stop)
        self.stdout_patch = patch("sys.stdout")
        self.stdout_patch.start()
        self.addCleanup(self.stdout_patch.stop)

    def test_saves_original_outputs_provenance_and_evaluation(self):
        metadata = run_baseline(self.run_dir)
        self.assertEqual(self.fake.extract.call_count, 8)
        self.assertEqual(metadata["model_requested"], "test/default")
        self.assertTrue(metadata["reference_applied_to_extractor"])
        self.assertIsNone(metadata["cost_usd"])
        self.assertIsNone(metadata["usage"])
        self.assertEqual(metadata["cost_reported_documents"], 0)
        self.assertIsNone(metadata["reported_cost_usd"])
        self.assertIn("scripts/extract.py", metadata["sha256"])
        self.assertIn("docs/tx_01.pdf", metadata["sha256"])
        self.assertTrue(all(row["status"] == "returned_output" for row in metadata["documents"]))
        self.assertTrue(all(row["elapsed_seconds"] >= 0 for row in metadata["documents"]))
        for path, model in (call.args for call in self.fake.extract.call_args_list):
            self.assertEqual(model, "test/default")
            output = json.loads((self.run_dir / "predictions" / f"{path.stem}.json").read_text(encoding="utf-8"))
            self.assertEqual(output, self.labels[path.stem])
        for call in self.fake.extract.call_args_list:
            self.assertEqual(call.kwargs["reference_date"], "2026-11-01")
            self.assertEqual(call.kwargs["expiring_soon_window_days"], 60)
        report = json.loads((self.run_dir / "evaluation.json").read_text(encoding="utf-8"))
        self.assertEqual(report["overall"]["correct"], 64)
        self.assertNotIn("test-placeholder", (self.run_dir / "run.json").read_text(encoding="utf-8"))

    def test_operational_failure_stops_without_retry_and_scores_remaining_as_missing(self):
        failure = RuntimeError("sensitive provider response")
        failure.response = types.SimpleNamespace(status_code=400)
        self.fake.extract.side_effect = [self.labels["al_01"], failure]
        metadata = run_baseline(self.run_dir, "test/explicit")
        self.assertEqual(self.fake.extract.call_count, 2)
        self.assertEqual(metadata["model_requested"], "test/explicit")
        self.assertEqual(metadata["documents"][1]["status"], "failed")
        self.assertEqual(metadata["documents"][1]["http_status"], 400)
        self.assertTrue(all(row["status"] == "not_attempted" for row in metadata["documents"][2:]))
        self.assertNotIn("sensitive provider response", (self.run_dir / "run.json").read_text(encoding="utf-8"))
        report = json.loads((self.run_dir / "evaluation.json").read_text(encoding="utf-8"))
        self.assertEqual(report["overall"]["correct"], 8)
        self.assertEqual(report["overall"]["total"], 64)

    def test_invalid_json_error_output_is_preserved(self):
        output = {"error": "invalid JSON from model", "raw": "synthetic unparseable response"}
        self.fake.extract.side_effect = lambda path, model, **kwargs: output
        run_baseline(self.run_dir)
        saved = json.loads((self.run_dir / "predictions" / "al_01.json").read_text(encoding="utf-8"))
        self.assertEqual(saved, output)
        report = json.loads((self.run_dir / "evaluation.json").read_text(encoding="utf-8"))
        self.assertEqual(report["overall"]["correct"], 0)

    def test_preflight_rejects_existing_directory_without_extraction(self):
        self.run_dir.mkdir()
        with self.assertRaisesRegex(ValueError, "already exists"):
            run_baseline(self.run_dir)
        self.fake.extract.assert_not_called()

    def test_preflight_rejects_missing_credentials_without_writing(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(ValueError, "OPENROUTER_API_KEY is not set"):
                run_baseline(self.run_dir)
        self.fake.extract.assert_not_called()
        self.assertFalse(self.run_dir.exists())

    def test_model_environment_override(self):
        with patch.dict(os.environ, {"OPENROUTER_MODEL": "test/environment"}):
            self.assertEqual(run_baseline(self.run_dir)["model_requested"], "test/environment")

    def test_quiet_mode_retains_outputs_without_printing_document_data(self):
        with patch("sys.stdout") as stdout:
            metadata = run_baseline(self.run_dir, verbose=False)
        stdout.write.assert_not_called()
        self.assertEqual(len(metadata["documents"]), 8)
        self.assertTrue((self.run_dir / "evaluation.json").is_file())

    def test_aggregates_response_costs_and_native_token_counts(self):
        def extract(path, model, *, metadata, **kwargs):
            metadata.update({
                "response_id": f"synthetic-{path.stem}", "model": "test/served",
                "usage": {"prompt_tokens": 100, "completion_tokens": 20,
                          "total_tokens": 120, "cost": 0.0003},
            })
            return self.labels[path.stem]
        self.fake.extract.side_effect = extract
        metadata = run_baseline(self.run_dir)
        self.assertEqual(metadata["models_reported"], ["test/served"])
        self.assertEqual(metadata["usage"], {
            "prompt_tokens": 800, "completion_tokens": 160, "total_tokens": 960,
        })
        self.assertEqual(metadata["usage_reported_documents"], 8)
        self.assertEqual(metadata["cost_reported_documents"], 8)
        self.assertAlmostEqual(metadata["cost_usd"], 0.0024)
        self.assertAlmostEqual(metadata["mean_cost_per_document_usd"], 0.0003)
        saved = json.loads((self.run_dir / "run.json").read_text(encoding="utf-8"))
        self.assertEqual(saved, metadata)

    def test_partial_failure_preserves_known_charge_without_claiming_total_cost(self):
        def extract(path, model, *, metadata, **kwargs):
            if path.stem == "al_01":
                metadata.update({"usage": {"cost": 0.0003}})
                return self.labels[path.stem]
            # A response may include accounting even if its content cannot be consumed.
            metadata.update({"usage": {"cost": 0.0002}})
            raise KeyError("synthetic missing choices")
        self.fake.extract.side_effect = extract
        metadata = run_baseline(self.run_dir)
        self.assertEqual(self.fake.extract.call_count, 2)
        self.assertEqual(metadata["cost_reported_documents"], 2)
        self.assertAlmostEqual(metadata["reported_cost_usd"], 0.0005)
        self.assertIsNone(metadata["cost_usd"])
        self.assertIsNone(metadata["mean_cost_per_document_usd"])

    def test_missing_cost_is_distinct_from_explicit_zero(self):
        for cost in (None, 0, True, -0.01, "0.01"):
            with self.subTest(cost=cost):
                def extract(path, model, *, metadata, **kwargs):
                    metadata.update({"usage": {"cost": cost}})
                    return self.labels[path.stem]
                self.fake.extract.side_effect = extract
                result = run_baseline(self.run_dir / str(cost))
                self.assertEqual(result["cost_usd"], 0 if type(cost) is int and cost == 0 else None)


if __name__ == "__main__":
    unittest.main()
