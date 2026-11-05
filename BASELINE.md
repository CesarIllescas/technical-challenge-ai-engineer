# Baseline runs and response accounting

The runner calls the current extractor once per document, saves the returned
credential JSON and separate response metadata, and runs the offline evaluator.
The current v01 experiment uses explicit extraction instructions and
passes the evaluation reference date/window into the prompt. It preserves the
first-page 100-DPI rendering, request options, model selection, and JSON parsing.
Source hashes and experiment summaries identify each extraction version.

**Running this command makes paid OpenRouter requests.** The user runs it locally;
no real requests or model results were produced while preparing this stage.

The subsequent user-run baseline has now been reviewed and archived in
[results/v00-baseline/](results/v00-baseline/README.md). For future version and
commit tracking, follow [the results workflow](results/README.md). Keep that
baseline unchanged when preparing later improvement iterations.

## Before the paid run

1. Check the available OpenRouter credit and the selected model's image support,
   availability, and price in OpenRouter. These have not been verified here. The
   supplied key has a $5 limit; leave credit for later iterations and reviewer use.
2. Use the existing virtual environment with the starter's dependencies installed.
   The runner adds no dependencies. Its `--help` command is offline.
3. Set `OPENROUTER_API_KEY` in your local shell or deployment secret store. The
   starter and runner do not load `.env` automatically. Never paste the key into
   chat, source files, command arguments, or committed results.

In PowerShell, if the key is not already configured, enter it through a hidden
prompt rather than a literal command that would enter shell history:

```powershell
$baselineApiKey = Read-Host 'OpenRouter API key' -AsSecureString
$env:OPENROUTER_API_KEY = [System.Net.NetworkCredential]::new('', $baselineApiKey).Password
Remove-Variable baselineApiKey
```

## Run once

From the repository root in PowerShell:

```powershell
& .\.venv\Scripts\python.exe -B -m scripts.run_baseline --run-dir outputs/v01-contract
```

The model defaults to `OPENROUTER_MODEL` when set, otherwise the starter default
`deepseek/deepseek-v4.1-flash`. The runner prints the requested model and records
it. To explicitly request the original default despite an environment override:

```powershell
& .\.venv\Scripts\python.exe -B -m scripts.run_baseline --run-dir outputs/v01-contract --model deepseek/deepseek-v4.1-flash
```

Choose **one** run command. There are eight document invocations, each with at
most one model request; local failures may occur before a request. There are no
automatic retries or model substitutions. A transport/provider error stops the
remaining invocations. Do not blindly rerun on an error: inspect the saved status
and the provider's error/usage information first. If the default model cannot run,
record that blocker before deliberately choosing a substitute baseline.

The run directory must not already exist, including an empty directory. A new
attempt requires a different directory and may incur additional charges. Keep
failed-run evidence rather than mixing fresh outputs into a prior run.

## Saved evidence

Inside the chosen run directory (for example `outputs/v01-contract/`):

- `predictions/<document>.json`: values returned by the extractor,
  including its error object if a model response could not be parsed.
- `run.json`: requested model, UTC timestamps, local package/Python versions,
  source/input SHA-256 hashes, document outcomes, elapsed time per invocation,
  per-document response accounting, and run accounting totals.
- `evaluation.json`: per-field accuracy, overall accuracy, schema validity,
  complete-document accuracy, null diagnostics, and document-level mismatches.

Timing includes local rendering, network/model time, and prediction-file writing;
it is not isolated model latency. The runner records document status before each
invocation and saves progress after it. An interrupted request may still have
incurred a charge. A forced process exit can leave an `in_progress` record and no
final evaluation; existing saved predictions can still be scored offline.

Each document's `response` records only selected response fields: generation ID,
reported model, provider when present, creation time, normalized/native finish
reasons, and the `usage` object. Usage includes prompt/completion/total tokens and,
when present, reasoning/cache details, BYOK indication, and cost breakdowns. No
prompt, image, assistant content, reasoning text, or authentication headers are
included in this metadata. Metadata is captured before content parsing, so it
survives invalid JSON and content-access failures in the runner.

[OpenRouter usage accounting](https://openrouter.ai/docs/cookbook/administration/usage-accounting)
documents automatic usage reporting on non-streaming chat responses; no extra
request parameters or lookup requests are needed. `usage.cost` is the account
charge in [USD-denominated credits](https://openrouter.ai/support); it is the source
for dollar totals, rather than upstream inference cost or a token-price estimate.

Run accounting fields have explicit coverage:

- `models_reported`: distinct model names actually reported by captured responses,
  without substituting the requested model when metadata is absent.
- `usage_reported_documents`: documents reporting all three nonnegative integer
  token counts. `usage` contains their totals only when all scheduled documents
  report them; otherwise it is null. Detailed usage remains per document.
- `cost_reported_documents`: documents reporting a finite nonnegative numeric cost.
  `reported_cost_usd` sums only these known charges, or is null when none are known.
- `cost_usd` and `mean_cost_per_document_usd`: complete totals only when every
  scheduled document reports cost. A zero reported cost is valid; an absent cost
  stays unknown. Failed or unattempted requests can leave incomplete accounting,
  and failed requests can incur charges not represented in their response.

The original `v00-baseline` predates metadata capture and remains unchanged. Its
missing metadata cannot be reconstructed from the saved predictions. Any later
billing evidence should be recorded separately with its source; do not rerun or
replace `v00` to manufacture historical cost data. Future evaluations can use this
capture without a separate paid accounting experiment.

For the extraction CLI alone, metadata capture is optional and stored separately:

```powershell
& .\.venv\Scripts\python.exe -B -m scripts.extract docs/tx_01.pdf --out-dir outputs/metadata-check/predictions --metadata-dir outputs/metadata-check/metadata
```

This example makes one paid request if the user runs it; it has not been executed
during implementation. `extract(path, model)` still returns only the credential
object; callers can pass an empty `metadata` dictionary to collect the accounting
fields separately. The dictionary is cleared at the start of each extraction.
`call_model` now returns the full response object internally, rather than discarding
everything except content. Raw response bodies are not written to metadata files.

Operational exceptions save only their class and HTTP status, not exception
messages, headers, or HTTP bodies. Saved original outputs can contain document
data and raw model text; `outputs/` is already ignored by Git. Review outputs and
reports before sharing or committing them. Do not share credentials or dashboard
screenshots containing credentials.

The runner exits 0 when every invocation returned an output, even if accuracy is
poor; invalid model output is an extraction finding. It exits 1 after an
operational failure/interruption, and 2 for setup errors. Failed and unattempted
documents still count in all evaluation denominators; distinguish an incomplete
operational run from a completed extraction benchmark.

## After the run

Tell the assistant the run directory and whether it finished. The saved files in
the shared workspace are sufficient to analyze field errors; no key is needed.
Captured response accounting is available in `run.json`; any separate billing
evidence can be supplied without credentials. The original baseline has already
been scored and reviewed. The metadata addition has only been verified with
mocked responses; its live response shape will be confirmed on a future user-run
request. It is an instrumentation change, not a measured extraction improvement.

To rescore already saved outputs without making API requests:

```powershell
& .\.venv\Scripts\python.exe -B -m scripts.evaluate --predictions outputs/baseline/predictions --report outputs/baseline/evaluation.json
```

After review, the genuine evaluation and run metadata can be copied to a dedicated
`results/` directory for the challenge submission. Synthetic test results must not
be presented as a model baseline.
