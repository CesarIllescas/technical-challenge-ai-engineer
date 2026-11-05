# Medical credential extraction: technical report

The extractor improved from **35/64 correct fields (54.69%)** in v00 to
**64/64 (100%)** in the selected final v02 run on the eight supplied documents.
The final model is `deepseek/deepseek-v4.1-flash`, with a measured mean inference
cost of approximately **$0.001725 per document**. These are development-set
results; the samples were used during iteration, so this score does not establish
accuracy on unseen documents or guarantee that every new run will score 100%.

## Evaluation and measured improvements

I built the offline evaluator before changing extraction behavior. It compares
the eight required fields against the supplied JSON using exact typed equality,
and reports per-field accuracy, overall accuracy, valid schemas, and fully correct
documents. Missing or failed predictions remain in the denominator. Evaluation
uses the supplied reference date, `2026-11-01`, and 60-day expiration window.
The labels and scoring rules remained unchanged across iterations.

| Version | Main change | Correct fields | Schema-valid documents | Fully correct documents |
|---|---|---|---|---|
| [v00](results/v00-baseline/evaluation.json) | Original extraction baseline | 35/64 (54.69%) | 1/8 | 0/8 |
| [v01](results/v01-contract/evaluation.json) | Explicit extraction contract and reference configuration | 62/64 (96.88%) | 8/8 | 6/8 |
| [v02](results/v02-image-quality/evaluation.json) | Local validation and expiration rules, higher-resolution rendering, orientation correction | 64/64 (100%) | 8/8 | 8/8 |

v01 improved field accuracy by **42.19 percentage points** over v00. The selected
final v02 run added **3.13 percentage points**, for a total gain of **45.31
percentage points**. Intermediate experiments also introduced regressions; these
three published milestones are selected individual runs, not averages across
every attempt. [Results and provenance](results/README.md) describe that history.

## What failed in v00

The baseline recognized whether each sample was a credential, but it did not
consistently satisfy the required field contract:

- **Dates:** six credential expiration dates and one issue date used slash
  formats instead of ISO dates. Date-format errors made seven outputs schema
  invalid.
- **Names:** five names included professional degrees such as MD or DO, which
  the expected holder names exclude. Personal suffixes still needed preservation.
- **Identifiers:** one license number changed a period into a hyphen:
  `MD.20417` became `MD-20417`.
- **Type and issuer wording:** capitalization differed from the expected
  representation, and some issuer names included extra administrative wording.
  These counted as errors under the declared exact comparison.
- **Non-credential consistency:** a renewal notice was correctly classified as
  `is_credential: false`, but six other fields were populated instead of null.
- **Expiration status:** both examples inside the expiring-soon window were
  returned as valid. The non-credential also had a status instead of null.

The starter prompt did not define the field conventions or supply the evaluation
reference date. That was a plausible cause of the formatting, consistency, and
status errors. Punctuation errors suggested a separate transcription problem;
the baseline alone could not determine whether rendering quality or model
variability caused them. The [baseline analysis](results/v00-baseline/README.md)
records the individual failures.

## How the system improved

### v01: make the extraction contract explicit

I kept the original model and first-page, 100-DPI PDF rendering, and clarified
the prompt: return exactly eight keys, use ISO dates and genuine nulls, distinguish
credentials from notices, exclude professional degrees from names, preserve
identifier punctuation and personal suffixes, and select the principal issuer.
The prompt also received the configured reference date and expiration window.

This improved the selected run to 62/64 correct fields. All schemas became valid;
the two remaining errors were the license-number period changed to a hyphen and
a missing period in `JR.`. The pattern favored improving transcription rather
than adding document-specific replacements.

### v02: strengthen general rules and input quality

I retained the v01 prompt and added deterministic expiration calculation,
conservative date normalization, non-credential null consistency, and schema
validation. Local date normalization accepts ISO dates and unambiguous numeric
dates with four-digit years; ambiguous or invalid values produce explicit errors.
For credentials, dates before the reference are expired, day 0 through day 60
are expiring soon, later dates are valid, and a null expiration produces
`no_expiration`. The boundary convention is an explicit implementation choice.

Some earlier v02 attempts and model substitutions regressed, so local rules
alone were not sufficient. The final version increased PDF rendering to 200 DPI
and added quarter-turn orientation correction when PDF text geometry provides
strong evidence. Missing, sparse, or conflicting text leaves orientation
unchanged. Image inputs pass through, and PDF processing still uses only the
first page.

The selected final run achieved 64/64 fields. Its metadata shows that local
post-processing changed no fields: the model's parsed values were already
correct. Resolution and orientation changed together, and provider routing was
not fixed, so this experiment does not isolate their individual contributions.
There are no filename-based answers, label lookups during extraction, or
document-specific punctuation corrections.

## Model choice

I chose **`deepseek/deepseek-v4.1-flash`** for its balance of inference cost, token
usage, and measured extraction performance within the challenge's $5 budget.
It was the starter model, and improving the prompt and document preparation
allowed it to reach 100% in the selected sample run without a larger architecture
or an additional OCR service.

I also tested **`deepseek/deepseek-v4.1-flash-1017`**, which remains an alternative
through the existing model configuration. In one exploratory comparison on the
same extraction revision, the original model scored 60/64 and the variant
61/64: a one-field difference. That comparison used an intermediate revision,
not the final 200-DPI configuration, and does not establish a consistent advantage.
The original model subsequently achieved the final 64/64 result, so the evidence
did not justify changing the default. Exploratory comparison files remain local;
the published results preserve the selected v00, v01, and final v02 runs.

As checked on November 5, 2026, the variant ranked first on OpenRouter's usage
leaderboard, based on tokens processed. That measures adoption, not credential
extraction accuracy; the decision here rests on the task-specific evaluation.
See [OpenRouter rankings](https://openrouter.ai/rankings) and the
[variant's model page](https://openrouter.ai/deepseek/deepseek-v4.1-flash-20261017).

## Approximate cost per document

The selected final [run metadata](results/v02-image-quality/run.json) records
response `usage.cost` for all eight documents:

| Measurement | Final v02 run |
|---|---|
| Total reported inference cost | $0.01379920 |
| Mean inference cost per document | $0.00172490, approximately 0.1725 US cents |
| Prompt tokens | 13,961 |
| Completion tokens | 12,519 |
| Total tokens | 26,480 |

The mean is the summed response cost divided by eight. At the same workload and
rates, 1,000 documents would cost approximately **$1.72 in inference**. This is an
illustration, not a price guarantee: image size, output/reasoning tokens, caching,
provider routing, retries, and future prices can change the result. Hosting,
storage, and human review are excluded.

For context, the selected v01 run cost $0.007662025 total, approximately $0.000958
per document. v00 predates response accounting, so its cost is unknown. The final
run cost is not total development spend or a statement of remaining API credit.

## Validating the results

Saved predictions, evaluation reports, and run metadata are under `results/`.
The final predictions can be independently scored without model requests:

```bash
python -m scripts.evaluate --predictions results/v02-image-quality/predictions
```

The Streamlit interface supports upload-to-JSON viewing and download. Its sample
evaluation runs fresh extraction, computes metrics with the same evaluator, and
lets users inspect generated and expected JSON. The downloadable ZIP includes
the actual scored predictions, labels, reference configuration, report, and run
metadata so users can recompute the metrics. Viewing or downloading results does
not repeat model calls. Setup is in [deploy/README.md](deploy/README.md).

The sample set contains only eight documents and one non-credential. Repeated
development on these samples limits any claim of generalization. Before relying
on the system more broadly, I would freeze the configuration, measure repeated
runs, and evaluate independent documents covering different issuers, scans,
orientations, missing fields, and ambiguous dates. First-page processing and
orientation correction without an OCR fallback are also current limitations.

## Taking the demonstration to production with real data

The current solution is designed as a technical demonstration using the provided
sample documents. Before processing real-world sensitive data, I would focus on
three areas. The following are proposed production improvements, not claims about
controls already implemented in this demonstration.

### Security and PHI protection

I would introduce authentication, authorization, encryption in transit and at
rest, and clearly defined data retention policies. Uploaded documents would be
stored only when necessary and removed according to the organization's retention
requirements. Those policies would also cover extracted JSON, evaluation
artifacts, session data, and downloaded results.

Before transmitting documents containing PHI to an external AI provider, I would
verify its data handling policies, contractual requirements, and suitability for
the organization's HIPAA obligations, including Business Associate Agreements
where applicable. This review would cover OpenRouter and the actual downstream
providers, with routing restricted to approved services. HHS guidance addresses
the need for risk assessment and appropriate agreements when cloud services
process ePHI; encryption alone does not resolve those obligations.
See [HHS guidance on HIPAA and cloud computing](https://www.hhs.gov/hipaa/for-professionals/special-topics/health-information-technology/cloud-computing/index.html).

Application logs and monitoring systems should avoid recording sensitive
document contents or personal information. API credentials would remain in a
server-side secret store and would not appear in source, logs, or exports.

### Cost optimization

I would track token consumption, processing time, and inference cost per document.
The existing response accounting provides a starting point. Model selection
would depend on the measured trade-off between extraction accuracy, latency,
and cost rather than benchmark performance alone.

I would also introduce bounded retries for appropriate transient failures,
request limits, and usage alerts to prevent unnecessary spending. The current
evaluation runner deliberately stops on operational failures without automatic
retries; a production retry policy would need explicit limits and accounting.

### Monitoring and reliability

I would monitor request latency, API failures, invalid outputs, and processing
costs. To monitor extraction quality, I would maintain a representative evaluation
dataset and periodically compare production outputs against human-verified
results, with access and retention controls appropriate to that data.

Prompt or model changes would be evaluated before deployment to detect
regressions. Documents with ambiguous or unreliable extraction results could be
routed for human review rather than automatically accepted. Valid JSON alone
would not be treated as evidence that every extracted value is correct.
