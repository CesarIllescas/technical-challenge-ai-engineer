"""Offline scoring checks. Perfect predictions below are synthetic, not model results."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.evaluate import ROOT, evaluate, load_fixtures


class EvaluationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.predictions = Path(self.temp.name)
        self.labels, _ = load_fixtures(ROOT / "docs", ROOT / "expected")
        for stem, label in self.labels.items():
            self.write(stem, label)

    def write(self, stem, value):
        (self.predictions / f"{stem}.json").write_text(
            json.dumps(value, ensure_ascii=False), encoding="utf-8"
        )

    def test_fixture_discovery_and_perfect_synthetic_predictions(self):
        report = evaluate(self.predictions)
        self.assertEqual(report["document_count"], 8)
        self.assertEqual(report["overall"], {"correct": 64, "total": 64, "accuracy": 1.0})
        self.assertEqual(report["schema_validity"]["correct"], 8)
        self.assertEqual(report["complete_documents"]["correct"], 8)
        self.assertEqual(report["by_expected_value"]["null"]["total"], 13)
        self.assertEqual(report["by_expected_value"]["non_null"]["total"], 51)
        self.assertEqual(report["reference"], {
            "reference_date": "2026-11-01", "expiring_soon_window_days": 60,
        })
        self.assertTrue(all(value["total"] == 8 for value in report["per_field"].values()))

    def test_invalid_or_wrong_fields_cannot_receive_credit(self):
        cases = [
            ("is_credential", 1, False),
            ("license_number", 41872, False),
            ("issue_date", "2012-02-30", False),
            ("issue_date", "20120314", False),
            ("issue_date", "2012-03-14T00:00:00", False),
            ("expiration_status", "active", False),
            ("holder_name", "tamsin rae holloway", True),
            ("license_number", "MD. 41872", True),
            ("holder_name", None, True),
        ]
        for field, actual, valid_schema in cases:
            with self.subTest(field=field, actual=actual):
                prediction = dict(self.labels["al_01"])
                prediction[field] = actual
                self.write("al_01", prediction)
                report = evaluate(self.predictions)
                self.assertEqual(report["overall"]["correct"], 63)
                self.assertEqual(report["per_field"][field]["correct"], 7)
                self.assertEqual(report["schema_validity"]["correct"], 8 if valid_schema else 7)
                self.assertEqual(report["complete_documents"]["correct"], 7)

    def test_missing_null_field_is_not_null(self):
        prediction = dict(self.labels["ny_01"])
        del prediction["issue_date"]
        self.write("ny_01", prediction)
        report = evaluate(self.predictions)
        self.assertEqual(report["overall"]["correct"], 63)
        self.assertEqual(report["by_expected_value"]["null"]["correct"], 12)
        prediction["issue_date"] = "null"
        self.write("ny_01", prediction)
        self.assertEqual(evaluate(self.predictions)["overall"]["correct"], 63)

    def test_failed_predictions_remain_in_denominator(self):
        path = self.predictions / "al_01.json"
        cases = [None, '{"broken":', '[]', 'null', '"text"',
                 '{"error": "model failed"}', '{"is_credential": NaN}',
                 '{"is_credential": true, "is_credential": false}']
        for content in cases:
            with self.subTest(content=content):
                if content is None:
                    path.unlink()
                else:
                    path.write_text(content, encoding="utf-8")
                report = evaluate(self.predictions)
                self.assertEqual(report["overall"]["correct"], 56)
                self.assertEqual(report["overall"]["total"], 64)
                self.assertEqual(report["schema_validity"]["correct"], 7)
                self.assertTrue(all(value["total"] == 8 for value in report["per_field"].values()))

    def test_empty_predictions_score_zero(self):
        for path in self.predictions.iterdir():
            path.unlink()
        report = evaluate(self.predictions)
        self.assertEqual(report["overall"]["correct"], 0)
        self.assertEqual(report["overall"]["total"], 64)

    def test_extra_keys_fail_schema_without_erasing_correct_fields(self):
        self.write("al_01", {**self.labels["al_01"], "summary": "extra"})
        self.write("unrelated", {})
        report = evaluate(self.predictions)
        self.assertEqual(report["overall"]["correct"], 64)
        self.assertEqual(report["schema_validity"]["correct"], 7)
        self.assertEqual(report["complete_documents"]["correct"], 7)
        self.assertEqual(report["ignored_prediction_files"], ["unrelated.json"])

    def test_serialization_order_and_unicode_preservation(self):
        self.write("tx_01", dict(reversed(list(self.labels["tx_01"].items()))))
        self.assertEqual(evaluate(self.predictions)["overall"]["correct"], 64)
        prediction = dict(self.labels["tx_01"])
        prediction["holder_name"] = "ADRIANA LUCIA FERRER"
        self.write("tx_01", prediction)
        self.assertEqual(evaluate(self.predictions)["overall"]["correct"], 63)

    def test_fixture_pairing_errors_stop_evaluation(self):
        docs = self.predictions / "docs"
        docs.mkdir()
        with self.assertRaisesRegex(ValueError, "pairing failed"):
            evaluate(self.predictions, docs_dir=docs)
        for stem in self.labels:
            (docs / f"{stem}.pdf").touch()
        (docs / "al_01.png").touch()
        with self.assertRaisesRegex(ValueError, "duplicate document stem"):
            evaluate(self.predictions, docs_dir=docs)

    def test_cli_writes_report_and_rejects_missing_directory(self):
        report_path = self.predictions / "reports" / "score.json"
        result = subprocess.run(
            [sys.executable, "-B", "-m", "scripts.evaluate", "--predictions",
             str(self.predictions), "--report", str(report_path)],
            capture_output=True, text=True, encoding="utf-8",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("64/64", result.stdout)
        self.assertEqual(json.loads(report_path.read_text(encoding="utf-8"))["overall"]["correct"], 64)
        result = subprocess.run(
            [sys.executable, "-B", "-m", "scripts.evaluate", "--predictions",
             str(self.predictions / "missing")], capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 2)


if __name__ == "__main__":
    unittest.main()
