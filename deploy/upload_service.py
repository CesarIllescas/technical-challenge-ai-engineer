"""Temporary-upload adapter for the existing credential extractor."""

import os
from pathlib import Path
from tempfile import TemporaryDirectory

import pymupdf
import requests

from scripts.extract import DEFAULT_MODEL, SUPPORTED_EXTENSIONS, extract


MAX_UPLOAD_BYTES = 10 * 1024 * 1024


class UploadError(ValueError):
    """An error message suitable for display without provider or document details."""


def extract_upload(filename: str, content: bytes, reference_date: str, window_days: int) -> dict:
    suffix = Path(filename).suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        raise UploadError("Choose a PDF, PNG, JPG, JPEG, or WebP document.")
    if not content:
        raise UploadError("The uploaded file is empty. Choose a document with content.")
    if len(content) > MAX_UPLOAD_BYTES:
        raise UploadError("The uploaded file exceeds the 10 MB limit.")
    if not os.environ.get("OPENROUTER_API_KEY"):
        raise UploadError("The extraction service is not configured. Please contact the host.")
    model = os.environ.get("OPENROUTER_MODEL", DEFAULT_MODEL)
    if not model.strip():
        raise UploadError("The extraction service configuration needs attention. Please contact the host.")

    try:
        with TemporaryDirectory(prefix="credential-upload-") as directory:
            # Never use the supplied filename as a filesystem path.
            path = Path(directory) / f"document{suffix}"
            path.write_bytes(content)
            result = extract(path, model, reference_date=reference_date,
                             expiring_soon_window_days=window_days)
    except requests.Timeout:
        raise UploadError("The extraction request timed out. Please try again.") from None
    except requests.HTTPError as exc:
        status = getattr(exc.response, "status_code", None)
        if status in (401, 403):
            message = "The extraction service could not authenticate. Please contact the host."
        elif status == 402:
            message = "The extraction service has no available credit. Please contact the host."
        elif status == 429:
            message = "The extraction service is busy. Please try again later."
        else:
            message = "The extraction provider could not process the request. Please try again later."
        raise UploadError(message) from None
    except requests.RequestException:
        raise UploadError("The extraction provider could not be reached. Please try again later.") from None
    except (pymupdf.FileDataError, pymupdf.EmptyFileError, ValueError, IndexError, RuntimeError):
        raise UploadError("The document could not be read. Please choose a readable, unencrypted document.") from None

    if not isinstance(result, dict) or "error" in result:
        raise UploadError("The document could not be extracted reliably. Please try a clearer copy.")
    return result
