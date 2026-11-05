# Offline evaluation contract

This evaluator implements the challenge's required per-field accuracy report.
It reads saved predictions only: it does not import `extract.py`, call a model,
access API credentials, or change the supplied documents and labels.

## Usage

With existing extractor outputs saved as `<document>.json` in a directory:

```bash
python -m scripts.evaluate --predictions results/v02-image-quality/predictions
```

This command only scores files. It does not generate predictions. Creating a
baseline with the original extractor requires model calls; see [BASELINE.md](BASELINE.md)
for the user-run procedure and saved run evidence. The original user-run baseline
is preserved in [results/v00-baseline/](results/v00-baseline/README.md); selected
v01 and final v02 results are summarized in [results/README.md](results/README.md).
The deployed app uses this same evaluator for fresh sample evaluations; see
[the interface documentation](deploy/README.md).

The document and expected-output directories default to `docs/` and `expected/`
at the repository root, independently of the script location. Run module commands from the repository root. Override them with
`--docs` and `--expected` if needed. The prediction directory must already exist.
The optional report's parent directory is created automatically. Keep reports
outside the prediction directory so they are not listed as unrelated predictions.

## Fixture and reference rules

- Every supported document must have exactly one expected JSON with the same
  filename stem, and every label must have a document. Duplicate document stems,
  missing pairs, empty fixture sets, invalid label schemas, or invalid reference
  configuration stop evaluation rather than changing the scoring population.
- Supported document suffixes match the starter: PDF, PNG, JPG, JPEG, and WebP.
  Evaluation identifies these files by suffix; it does not open or render them.
- `expected/_reference.json` is configuration, not a document label. Its
  `2026-11-01` reference date and 60-day window are included in the report.
- Status predictions are compared with the supplied labels as saved. Evaluation
  never recomputes or repairs them, which would otherwise conceal starter errors.
  Expiration-day boundary choices belong to the later expiration implementation.

## Scoring policy

The following are evaluator decisions for making the required measurement precise;
the challenge does not specify a detailed scoring algorithm or a passing score.

- Score each of the eight required fields independently against its expected JSON
  value, with exact type and value equality. JSON formatting and object-key order
  do not matter. Strings are not trimmed, case-folded, accent-folded, or otherwise
  normalized. License numbers stay strings. Boolean `true` is not numeric `1`.
- A missing key, an empty string, and the string `"null"` do not equal JSON `null`.
- Missing files, unreadable or invalid JSON, and non-object outputs receive zero
  field credit for that document. All documents remain in every field denominator.
  Error objects also receive no credit for missing required fields.
- JSON must be UTF-8. Duplicate keys and non-JSON constants such as `NaN` are
  rejected. Markdown-fenced files are not repaired: the starter's saved output is
  already JSON, and parsing behavior belongs to the extractor.
- Schema checks require exactly the eight keys, a boolean `is_credential`, strings
  or nulls for the remaining fields, valid calendar dates in `YYYY-MM-DD` format,
  and the documented expiration-status enum or null. A malformed field earns no
  field credit. Correct fields retain credit even when another field or an extra
  key makes the document schema invalid.
- Schema validity checks shape and field domains, not semantic consistency.
  Non-credential null behavior and expiration correctness are measured against
  the supplied labels. No new semantic rules or date-boundary policy are inferred.
- Unrelated prediction JSON files are listed and ignored; they cannot add credit
  or change denominators. Use a separate directory for each experimental run and
  avoid stale predictions from a previous run.

## Report interpretation

Console output and the optional JSON report include:

- Accuracy per field, overall field accuracy, schema-valid document rate, and
  complete-document accuracy (all eight correct fields and valid schema).
- Separate accuracy for fields whose expected value is null or non-null.
- Per-document mismatches and schema errors, including failures to read predictions.

JSON metrics include `correct`, `total`, and `accuracy` as a fraction from 0 to 1.
An empty diagnostic group has `accuracy: null`; the console displays `n/a`.
For the supplied fixtures there are eight documents, 64 field comparisons, 13
expected nulls, and 51 expected non-null values. One error changes a single field's
accuracy by 12.5 percentage points. The sample set is too small to establish
unseen-document performance, and null-heavy fields can inflate aggregate accuracy.

A completed scoring run exits 0 even when predictions are wrong or missing.
Configuration, fixture, or report-writing errors exit 2. There is no accuracy gate
because the challenge specifies no numerical passing threshold.

Reports contain expected and predicted field values for diagnosis; treat them as
sensitive if evaluating real documents. Parsing errors do not dump raw responses.
Do not put credentials in predictions, report metadata, logs, or source control.
The existing `.gitignore` excludes `outputs/`; reviewed challenge evaluation
reports are published under `results/`; new genuine runs can be reviewed and
archived separately without replacing the historical evidence.

## Offline verification

```bash
python -B -m unittest discover -s tests -v
```

Tests create temporary, synthetic predictions from the supplied labels, then
introduce controlled mistakes to verify scoring. Their perfect score is a test of
the evaluator, not extraction accuracy. Evaluator tests require only the Python
standard library; extractor metadata tests also use the existing extractor
dependencies. All HTTP responses in those tests are mocked. Tests make no API
requests and do not modify the supplied fixtures.
