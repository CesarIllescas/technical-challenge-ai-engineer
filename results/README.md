# Experiment results

Each directory preserves one reviewed run. Keep run evidence and predictions
unchanged after archiving; use a new directory for every subsequent run, including
unsuccessful experiments. All scores below use the same eight supplied documents,
strict evaluator, and `2026-11-01` reference date with a 60-day window.

| Run | Change | Requested model | Field accuracy | Schema validity | Complete documents | Cost |
|---|---|---|---|---|---|---|---|
| [v00-baseline](v00-baseline/README.md) | Unchanged starter | `deepseek/deepseek-v4.1-flash` | 35/64 (54.69%) | 1/8 (12.50%) | 0/8 (0%) | Not captured |

The initial run is the baseline, not one of the challenge's two required
improvement iterations. Reserve `v01-<change>` and `v02-<change>` for those
experiments. Add further rows for further runs; do not replace a prior result.
Record before/after numbers and whether each change was retained, even if it
reduced accuracy. No improvement experiment has been run yet.

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
