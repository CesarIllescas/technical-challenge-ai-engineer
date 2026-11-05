"""Baseline credential extractor.

Sends a license or certification document (PDF or image) to a vision model on
OpenRouter and prints the extracted fields as JSON.

This is a deliberately simple starting point. It is expected to score around
60% field accuracy on the sample documents.

Usage:
    python extract.py docs/tx_01.pdf
    python extract.py docs/ --out-dir outputs/
"""

import argparse
import base64
import json
import os
import sys
from pathlib import Path

import pymupdf
import requests

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = "deepseek/deepseek-v4.1-flash"
SUPPORTED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".webp"}

PROMPT = """Extract the following information from this medical license document
and return it as JSON:

- is_credential
- holder_name
- credential_type
- license_number
- issuing_authority
- issue_date
- expiration_date
- expiration_status (expired, expiring_soon, valid or no_expiration)
"""


def load_image(path: Path) -> tuple[str, str]:
    """Return (mime_type, base64_data) for the document. PDFs use the first page only."""
    if path.suffix.lower() == ".pdf":
        with pymupdf.open(path) as pdf:
            pixmap = pdf[0].get_pixmap(dpi=100)
            return "image/png", base64.b64encode(pixmap.tobytes("png")).decode()

    mime = "image/jpeg" if path.suffix.lower() in {".jpg", ".jpeg"} else f"image/{path.suffix.lower()[1:]}"
    return mime, base64.b64encode(path.read_bytes()).decode()


def call_model(mime: str, image_b64: str, model: str) -> dict:
    """Return the response body so extraction can retain usage and request metadata."""
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        sys.exit("OPENROUTER_API_KEY is not set")

    response = requests.post(
        OPENROUTER_URL,
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "model": model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": PROMPT},
                        {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{image_b64}"}},
                    ],
                }
            ],
        },
        timeout=120,
    )
    response.raise_for_status()
    return response.json()


def response_metadata(response: dict) -> dict:
    """Select response accounting fields without retaining message content or headers."""
    choices = response.get("choices") or []
    choice = choices[0] if choices and isinstance(choices[0], dict) else {}
    return {
        "response_id": response.get("id"),
        "model": response.get("model"),
        "provider": response.get("provider"),
        "created": response.get("created"),
        "finish_reason": choice.get("finish_reason"),
        "native_finish_reason": choice.get("native_finish_reason"),
        "usage": response.get("usage") if isinstance(response.get("usage"), dict) else None,
    }


def parse_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`").removeprefix("json").strip()
    return json.loads(text)


def extract(path: Path, model: str, *, metadata: dict | None = None) -> dict:
    """Return credential JSON; optionally populate a separate response-metadata dict."""
    if metadata is not None:
        metadata.clear()
    mime, image_b64 = load_image(path)
    response = call_model(mime, image_b64, model)
    if metadata is not None:
        # Capture accounting before parsing, even when content is malformed.
        metadata.update(response_metadata(response))
    raw = response["choices"][0]["message"]["content"]
    try:
        return parse_json(raw)
    except json.JSONDecodeError:
        return {"error": "invalid JSON from model", "raw": raw}


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract credential fields from a document.")
    parser.add_argument("path", type=Path, help="A document or a folder of documents")
    parser.add_argument("--out-dir", type=Path, help="Write one <document>.json per input here")
    parser.add_argument("--metadata-dir", type=Path, help="Optionally save response metadata separately")
    parser.add_argument("--model", default=os.environ.get("OPENROUTER_MODEL", DEFAULT_MODEL))
    args = parser.parse_args()
    if args.metadata_dir and args.out_dir and args.metadata_dir.resolve() == args.out_dir.resolve():
        parser.error("--metadata-dir must differ from --out-dir")

    if args.path.is_dir():
        files = sorted(p for p in args.path.iterdir() if p.suffix.lower() in SUPPORTED_EXTENSIONS)
    else:
        files = [args.path]

    if args.out_dir:
        args.out_dir.mkdir(parents=True, exist_ok=True)
    if args.metadata_dir:
        args.metadata_dir.mkdir(parents=True, exist_ok=True)

    for file in files:
        metadata = {} if args.metadata_dir else None
        result = extract(file, args.model, metadata=metadata)
        if args.metadata_dir:
            (args.metadata_dir / f"{file.stem}.json").write_text(
                json.dumps(metadata, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
            )
        output = json.dumps(result, indent=2, ensure_ascii=False)
        if args.out_dir:
            (args.out_dir / f"{file.stem}.json").write_text(output + "\n")
            print(f"{file.name} -> {args.out_dir / (file.stem + '.json')}")
        else:
            print(f"# {file.name}\n{output}")


if __name__ == "__main__":
    main()
