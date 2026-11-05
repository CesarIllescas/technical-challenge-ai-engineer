# Evaluation results

This submission preserves three selected milestones: the starter baseline, the
first improvement, and the final v02 system. All use the eight supplied documents,
the same exact field scorer, reference date `2026-11-01`, and a 60-day window.
All three requested `deepseek/deepseek-v4.1-flash`.

| Version | Main change | Field accuracy | Schema-valid documents | Complete documents | Reported run cost |
|---|---|---|---|---|---|
| [v00 baseline](v00-baseline/README.md) | Original starter | 35/64 (54.69%) | 1/8 (12.50%) | 0/8 (0%) | Not captured |
| [v01 contract](v01-contract/evaluation.json) | Explicit extraction instructions and reference configuration | 62/64 (96.88%) | 8/8 (100%) | 6/8 (75%) | $0.007662025 |
| [v02 image quality](v02-image-quality/evaluation.json) | Local rules, 200-DPI rendering, and conservative orientation correction | 64/64 (100%) | 8/8 (100%) | 8/8 (100%) | $0.01379920 |

v01 improved field accuracy by 42.19 percentage points over v00. The selected final
v02 run improved it by another 3.13 percentage points over v01. These are selected
individual development-set runs, not averages or held-out performance estimates.
Intermediate prompt revisions, model comparisons, and unsuccessful v02 attempts
were explored. Their raw evidence is retained locally under ignored `outputs/`,
including `outputs/development-archives/`; only the final v02 result is published
here. The final result does not imply that every intermediate change improved
accuracy or that this score was consistently reproduced.

## Accuracy per field

| Field | v00 correct | v01 correct | v02 correct |
|---|---|---|---|
| `is_credential` | 8/8 | 8/8 | 8/8 |
| `holder_name` | 3/8 | 7/8 | 8/8 |
| `credential_type` | 3/8 | 8/8 | 8/8 |
| `license_number` | 6/8 | 7/8 | 8/8 |
| `issuing_authority` | 2/8 | 8/8 | 8/8 |
| `issue_date` | 7/8 | 8/8 | 8/8 |
| `expiration_date` | 1/8 | 8/8 | 8/8 |
| `expiration_status` | 5/8 | 8/8 | 8/8 |

The final run has 13/13 correct expected-null values and 51/51 correct expected
non-null values. Missing fields and failed predictions remain in the evaluator's
denominators. Neither the labels nor string-comparison rules were changed to
obtain the final score.

## Failure analysis and changes

The starter commonly returned slash-separated dates, kept professional degrees
in holder names, varied type/authority wording, populated credential fields on a
correctly classified renewal notice, and missed both expiring-soon examples.
Its prompt did not specify the detailed output contract or expiration reference.

v01 added explicit field instructions, null behavior, ISO dates, name and issuer
selection guidance, identifier preservation, and the configurable reference/window.
It retained the original model and first-page 100-DPI rendering. The remaining
errors in the selected v01 run were a period changed to a hyphen in a license
number and a missing period on a personal suffix.

Final v02 retains the v01 prompt and adds:

- Local expiration calculation using the configured reference and window. Dates
  before the reference are expired; day 0 through the window's final day inclusive
  are expiring soon; later dates are valid. A genuine null expiration yields
  `no_expiration`. These boundaries are an explicit implementation interpretation.
- Conservative date normalization, non-credential null consistency, and final
  schema validation. Ambiguous or invalid dates produce explicit failures rather
  than invented values. Shared schema checks keep evaluation behavior consistent.
- First-page PDF rendering at 200 DPI, preserving more detail from scans that
  contain roughly 300-DPI source images.
- Quarter-turn orientation correction only when PDF text geometry strongly
  supports it, accounting for PDF rotation metadata. Sparse, missing, unreadable,
  or conflicting text keeps the existing orientation. Image-only PDFs receive
  higher resolution without inferred orientation; image inputs pass through.

The rendering rules use no filenames, document-specific answers, authority
lookups, or identifier replacements. Their tests include independently generated
PDFs at all four orientations, rotated metadata, sparse/mixed text, image
passthrough, and actual render dimensions. Rotation metadata is saved per document.
The final sample run has no local changed fields: the model's parsed values were
already correct, and the deterministic rules produced the same values.

## Final v02 provenance and accounting

The selected submission directory is `results/v02-image-quality/`. Its original
working-run directory was `outputs/v03-image-quality/`; the submission label
consolidates the final improvements into v02. The ten archived JSON files are
byte-for-byte copies of that run, without rewriting its metadata or predictions.

- Source matches commit `c337a0a8f98e939d068b94e84dbd8d6d4d455ece`. All source,
  configuration, label, and document hashes saved in [run.json](v02-image-quality/run.json)
  matched the reviewed workspace.
- UTC interval: `2026-11-05T21:27:59.910874+00:00` through
  `2026-11-05T21:28:55.808071+00:00`. All eight documents returned outputs; mean
  invocation time was 6.99 seconds, including local work and network/model time.
- Requested and reported model: `deepseek/deepseek-v4.1-flash`. Providers were
  Cohere, DeepInfra, CoreWeave, Together, and Wafer. Routing was not fixed.
- Complete accounting for 8/8 documents: 13,961 prompt tokens, 12,519 completion
  tokens, and 26,480 total tokens.
- Summed response `usage.cost`: **$0.01379920 total**, or **$0.00172490 per document**.
  This is reported inference cost, not total account spend or remaining credit.
  v00 cost was not captured and remains unknown. Different provider routing and
  token/cache behavior limit causal attribution of cost changes to rendering.

## Reproduction and limits

Re-score the final saved predictions without API requests or overwriting evidence:

```powershell
& .\.venv\Scripts\python.exe -B -m scripts.evaluate --predictions results/v02-image-quality/predictions
```

The saved report reproduces exactly: 64/64 fields, 8/8 valid schemas, and 8/8 complete
documents. A new model run is a separate experiment and requires a fresh output
directory and paid calls performed by the user.

The eight samples were repeatedly used during development. A selected 100% run
on them does not establish repeatability or generalization to unseen documents.
Resolution and orientation changed together, and provider/model variability was
not eliminated, so their individual contributions are not isolated. Repeat the
frozen configuration and use independent documents, when available, before making
broader accuracy claims. Preserve the scorer and labels, and document issuer-name
representation ambiguities rather than hiding them with fuzzy scoring.

The user makes all commits and paid API calls. BASELINE.md and EVALUATION.md are
being kept for the final documentation pass rather than this results commit.
