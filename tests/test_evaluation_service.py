"""Fresh sample evaluation through the shared runner, with the model fully mocked."""

import os
import unittest
from unittest.mock import patch

from deploy.evaluation_service import EvaluationError, evaluate_samples, sample_configuration
from scripts.evaluate import ROOT, load_fixtures
from scripts.extract import DEFAULT_MODEL
from scripts.run_baseline import run_baseline


class EvaluationServiceTests(unittest.TestCase):
    def setUp(self):
        self.labels, _ = load_fixtures(ROOT / "docs", ROOT / "expected")
        self.env = patch.dict(os.environ, {"OPENROUTER_API_KEY": "synthetic-key", "OPENROUTER_MODEL": DEFAULT_MODEL})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.extract_patch = patch("scripts.extract.extract", side_effect=lambda path, model, **kwargs: self.labels[path.stem])
        self.extract = self.extract_patch.start()
        self.addCleanup(self.extract_patch.stop)

    def test_runs_all_original_documents_with_fixed_reference_and_removes_outputs(self):
        with patch("deploy.evaluation_service.run_baseline", wraps=run_baseline) as runner:
            result = evaluate_samples()
        self.assertEqual(result["report"]["overall"]["correct"], 64)
        self.assertEqual(result["report"]["overall"]["total"], 64)
        self.assertEqual(self.extract.call_count, 8)
        self.assertEqual({call.args[0].stem for call in self.extract.call_args_list}, set(self.labels))
        for call in self.extract.call_args_list:
            self.assertEqual(call.args[0].parent, ROOT / "docs")
            self.assertEqual(call.args[1], DEFAULT_MODEL)
            self.assertEqual(call.kwargs["reference_date"], "2026-11-01")
            self.assertEqual(call.kwargs["expiring_soon_window_days"], 60)
            self.assertEqual(set(call.kwargs), {"metadata", "reference_date", "expiring_soon_window_days"})
        self.assertFalse(runner.call_args.args[0].parent.exists())
        self.assertEqual(runner.call_args.kwargs, {"verbose": False})

    def test_incomplete_run_keeps_every_document_in_score_without_retry(self):
        self.extract.side_effect = [self.labels["al_01"], RuntimeError("private provider response")]
        result = evaluate_samples()
        self.assertEqual(self.extract.call_count, 2)
        self.assertEqual(result["report"]["overall"]["correct"], 8)
        self.assertEqual(result["report"]["overall"]["total"], 64)
        self.assertEqual(result["run"]["documents"][1]["status"], "failed")
        self.assertTrue(all(row["status"] == "not_attempted" for row in result["run"]["documents"][2:]))
        self.assertNotIn("private provider response", str(result))

    def test_missing_key_never_starts_extraction(self):
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": ""}):
            with self.assertRaises(EvaluationError):
                evaluate_samples()
        self.extract.assert_not_called()

    def test_sample_configuration_reports_original_count_and_reference(self):
        self.assertEqual(sample_configuration(), {
            "document_count": 8,
            "reference": {"reference_date": "2026-11-01", "expiring_soon_window_days": 60},
        })
        self.extract.assert_not_called()

    def test_fixture_setup_errors_do_not_expose_internal_details(self):
        with patch("deploy.evaluation_service.load_fixtures", side_effect=ValueError("private path")):
            with self.assertRaises(EvaluationError) as error:
                sample_configuration()
        self.assertNotIn("private path", str(error.exception))


if __name__ == "__main__":
    unittest.main()
