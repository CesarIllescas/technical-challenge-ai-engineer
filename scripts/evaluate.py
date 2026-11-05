"""Evaluate saved credential predictions without importing or calling the extractor."""

import argparse
import json
from pathlib import Path

from scripts.credential import FIELDS, STATUSES, schema_errors, valid_date

ROOT = Path(__file__).resolve().parents[1]
DOCUMENT_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".webp"}


def _unique_object(pairs: list[tuple]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise ValueError(f"invalid JSON constant: {value}")


def read_json(path: Path) -> object:
    return json.loads(
        path.read_text(encoding="utf-8"),
        object_pairs_hook=_unique_object,
        parse_constant=_reject_constant,
    )


def load_fixtures(docs_dir: Path, expected_dir: Path) -> tuple[dict, dict]:
    """Require a one-to-one document/label mapping before any scoring."""
    if not docs_dir.is_dir() or not expected_dir.is_dir():
        raise ValueError("document and expected-output directories must exist")
    documents = {}
    for path in sorted(docs_dir.iterdir()):
        if path.is_file() and path.suffix.lower() in DOCUMENT_EXTENSIONS:
            if path.stem in documents:
                raise ValueError(f"duplicate document stem: {path.stem}")
            documents[path.stem] = path
    labels = {
        path.stem: path for path in sorted(expected_dir.glob("*.json"))
        if path.name != "_reference.json"
    }
    if not documents or set(documents) != set(labels):
        raise ValueError(
            "document/label pairing failed: "
            f"missing labels={sorted(set(documents) - set(labels))}; "
            f"missing documents={sorted(set(labels) - set(documents))}"
        )
    reference = read_json(expected_dir / "_reference.json")
    if (
        not isinstance(reference, dict)
        or not isinstance(reference.get("reference_date"), str)
        or not valid_date(reference["reference_date"])
        or type(reference.get("expiring_soon_window_days")) is not int
        or reference["expiring_soon_window_days"] < 0
    ):
        raise ValueError("invalid reference configuration")
    expected = {}
    for stem, path in labels.items():
        value = read_json(path)
        errors = schema_errors(value)
        if errors:
            raise ValueError(f"invalid expected output {path.name}: {errors}")
        expected[stem] = value
    return expected, reference


def metric(correct: int, total: int) -> dict:
    return {"correct": correct, "total": total, "accuracy": correct / total if total else None}


def evaluate(predictions_dir: Path, docs_dir: Path = ROOT / "docs",
             expected_dir: Path = ROOT / "expected") -> dict:
    if not predictions_dir.is_dir():
        raise ValueError("prediction directory must exist")
    expected, reference = load_fixtures(docs_dir, expected_dir)
    correct_by_field = dict.fromkeys(FIELDS, 0)
    null_totals = {"null": 0, "non_null": 0}
    null_correct = {"null": 0, "non_null": 0}
    documents = []
    for stem, label in expected.items():
        prediction = None
        prediction_error = None
        try:
            prediction = read_json(predictions_dir / f"{stem}.json")
        except FileNotFoundError:
            prediction_error = "missing prediction file"
        except (OSError, ValueError) as exc:
            # Never include the raw model response in parse-error diagnostics.
            prediction_error = f"could not read prediction ({type(exc).__name__})"
        errors = schema_errors(prediction) if prediction_error is None else {"$": prediction_error}
        mismatches = {}
        correct_fields = 0
        for field in FIELDS:
            group = "null" if label[field] is None else "non_null"
            null_totals[group] += 1
            if prediction_error is not None or not isinstance(prediction, dict):
                mismatch = {"expected": label[field], "reason": errors["$"]}
            elif field not in prediction:
                mismatch = {"expected": label[field], "reason": "missing field"}
            else:
                actual = prediction[field]
                matches = (
                    field not in errors
                    and type(actual) is type(label[field])
                    and actual == label[field]
                )
                if matches:
                    correct_by_field[field] += 1
                    null_correct[group] += 1
                    correct_fields += 1
                    continue
                mismatch = {
                    "expected": label[field], "actual": actual,
                    "reason": errors.get(field, "value differs"),
                }
            mismatches[field] = mismatch
        documents.append({
            "document": stem,
            "schema_valid": not errors,
            "schema_errors": errors,
            "correct_fields": correct_fields,
            "exact_match": correct_fields == len(FIELDS) and not errors,
            "mismatches": mismatches,
        })
    count = len(documents)
    return {
        "reference": reference,
        "document_count": count,
        "per_field": {field: metric(correct, count) for field, correct in correct_by_field.items()},
        "overall": metric(sum(correct_by_field.values()), count * len(FIELDS)),
        "schema_validity": metric(sum(doc["schema_valid"] for doc in documents), count),
        "complete_documents": metric(sum(doc["exact_match"] for doc in documents), count),
        "by_expected_value": {
            group: metric(null_correct[group], null_totals[group]) for group in null_totals
        },
        "ignored_prediction_files": sorted(
            path.name for path in predictions_dir.glob("*.json") if path.stem not in expected
        ),
        "documents": documents,
    }


def print_report(report: dict) -> None:
    reference = report["reference"]
    print(f"Documents: {report['document_count']}; reference: {reference['reference_date']}; "
          f"window: {reference['expiring_soon_window_days']} days")
    metrics = list(report["per_field"].items()) + [
        ("overall fields", report["overall"]),
        ("schema validity", report["schema_validity"]),
        ("complete documents", report["complete_documents"]),
    ] + [(f"expected {group}", value) for group, value in report["by_expected_value"].items()]
    for name, value in metrics:
        accuracy = "n/a" if value["accuracy"] is None else f"{value['accuracy']:.1%}"
        print(f"{name:24} {value['correct']:3}/{value['total']:<3} {accuracy:>6}")
    for document in report["documents"]:
        if not document["exact_match"]:
            print(f"\n{document['document']}: {document['correct_fields']}/{len(FIELDS)} fields")
            if document["schema_errors"]:
                print("  schema: " + json.dumps(document["schema_errors"], ensure_ascii=False))
            for field, mismatch in document["mismatches"].items():
                print(f"  {field}: " + json.dumps(mismatch, ensure_ascii=False))
    if report["ignored_prediction_files"]:
        print("\nIgnored predictions: " + ", ".join(report["ignored_prediction_files"]))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--predictions", type=Path, required=True, help="Directory of <document>.json outputs")
    parser.add_argument("--docs", type=Path, default=ROOT / "docs")
    parser.add_argument("--expected", type=Path, default=ROOT / "expected")
    parser.add_argument("--report", type=Path, help="Optionally save the detailed JSON report")
    args = parser.parse_args()
    try:
        report = evaluate(args.predictions, args.docs, args.expected)
        if args.report:
            args.report.parent.mkdir(parents=True, exist_ok=True)
            args.report.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    print_report(report)


if __name__ == "__main__":
    main()
