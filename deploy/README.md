# Upload interface

The application is deployed on Streamlit Community Cloud:
[Open the credential extractor](https://technical-challenge-ai-engineer-89lj62eh39mpw3v9jnivwb.streamlit.app/).
The instructions below also support running it locally.

The Streamlit interface uses the same `scripts.extract.extract` function as the CLI and
evaluation runner. It accepts PDF, PNG, JPG, JPEG, and WebP, processes a document
only when **Extract JSON** is selected, and displays the eight-field JSON result.
Select **Download JSON** to save that result as `credential.json`.
Non-credentials display their normal `false`/null result. Failed requests and
unreadable documents display a controlled error rather than a provider response.

## Run locally

From the repository root, install the requirements into your virtual environment:

```powershell
& .\.venv\Scripts\python.exe -m pip install -r deploy/requirements.txt
```

Configure `OPENROUTER_API_KEY` in your local shell without putting the literal key
in source, chat, or command history. If it is not already configured:

```powershell
$interfaceApiKey = Read-Host 'OpenRouter API key' -AsSecureString
$env:OPENROUTER_API_KEY = [System.Net.NetworkCredential]::new('', $interfaceApiKey).Password
Remove-Variable interfaceApiKey
```

Then start the interface:

```powershell
& .\.venv\Scripts\python.exe -m streamlit run deploy/app.py
```

Open the local URL printed by Streamlit, normally `http://localhost:8501`.
Starting the app or uploading a document makes no model request. Selecting
**Extract JSON** makes one paid request. Successful results remain in that browser
session, and ordinary reruns do not repeat the call. Changing the document,
expiration settings, or server model clears the old result. The button is disabled
when a successful result already exists for the same inputs.

The default model is the final evaluated `deepseek/deepseek-v4.1-flash`.
`OPENROUTER_MODEL` can override it on the server; visitors cannot change models or
supply credentials through the page. Reference date/window default to the supplied
`expected/_reference.json` and are editable in **Expiration settings**. PDF
processing retains the evaluated first-page, 200-DPI orientation-aware behavior.

## Evaluate the original documents

Select **Evaluate samples**, then **Evaluate original documents**. This runs fresh
extraction on all eight supplied PDFs and compares predictions with their expected
JSON using the same runner and exact scorer as the CLI. It can make up to eight
paid requests per button click. The interface shows field accuracy, complete
documents, schema validity, a table per field, document outcomes, mismatches, and
reported cost when available. This is a current run, not the archived 100% score.

Evaluation always uses `expected/_reference.json`, regardless of the upload date
settings. Failed and unattempted documents remain in the denominator. The runner
stops on an operational failure without retrying; partial accuracy is still shown
with a warning. Model/validation error outputs are scored as failures.

After evaluation, select a document to inspect its generated JSON and expand
**Expected JSON** to compare it with the supplied label. Download an individual
prediction, the accuracy report, or **all outputs (ZIP)**. Missing predictions are
identified explicitly; saved error outputs remain visible and downloadable.

The ZIP contains the exact prediction files used for scoring, expected labels,
reference configuration, `evaluation.json`, `run.json`, and re-scoring instructions.
Extract it into `sample-evaluation/` under the repository root, then independently
recompute the report without making model requests:

```powershell
& .\.venv\Scripts\python.exe -m scripts.evaluate --predictions sample-evaluation/predictions --expected sample-evaluation/expected
```

Temporary files are removed after evaluation. Their contents and the report stay
in the current browser session for inspection and download. Viewing, selecting,
or downloading results does not repeat model calls. Changing the server model
clears the previous evaluation.
Selecting the evaluation button again intentionally starts another paid run. The
interface does not overwrite or publish archived results.

## Deployment configuration and secrets

The interface also supports a root-level `OPENROUTER_API_KEY` in Streamlit secrets.
For local secrets, `.streamlit/secrets.toml` is ignored by Git. On a host supporting
Streamlit secrets, configure it in that platform's secret store. Environment
variables are also supported. No secret file is created by this implementation.
See [Streamlit secrets management](https://docs.streamlit.io/develop/concepts/connections/secrets-management).

Entry point: `deploy/app.py`. Start from the repository root with
`streamlit run deploy/app.py`. Install `deploy/requirements.txt`, which includes
the core requirements. Keep the `scripts/` package, `docs/`, and `expected/`
available. `.streamlit/config.toml` and optional `.streamlit/secrets.toml` stay at
the repository root, where Streamlit discovers them. The live deployment is
hosted on Streamlit Community Cloud at the URL above.

## Upload handling and limits

The interface applies a 10 MB upload limit, a demo implementation choice rather
than a challenge requirement. A temporary server-side file with a generated
directory and fixed filename is passed to the existing extractor. The original
upload name is never used as a filesystem path. The temporary directory is removed
after success or failure. No uploaded documents or live evaluation outputs are written to the repository,
cached globally, or logged by the interface; Streamlit keeps uploads/results in
the active session, and the external provider processes the document.

Upload failures show controlled error messages. Sample evaluation exports include
the actual saved extractor outputs, including error objects and invalid model
content when present, so failures can be inspected. Authentication headers,
provider HTTP error bodies, and model reasoning are not included. This is a
challenge demonstration, not a production PHI service or a
claim about provider retention. Proposed production controls are described in
[the technical report](../REPORT.md).

## Verification

```powershell
& .\.venv\Scripts\python.exe -B -m unittest discover -s tests -v
```

Upload handling, UI behavior, and export re-scoring are checked with temporary
files and mocked extraction. Export checks include a deliberately incorrect
prediction and confirm that the downloaded files reproduce its non-perfect score.
These checks make no paid model requests and do not change the
archived evaluation results. Live extraction requires a configured server key;
the offline checks do not establish the deployed provider's current availability.

Local verification used Streamlit 1.67.0, including the AppTest UI harness, server
startup, and health endpoint. This verification is separate from the published
deployment; no live extraction request was made during documentation updates.
