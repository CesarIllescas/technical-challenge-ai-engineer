# Experiment results

Each directory preserves one reviewed run. Keep run evidence and predictions
unchanged after archiving; use a new directory for every subsequent run, including
unsuccessful experiments. All scores below use the same eight supplied documents,
strict evaluator, and `2026-11-01` reference date with a 60-day window.

| Run | Change | Requested model | Field accuracy | Schema validity | Complete documents | Cost |
|---|---|---|---|---|---|---|---|
| [v00-baseline](v00-baseline/README.md) | Unchanged starter | `deepseek/deepseek-v4.1-flash` | 35/64 (54.69%) | 1/8 (12.50%) | 0/8 (0%) | Not captured |
| [v01-contract](v01-contract/evaluation.json) | Explicit field contract and supplied expiration reference | `deepseek/deepseek-v4.1-flash` | 62/64 (96.88%) | 8/8 (100%) | 6/8 (75%) | $0.007662025 total; ~$0.000958/document |

The initial run is the baseline, not one of the challenge's two required
improvement iterations. v01 is the first improvement iteration; v02 remains
pending. Add further rows for further runs; do not replace a prior result.
Record before/after numbers and whether each change was retained, even if it
reduced accuracy.

## v01 comparison and findings

**Hypothesis:** the starter's underspecified prompt was responsible for many of
the date-format, field-selection, null-consistency, and naming errors. v01 adds
explicit instructions for the eight fields and supplies the reference date/window
to the model. The model, request options, first-page 100-DPI PDF rendering, image
handling, and JSON parsing are unchanged. There is no local output correction,
expiration calculation, extra model pass, or provider-enforced schema in v01.

The prompt distinguishes document purpose from authenticity/test disclaimers,
requests ISO dates, excludes professional degrees from names, preserves personal
suffixes and identifier punctuation, and requests concise issuers and standard
capitalization while retaining acronyms. Name/type/issuer presentation conventions
are informed by the fixtures, not a state-specific answer map. Only the reference
configuration is read for prompting; per-document expected answers are not supplied.

The model receives `2026-11-01` and 60 days. For otherwise unspecified boundaries,
the prompt interprets expiration before the reference date as expired, the reference
date through day 60 inclusive as expiring soon, and later dates as valid. CLI and
library callers can override the reference, while evaluation fixes it to the
supplied configuration. Local expiration logic remains a later change.

| Metric | v00 | v01 |
|---|---|---|
| `is_credential` | 8/8 (100%) | 8/8 (100%) |
| `holder_name` | 3/8 (37.50%) | 7/8 (87.50%) |
| `credential_type` | 3/8 (37.50%) | 8/8 (100%) |
| `license_number` | 6/8 (75%) | 7/8 (87.50%) |
| `issuing_authority` | 2/8 (25%) | 8/8 (100%) |
| `issue_date` | 7/8 (87.50%) | 8/8 (100%) |
| `expiration_date` | 1/8 (12.50%) | 8/8 (100%) |
| `expiration_status` | 5/8 (62.50%) | 8/8 (100%) |
| **Overall fields** | **35/64 (54.69%)** | **62/64 (96.88%)** |
| Schema-valid documents | 1/8 (12.50%) | 8/8 (100%) |
| Complete documents | 0/8 (0%) | 6/8 (75%) |
| Expected-null fields | 7/13 (53.85%) | 13/13 (100%) |
| Expected-non-null fields | 28/51 (54.90%) | 49/51 (96.08%) |

Overall accuracy increased by **42.19 percentage points**: 27 previously incorrect
fields became correct and no previously correct field became incorrect. Date
formatting, the renewal notice's null fields, both expiring-soon statuses, and
issuer/type wording all match the labels in this run. Retain v01 as the starting
point for the next experiment; this is evidence from one development-set run,
not a guarantee of improvement on unseen documents.

Two errors remain, both in fields that were already incorrect in v00:

- `al_02.license_number`: expected `MD.20417`, returned `MD-20417`. The identifier
  punctuation error persists despite an explicit preservation instruction.
- `tx_03.holder_name`: expected `ROBERT ALAN MITCHELL JR.`, returned
  `ROBERT ALAN MITCHELL JR`. The professional degree is now removed, but the
  personal suffix lost its period. This is a different mismatch within the same
  previously incorrect field, not a new field-accuracy regression.

Do not change labels, loosen the scorer, replace identifier hyphens globally, or
append suffix punctuation blindly to eliminate these errors. Further transcription
changes need document evidence and another measured experiment. Local expiration
logic would improve reproducibility and boundary behavior; this run already has
8/8 correct statuses, so it does not demonstrate a remaining sample-status error.

### v01 run evidence and limits

- Original working directory: `outputs/v01-contract/`.
- Run interval: `2026-11-05T20:16:02.100563+00:00` through
  `2026-11-05T20:17:16.840628+00:00` (UTC). All eight invocations returned outputs,
  all reported finish reasons were `stop`, and all reported the requested model.
- The [saved evaluation](v01-contract/evaluation.json) reproduces exactly from
  [the archived predictions](v01-contract/predictions/). Every source/input hash
  in [run.json](v01-contract/run.json) matched the reviewed workspace. All ten
  archived JSON files are byte-for-byte copies of the original saved files.
- The run did not record a Git revision. At review, HEAD was
  `74f2b5e5c46b7abc41cc382d89cac455a434da8f`, with v01 changes in `extract.py` and
  `run_baseline.py` uncommitted. That HEAD identifies the metadata-capture parent,
  not a v01 code commit. The actual code and fixtures are identified by their saved
  hashes; commit the matching v01 source separately before further code changes.
- Python `3.13.5`, PyMuPDF `2.1`, and Requests `2.34.2` match the baseline environment.
  Mean invocation time was 9.34 seconds (v00: 8.83 seconds), with a 7.33-second
  median and about 74.74 seconds for the whole run. These include local work and
  network/model processing and are not isolated model latency measurements.
- Usage and cost coverage are complete for 8/8 documents: 10,727 prompt tokens,
  11,519 completion tokens, and 22,246 total tokens. Reported completion details
  include 10,922 reasoning tokens, already included in completion tokens; prompt
  details include 1,152 cached tokens, already included in prompt tokens.
- Summing the per-document `usage.cost` values gives **$0.007662025**, or
  **$0.000957753125 per document**. The original run's floating-point JSON values
  are preserved. This is reported inference spend, not an estimate from token
  prices, a total account balance, or a statement of remaining credit. v00 cost
  was not captured, so an exact cost comparison is unavailable.
- OpenRouter routed the eight requests across Alibaba, CoreWeave, DigitalOcean,
  AtlasCloud, Wafer, and Fireworks. Routing was not fixed, and v00 provider details
  are unknown. Together with model variability and a single run per version,
  this limits causal claims about the prompt alone. The results support retaining
  v01 but do not isolate every change's individual contribution.

Reproduce the v01 score offline without overwriting evidence:

```powershell
& .\.venv\Scripts\python.exe -B evaluate.py --predictions results/v01-contract/predictions
```

## Version and commit workflow

1. Before a paid experiment, finish and verify its code change. Commit that change
   yourself so the experiment has a reviewable code version. The assistant will
   propose the commit scope and message; it will not make commits.
2. Run the approved version locally into a fresh `outputs/<run-id>/` directory.
   Never merge outputs from separate paid attempts, and retain incomplete runs.
3. Review the outputs, reproduce their evaluation offline, and compare source/input
   hashes with the intended version. Record the code commit in the run summary
   when known, and explicitly describe any uncommitted changes present during a run.
4. Copy reviewed `run.json`, `evaluation.json`, and `predictions/` into a fresh
   `results/<run-id>/` directory. This challenge uses supplied synthetic fixtures;
   do not apply this publication workflow to real PHI or credential-bearing logs.
5. Add a summary describing the hypothesis, actual configuration, metrics,
   failures, cost evidence, and limitations; update this table. Then commit the
   results yourself, separately from the code change. The Git history of the
   result directory identifies its evidence commit without a self-referential hash.

The baseline predates this workflow: its runner was uncommitted during the run.
Its source/input hashes match the reviewed workspace. Commit the matching runner
and its documentation before the baseline evidence; do not invent a historical
code commit or rerun merely to obtain one.

`outputs/` remains ignored for local working data. `results/` is tracked so the
GitHub submission can preserve measurements for every reviewed version. Preserve
unknown usage and cost as null until actual billing evidence is available; a cost
update should be a documented follow-up, not a rewrite of the original run data.

## Reproduce the baseline score offline

```powershell
& .\.venv\Scripts\python.exe -B evaluate.py --predictions results/v00-baseline/predictions
```

This reads the archived predictions without API requests or overwriting the saved
report. Use the matching evaluator and fixtures recorded by `run.json`; if scoring
rules later change, make a separately labeled re-evaluation instead of rewriting
the original report. For all runs, state that these eight documents are a
development benchmark, not evidence of accuracy on unseen documents.
