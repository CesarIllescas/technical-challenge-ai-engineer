"""Streamlit upload interface. Model calls occur only on an explicit submission."""

import hashlib
import json
import os
import sys
from datetime import date
from pathlib import Path

import streamlit as st

# Streamlit executes this file directly, including when launched outside the repo.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.credential import FIELDS
from scripts.extract import DEFAULT_MODEL, resolve_reference
from deploy.upload_service import UploadError, extract_upload
from deploy.evaluation_service import EvaluationError, evaluate_samples, sample_configuration


def configure_server_key() -> bool:
    """Support environment configuration and root-level Streamlit secrets."""
    if os.environ.get("OPENROUTER_API_KEY"):
        return True
    try:
        key = st.secrets.get("OPENROUTER_API_KEY", "")
    except FileNotFoundError:
        return False
    if isinstance(key, str) and key.strip():
        os.environ["OPENROUTER_API_KEY"] = key
        return True
    return False


def render_upload(configured: bool, reference: str, window: int) -> None:
    with st.container(border=True):
        uploaded = st.file_uploader("Upload a document", type=["pdf", "png", "jpg", "jpeg", "webp"])
        st.caption("Maximum 10 MB. For PDFs, only the first page is processed.")
        with st.expander("Expiration settings"):
            reference_date = st.date_input("Reference date", value=date.fromisoformat(reference),
                                           min_value=date.min, max_value=date.max)
            window_days = st.number_input("Expiring-soon window (days)", min_value=0, value=window, step=1)
        if reference_date is not None:
            st.caption(f"Expiration reference: {reference_date.isoformat()} · Window: {window_days} days")

        content = uploaded.getvalue() if uploaded is not None else b""
        request = (
            uploaded.name if uploaded is not None else None,
            hashlib.sha256(content).hexdigest(),
            reference_date.isoformat() if reference_date is not None else None,
            window_days, os.environ.get("OPENROUTER_MODEL", DEFAULT_MODEL),
        )
        if st.session_state.get("extraction_request") != request:
            st.session_state.pop("extraction_result", None)
            st.session_state["extraction_request"] = request
        submitted = st.button(
            "Extract JSON", type="primary",
            disabled=not configured or uploaded is None or reference_date is None
            or "extraction_result" in st.session_state,
        )

    if submitted:
        with st.spinner("Reading the document…"):
            try:
                result = extract_upload(uploaded.name, content, reference_date.isoformat(), window_days)
            except UploadError as exc:
                st.error(str(exc))
            except Exception:
                # Do not expose tracebacks, response bodies, or document contents.
                st.error("The document could not be processed. Please try again or contact the host.")
            else:
                st.session_state["extraction_result"] = result
                st.rerun()

    if "extraction_result" in st.session_state:
        result = st.session_state["extraction_result"]
        st.subheader("Extracted JSON")
        if result["is_credential"] is False:
            st.info("This document is not a license or certification.")
        st.json(result)
        st.download_button("Download JSON", json.dumps(result, indent=2, ensure_ascii=False).encode("utf-8"),
                           file_name="credential.json", mime="application/json", key="download_upload")
    elif uploaded is None:
        st.info("Choose a document, then select Extract JSON.")
    st.caption("Documents are sent to the extraction provider for processing. "
               "Local temporary files are removed after each attempt.")


def render_sample_evaluation(configured: bool) -> None:
    st.subheader("Test with the original documents")
    try:
        configuration = sample_configuration()
    except EvaluationError as exc:
        st.error(str(exc))
        return
    count = configuration["document_count"]
    reference = configuration["reference"]
    st.write(f"Run fresh extractions on all {count} original sample documents and compare "
             "the results with their expected JSON.")
    st.caption(f"This action makes up to {count} paid requests. Evaluation always uses "
               f"{reference['reference_date']} and a {reference['expiring_soon_window_days']}-day "
               "window, independently of the upload settings.")
    model = os.environ.get("OPENROUTER_MODEL", DEFAULT_MODEL)
    if st.session_state.get("evaluation_model") != model:
        st.session_state.pop("sample_evaluation", None)
        st.session_state["evaluation_model"] = model
    if st.button("Evaluate original documents", key="evaluate_samples", disabled=not configured):
        st.session_state.pop("sample_evaluation", None)
        with st.spinner(f"Evaluating {count} documents…"):
            try:
                st.session_state["sample_evaluation"] = evaluate_samples()
            except EvaluationError as exc:
                st.error(str(exc))
            except Exception:
                st.error("The sample evaluation could not be completed. Please try again or contact the host.")
    if "sample_evaluation" not in st.session_state:
        return
    result = st.session_state["sample_evaluation"]
    report, run = result["report"], result["run"]
    st.subheader("Accuracy results")
    for column, label, metric in zip(
        st.columns(3), ("Field accuracy", "Complete documents", "Schema validity"),
        (report["overall"], report["complete_documents"], report["schema_validity"]),
    ):
        column.metric(label, f"{metric['accuracy']:.2%}", help=f"{metric['correct']} / {metric['total']}")
    st.caption(f"{report['overall']['correct']} / {report['overall']['total']} fields match exactly. "
               "Missing or failed outputs remain in the denominator.")
    st.dataframe([
        {"Field": field, "Correct": metric["correct"], "Total": metric["total"],
         "Accuracy": f"{metric['accuracy']:.2%}"}
        for field, metric in report["per_field"].items()
    ], hide_index=True)
    statuses = {row["document"]: row["status"] for row in run["documents"]}
    st.dataframe([
        {"Document": row["document"], "Correct fields": row["correct_fields"], "Total fields": len(FIELDS),
         "Schema valid": row["schema_valid"], "Complete match": row["exact_match"],
         "Run status": statuses[row["document"]]}
        for row in report["documents"]
    ], hide_index=True)
    completed = sum(row["status"] == "returned_output" for row in run["documents"])
    if completed != count:
        st.warning(f"Only {completed}/{count} documents returned outputs. "
                   "Failed and unattempted documents are included in the score.")
    if run["cost_usd"] is not None:
        st.caption(f"Reported run cost: ${run['cost_usd']:.6f}.")
    elif run["reported_cost_usd"] is not None:
        st.caption(f"Reported cost so far: ${run['reported_cost_usd']:.6f}. Total cost is unavailable.")
    else:
        st.caption("Cost was not reported by the provider.")
    mismatches = {row["document"]: row["mismatches"] for row in report["documents"] if row["mismatches"]}
    if mismatches:
        with st.expander("Field mismatches"):
            st.json(mismatches)
    st.subheader("Inspect and download the evaluation data")
    st.caption("These are the saved outputs used to calculate this run's metrics. "
               "Viewing or downloading them does not run extraction again.")
    st.download_button("Download all outputs (ZIP)", result["archive"],
                       file_name="sample-evaluation.zip", mime="application/zip", key="download_evaluation")
    st.download_button("Download accuracy report (JSON)",
                       json.dumps(report, indent=2, ensure_ascii=False).encode("utf-8"),
                       file_name="evaluation.json", mime="application/json", key="download_report")
    selected = st.selectbox("Document", [row["document"] for row in report["documents"]],
                            key="evaluation_document")
    st.markdown("**Generated JSON**")
    content = result["prediction_files"].get(selected)
    if content is None:
        st.info(f"No output was generated for this document (status: {statuses[selected]}).")
    else:
        try:
            st.json(json.loads(content))
        except (ValueError, UnicodeDecodeError):
            st.warning("The saved output is not valid JSON.")
            st.code(content.decode("utf-8", errors="replace"), language="text")
        st.download_button("Download document JSON", content, file_name=f"{selected}.json",
                           mime="application/json", key="download_document")
    with st.expander("Expected JSON"):
        st.json(result["expected"][selected])


def main() -> None:
    st.set_page_config(page_title="Credential extractor", page_icon="📄", layout="centered")
    st.title("Credential extractor")
    st.write("Upload a medical license or certification to view its structured details.")
    try:
        reference, window = resolve_reference()
    except (OSError, ValueError, KeyError):
        st.error("The expiration settings are unavailable. Please contact the host.")
        return
    configured = configure_server_key()
    if not configured:
        st.warning("Extraction is unavailable until the server API key is configured.")
    upload_tab, evaluation_tab = st.tabs(["Upload document", "Evaluate samples"])
    with upload_tab:
        render_upload(configured, reference, window)
    with evaluation_tab:
        render_sample_evaluation(configured)


if __name__ == "__main__":
    main()
