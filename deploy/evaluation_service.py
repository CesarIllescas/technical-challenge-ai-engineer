"""Run the original sample evaluation using the shared runner and temporary outputs."""

import json
import os
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZIP_DEFLATED, ZipFile

from scripts.extract import DEFAULT_MODEL
from scripts.evaluate import ROOT, load_fixtures
from scripts.run_baseline import run_baseline


class EvaluationError(ValueError):
    """A controlled evaluation setup error for the interface."""


def sample_configuration() -> dict:
    try:
        expected, reference = load_fixtures(ROOT / "docs", ROOT / "expected")
    except (OSError, ValueError):
        raise EvaluationError("The original sample evaluation is unavailable. Please contact the host.") from None
    return {"document_count": len(expected), "reference": reference}


def evaluate_samples() -> dict:
    """Return fresh CLI evaluation results and the exact artifacts used to score them."""
    if not os.environ.get("OPENROUTER_API_KEY"):
        raise EvaluationError("The extraction service is not configured. Please contact the host.")
    model = os.environ.get("OPENROUTER_MODEL", DEFAULT_MODEL)
    if not model.strip():
        raise EvaluationError("The extraction service configuration needs attention. Please contact the host.")
    try:
        with TemporaryDirectory(prefix="credential-evaluation-") as directory:
            run_dir = Path(directory) / "run"
            metadata = run_baseline(run_dir, model, verbose=False)
            report = json.loads((run_dir / "evaluation.json").read_text(encoding="utf-8"))
            prediction_files = {
                path.stem: path.read_bytes() for path in sorted((run_dir / "predictions").glob("*.json"))
            }
            expected, _ = load_fixtures(ROOT / "docs", ROOT / "expected")
            buffer = BytesIO()
            with ZipFile(buffer, "w", compression=ZIP_DEFLATED) as archive:
                for stem, content in prediction_files.items():
                    archive.writestr(f"predictions/{stem}.json", content)
                for filename in ["_reference.json"] + [f"{stem}.json" for stem in expected]:
                    archive.writestr(f"expected/{filename}", (ROOT / "expected" / filename).read_bytes())
                for filename in ("evaluation.json", "run.json"):
                    archive.writestr(filename, (run_dir / filename).read_bytes())
                archive.writestr("README.txt", (
                    "These are the exact saved outputs used by this evaluation.\n"
                    "Missing predictions are intentionally absent and count as failures.\n"
                    "From the repository root, after extracting to sample-evaluation/, run:\n"
                    "python -m scripts.evaluate --predictions sample-evaluation/predictions "
                    "--expected sample-evaluation/expected\n"
                    "The evaluator uses the repository's original docs/ for document pairing.\n"
                    "No API calls are needed to re-score these outputs.\n"
                ))
            archive_bytes = buffer.getvalue()
    except (OSError, ValueError, ImportError):
        raise EvaluationError("The original sample evaluation is unavailable. Please contact the host.") from None
    return {
        "report": report,
        "run": metadata,
        "prediction_files": prediction_files,
        "expected": expected,
        "archive": archive_bytes,
    }
