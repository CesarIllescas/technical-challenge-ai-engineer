# Technical Challenge – AI Engineer

Build an AI system that extracts structured data from medical licenses and certifications, measure its accuracy with an eval, improve it, and deploy it so we can try it. Expect about 90 minutes of work; you have 7 days to submit.

## The problem

MedTrainer helps healthcare organizations with credentialing: tracking the licenses and certifications of their staff. Today much of that data is typed in by hand from scanned or digital documents.

Your task is to build a credential extractor. Given a license or certification document, it returns a JSON with the key fields, flags whether the credential is expired or about to expire, and says clearly when the document is not a credential at all.

## What we give you

- **8 sample documents** of medical licenses or certifications (image or PDF) in [`docs/`](docs/).
- **An expected-output JSON for each document** in [`expected/`](expected/), so you can measure accuracy.
- **A reference date** for computing `expiration_status`: `2026-11-01`, with a 60-day `expiring_soon` window. Both are in [`expected/_reference.json`](expected/_reference.json).
- **A base Python script**, [`scripts/extract.py`](scripts/extract.py), with a basic prompt that extracts the fields at around 60% accuracy. This is your starting point.
- **An OpenRouter API key issued only to you**, with a $5 USD credit limit. That is enough for this challenge if you choose models with care. We can see usage, so your model choices and spend are part of the picture. If you run out of credit, write to us before continuing.

Some documents are deliberately tricky: dates in different formats, a license with no expiration date, and a document that is not a license at all.

## Output format

Your extractor must return a JSON with these fields, so your eval and ours compare the same thing. The expected-output files use the same structure.

| Field | Type | Notes |
|---|---|---|
| `is_credential` | boolean | `false` when the document is not a license or certification |
| `holder_name` | string or null | Full name as printed |
| `credential_type` | string or null | For example "Registered Nurse" or "BLS" |
| `license_number` | string or null | As printed, without extra spaces |
| `issuing_authority` | string or null | Board, state or organization that issued it |
| `issue_date` | string or null | ISO 8601 (`YYYY-MM-DD`) |
| `expiration_date` | string or null | ISO 8601 (`YYYY-MM-DD`); `null` when the document has none |
| `expiration_status` | string or null | `"expired"`, `"expiring_soon"` (within 60 days), `"valid"` or `"no_expiration"`; `null` when `is_credential` is `false` |

Use `null` for any field the document does not contain. Never guess a value that is not in the document.

## What you need to do

1. **Build the eval first.** Write a script that compares the extractor's output with the expected JSON and reports accuracy per field. Run it on the base script to get your baseline.
2. **Improve the system.** Change whatever you think matters: prompt, model, structured outputs, validations, pre- or post-processing. Do at least two iterations and record the before and after numbers for each.
3. **Flag expirations.** Compute `expiration_status` against a reference date. Make the reference date configurable; for the eval, use the date in [`expected/_reference.json`](expected/_reference.json) so results do not change over time.
4. **Deploy it.** Publish the solution with a simple interface where we can upload a document and see the extracted JSON.
5. **Write a document** that explains:
   - what failed at first, what you changed and how much it improved;
   - which model you chose and why;
   - the approximate cost per document;
   - what you would do to take this to production with real data (PHI): security, cost and monitoring.

**Optional bonus:** add a free-text field with a short summary of the document, evaluated with LLM-as-judge.

## Rules

- **AI tools are allowed and expected.** Use Cursor, Claude, Copilot, agents, skills or anything that makes you faster.
- **You choose the deploy platform.** Vercel, Streamlit Cloud, Hugging Face Spaces, Render or anything else, as long as we can open a URL and use it.
- **You may use your own API key or a local model** for development. If you do, document in the README which model you used and the approximate cost. The deployed solution must still run on an OpenRouter model with the key we gave you, so we can test it.

## Deliverables

- A GitHub repository with the code and the eval results.
- The URL of your deployed solution.

To test it, we will upload documents through your URL and review the results. We will also run a few documents you have not seen. A solution that scores 100% on the samples but drops on new documents is overfitted, so aim for a system that generalizes.

## What we evaluate

| Area | What we look for |
|---|---|
| End to end | It works from upload to JSON and is easy to run |
| Extraction quality and eval | Accurate fields, and a clear, honest way of measuring accuracy |
| Hard cases | Missing fields, different date formats, ambiguous or non-license documents |
| Production judgment | Cost, security and handling of health data (PHI) |
| Communication | A clear document that explains your decisions with numbers |
| Deploy | The published URL works and is easy to try |

## Timeline and follow-up

1. Receive the materials and your OpenRouter key.
2. Submit the repository link and the deployed URL within 7 days.
3. Join a 30-minute follow-up interview to walk us through your process, your decisions and how you used AI agents and tools.

If anything is unclear or the materials do not work, reply to the email you received with this challenge.

Thank you for your time. We look forward to seeing how you approach the problem.

---

## Getting started

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export OPENROUTER_API_KEY=sk-or-...   # the key we sent you

# One document
python -m scripts.extract docs/tx_01.pdf

# Every document in a folder, one JSON file per document
python -m scripts.extract docs/ --out-dir outputs/
```

The base script uses `deepseek/deepseek-v4.1-flash` by default. Use `--model` or `OPENROUTER_MODEL` to try a different OpenRouter model.

The base script is intentionally simple. Everything in it is fair game to change.

## Current project layout

- `scripts/`: credential rules, extractor, offline evaluator, and evaluation runner.
- `deploy/`: Streamlit entry point, upload/evaluation adapters, UI dependencies, and setup guide.
- `.streamlit/`: framework configuration, kept at the repository root for Streamlit discovery.
- `docs/` and `expected/`: original documents, labels, and reference configuration.
- `results/`: selected evaluation evidence; `tests/`: offline checks.

Run the following commands from the repository root:

```bash
# Interface dependencies include the core requirements
pip install -r deploy/requirements.txt
python -m streamlit run deploy/app.py

# CLI extraction (paid request)
python -m scripts.extract docs/tx_01.pdf

# Score saved predictions without an API request
python -m scripts.evaluate --predictions results/v02-image-quality/predictions

# Run a new evaluation (paid requests; directory must be new)
python -m scripts.run_baseline --run-dir outputs/new-run

# All tests use mocked model calls
python -B -m unittest discover -s tests -v
```

See [deployment and interface setup](deploy/README.md) for server secrets and the
**Evaluate samples** tab, which runs fresh extraction on the original documents
and displays the shared evaluator's accuracy report. No model requests occur
until an extraction or evaluation button is explicitly selected.
