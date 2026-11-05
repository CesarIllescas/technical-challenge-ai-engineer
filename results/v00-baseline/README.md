# v00: unchanged extraction baseline

## Run identity and provenance

- Original working directory: `outputs/baseline/`.
- Run interval: `2026-11-05T19:28:49.167673+00:00` to
  `2026-11-05T19:29:59.802625+00:00` (UTC).
- Requested model: `deepseek/deepseek-v4.1-flash`; provider-reported model unknown.
- Python: `3.13.5`; installed PyMuPDF: `2.1`; Requests: `2.34.2`.
- Eight of eight documents returned outputs; no recorded operational failures.
- Extraction behavior: original prompt, first PDF page at 100 DPI, original
  request options and parsing, no supplied reference date and no post-processing.
- Evaluation: exact typed values against the supplied labels, reference
  `2026-11-01`, 60-day window. The evaluator does not repair predictions.

The saved report was independently recomputed from the predictions and matched
exactly. Every source/configuration/label/document SHA-256 in [run.json](run.json)
matched the reviewed workspace. The archived JSON files are byte-for-byte copies
of the original saved evidence, not regenerated predictions.

The runner did not capture a Git revision. At review, `extract.py` and `evaluate.py`
were unchanged tracked files at commit
`7009d1a5dffec0ee9c7e619669b36dcfb4c74cf7`; `run_baseline.py` was staged but not
committed. The hashes are the recorded identifiers of the actual files used.
The proposed runner commit preserves that version before further extraction work.

## Measured results

| Field | Correct / total | Accuracy |
|---|---|---|
| `is_credential` | 8/8 | 100.00% |
| `holder_name` | 3/8 | 37.50% |
| `credential_type` | 3/8 | 37.50% |
| `license_number` | 6/8 | 75.00% |
| `issuing_authority` | 2/8 | 25.00% |
| `issue_date` | 7/8 | 87.50% |
| `expiration_date` | 1/8 | 12.50% |
| `expiration_status` | 5/8 | 62.50% |
| **Overall fields** | **35/64** | **54.69%** |
| Schema-valid documents | 1/8 | 12.50% |
| Complete documents | 0/8 | 0.00% |
| Expected-null fields | 7/13 | 53.85% |
| Expected-non-null fields | 28/51 | 54.90% |

Per-document correct fields: `al_01` 5/8, `al_02` 6/8, `al_03` 2/8,
`ny_01` 5/8, `ny_02` 4/8, `tx_01` 5/8, `tx_02` 5/8, and `tx_03` 3/8.
Full mismatches are in [evaluation.json](evaluation.json); returned values are in
[predictions/](predictions/).

## Observed failures

- **Date format:** six credential expiration dates and one issue date were
  returned in slash-separated rather than ISO format. The renewal notice also
  supplied a slash-separated deadline as expiration. All seven schema-invalid
  documents have a date-format error. The one correct expiration-date field is
  the no-expiration license, not the non-credential.
- **Names:** five names include `MD` or `DO`; expected names omit those degrees
  while preserving the personal suffix `JR.`. The model preserved the accent in
  the Texas holder name, so this run does not establish an accent-recognition problem.
- **License number:** `al_02` changed `MD.20417` to `MD-20417`. The other mismatch
  is a license number populated on the non-credential.
- **Type and authority wording:** four credential-type mismatches are case-only;
  the fifth is a populated type on the non-credential. Three authority mismatches
  are case-only; two include extra organizational wording; the sixth is populated
  on the non-credential. These remain errors under the predeclared exact scorer.
- **Non-credential consistency:** the renewal notice was correctly classified as
  `false`, but six other fields were populated. Only `is_credential` and the null
  `issue_date` match. Classification accuracy alone conceals this failure.
- **Expiration status:** both `expiring_soon` examples were returned as `valid`;
  the non-credential also incorrectly returned `valid` rather than null.

`issue_date` accuracy includes six correct nulls and only one of two correct
present dates. `is_credential` has only one negative sample. Neither high score
establishes broad performance. No score normalization or ground-truth changes
were applied after inspecting the output.

## Timing and cost limits

Mean document invocation time was **8.83 seconds**, with a **6.135-second median**
and a **2.24–25.00-second range**. The total run interval was about **70.63 seconds**.
These timings include local work and network/model processing, not model latency
alone. No latency target is specified by the challenge.

Token usage, actual served model, and billed cost were not exposed by the original
extractor. They remain null in the original metadata. Obtain billing evidence
from the corresponding OpenRouter usage interval before reporting a dollar cost
or cost per document; unknown cost does not mean free.

## Recommendation for the next experiment

The observed errors favor a focused contract/prompt and deterministic expiration
iteration before changing models, adding OCR, or increasing resolution. Explicit
date and non-credential rules address demonstrated failures; name and wording
conventions need careful, general instructions rather than document-specific
answers. Measure the effect using the same scorer and fixtures, with no claimed
improvement until a new run is available. This recommendation has not been implemented.
