"""Run the original sample evaluation using the shared runner and temporary outputs."""

import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory

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
    """Perform fresh extractions, then return the same report produced by the CLI."""
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
    except (OSError, ValueError, ImportError):
        raise EvaluationError("The original sample evaluation is unavailable. Please contact the host.") from None
    return {"report": report, "run": metadata}
