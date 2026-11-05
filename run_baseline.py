"""Run the current extractor, capture response metadata, and evaluate it (makes API calls)."""

import argparse
import hashlib
import importlib.metadata
import json
import math
import os
import platform
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter

from evaluate import ROOT, evaluate, load_fixtures, print_report


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def update_accounting(metadata: dict) -> None:
    """Keep incomplete accounting explicit instead of treating absent values as zero."""
    responses = [record.get("response") or {} for record in metadata["documents"]]
    usages = [response.get("usage") or {} for response in responses]
    token_fields = ("prompt_tokens", "completion_tokens", "total_tokens")
    complete_usage = [
        usage for usage in usages
        if all(type(usage.get(field)) is int and usage[field] >= 0 for field in token_fields)
    ]
    costs = [
        usage["cost"] for usage in usages
        if type(usage.get("cost")) in (int, float)
        and math.isfinite(usage["cost"]) and usage["cost"] >= 0
    ]
    count = len(responses)
    metadata["models_reported"] = sorted({
        response["model"] for response in responses if isinstance(response.get("model"), str)
    })
    metadata["usage_reported_documents"] = len(complete_usage)
    metadata["usage"] = (
        {field: sum(usage[field] for usage in complete_usage) for field in token_fields}
        if count and len(complete_usage) == count else None
    )
    metadata["cost_reported_documents"] = len(costs)
    metadata["reported_cost_usd"] = math.fsum(costs) if costs else None
    metadata["cost_usd"] = metadata["reported_cost_usd"] if count and len(costs) == count else None
    metadata["mean_cost_per_document_usd"] = (
        metadata["cost_usd"] / count if metadata["cost_usd"] is not None else None
    )


def run_baseline(run_dir: Path, model: str | None = None) -> dict:
    # Import lazily so --help does not load model dependencies or read credentials.
    import extract as baseline

    expected, reference = load_fixtures(ROOT / "docs", ROOT / "expected")
    if not os.environ.get("OPENROUTER_API_KEY"):
        raise ValueError("OPENROUTER_API_KEY is not set; configure it locally before running")
    model = model if model is not None else os.environ.get("OPENROUTER_MODEL", baseline.DEFAULT_MODEL)
    if not model.strip():
        raise ValueError("model must not be empty")
    # A fresh directory prevents stale predictions and accidental paid reruns.
    if run_dir.exists():
        raise ValueError("run directory already exists; choose a new directory for a new paid run")
    documents = sorted(
        path for path in (ROOT / "docs").iterdir()
        if path.is_file() and path.stem in expected
        and path.suffix.lower() in baseline.SUPPORTED_EXTENSIONS
    )
    provenance_files = [ROOT / "extract.py", ROOT / "credential.py", ROOT / "evaluate.py", ROOT / "run_baseline.py"]
    provenance_files += sorted((ROOT / "expected").glob("*.json")) + documents
    versions = {}
    for package in ("pymupdf", "requests"):
        try:
            versions[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            versions[package] = None
    metadata = {
        "started_at_utc": timestamp(),
        "finished_at_utc": None,
        "model_requested": model,
        "models_reported": [],
        "python_version": platform.python_version(),
        "package_versions": versions,
        "sha256": {
            path.relative_to(ROOT).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in provenance_files
        },
        "evaluation_reference": reference,
        "reference_applied_to_extractor": True,
        "usage": None,
        "cost_usd": None,
        "cost_note": "Source: response usage.cost (USD-denominated OpenRouter credits). "
                     "Run totals require reporting for every scheduled document; "
                     "reported_cost_usd includes only known costs. Failed requests may incur unknown charges.",
        "documents": [
            {"document": path.stem, "status": "not_attempted", "elapsed_seconds": None, "response": None}
            for path in documents
        ],
    }
    run_dir.mkdir(parents=True)
    predictions_dir = run_dir / "predictions"
    predictions_dir.mkdir()
    metadata_path = run_dir / "run.json"
    update_accounting(metadata)
    write_json(metadata_path, metadata)
    for path, record in zip(documents, metadata["documents"]):
        record["status"] = "in_progress"
        record["response"] = {}
        write_json(metadata_path, metadata)
        print(f"Extracting {path.name} with {model}...", flush=True)
        started = perf_counter()
        try:
            prediction = baseline.extract(path, model, metadata=record["response"],
                                          reference_date=reference["reference_date"],
                                          expiring_soon_window_days=reference["expiring_soon_window_days"])
        except (Exception, KeyboardInterrupt) as exc:
            record["status"] = "interrupted" if isinstance(exc, KeyboardInterrupt) else "failed"
            record["error_type"] = type(exc).__name__
            response = getattr(exc, "response", None)
            record["http_status"] = getattr(response, "status_code", None)
            # Exception text and HTTP bodies may contain sensitive material.
            print(f"Stopped at {path.name}: {record['error_type']}; "
                  f"HTTP status={record['http_status']}. No automatic retry.")
            break
        else:
            # Evaluate the final extractor output, including validation-error objects.
            write_json(predictions_dir / f"{path.stem}.json", prediction)
            record["status"] = "returned_output"
        finally:
            record["elapsed_seconds"] = round(perf_counter() - started, 4)
            update_accounting(metadata)
            write_json(metadata_path, metadata)
    metadata["finished_at_utc"] = timestamp()
    write_json(metadata_path, metadata)
    report = evaluate(predictions_dir)
    write_json(run_dir / "evaluation.json", report)
    print_report(report)
    print(f"\nSaved outputs and run evidence in {run_dir}")
    return metadata


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True, help="New directory for this paid run")
    parser.add_argument("--model", help="Defaults to OPENROUTER_MODEL or the unchanged starter default")
    args = parser.parse_args()
    try:
        metadata = run_baseline(args.run_dir, args.model)
    except (OSError, ValueError, ImportError) as exc:
        parser.error(str(exc))
    if any(record["status"] != "returned_output" for record in metadata["documents"]):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
