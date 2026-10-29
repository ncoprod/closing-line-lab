# Targets and iteration log

Targets were specified before a real-data evaluation. Quality targets are not promises
of a profitable strategy; a well-measured negative result is useful research.

| Target | Threshold | Evidence now |
|---|---|---|
| Validation outcome log loss vs closing | gap ≤ 0.01 nats, on identical eligible matches | NOT_RUN: source permission |
| Held-out CLV estimate | report mean, 95% date-block CI, missingness and count; no positivity requirement | UNEVALUATED |
| Primary forward hypothesis | lower 95% CLV CI endpoint > 0 | NOT_ESTIMABLE: no bets |
| Forward pipeline on GitHub | real forecast pushed and server-receipt verified before kickoff | NOT_RUN: permission and freeze |
| Scheduled execution | at least one `event=schedule` run succeeds | Check `results/actions_evidence.json`; gated runs only prove scheduling |
| Code verification | ruff and required tests green on GitHub | CI run URL in actions evidence |

For research iterations: run validation → measure → diagnose → make one focused change
on training/validation only → re-run. Stop when the calibration target is met or after two
iterations without improvement. Preserve the gap and negative metrics. Do not open the
test season to decide what to change. Stop scientific iteration immediately at the tag.

Eight candidate model/threshold combinations are predeclared in the protocol and code.
Every evaluation appends a trial record before fitting; every iteration or blocked attempt
must also append a record. DSR counts the entire append-only registry, not only successful
or winning variants. Engineering unit tests on synthetic data do not constitute evidence
that a strategy works and are never used to choose a model.

## Iteration 1 — 2026-10-29: source audit and initial implementation

Attempt: establish the real-data train/validation/test baseline.
Measurement: no legitimate bulk dataset acquired; no model research metric estimated.
Diagnosis: the live source's restricted terms do not establish permission for the proposed
automated training/collection and later redistribution. Its non-C quotes are snapshots,
not timestamped opening quotes; Pinnacle is explicitly stale after July 2025.
Focused change: gate source access and use AvgC as the planned closing benchmark, with
same-book and de-vigged sensitivity checks. Keep held-out targets out of model selection; see the schema-preview exception below.
Outcome: baseline blocked. See `results/trials.jsonl` and `results/status.json`.

No second scientific iteration is manufactured without data. The permission-gated Actions
run and synthetic tests are engineering checks; they do not close the live-forecast target.

## Engineering verification — 2026-10-29

The initial property-test setup failed because a generated argument was bound positionally;
keyword binding fixed it. NumPy was bounded below 2.5 after pandas compatibility warnings.
A final source audit tightened the holdout gate, frozen-runtime coverage and settlement replay.
A one-off documentation-generation command failed on quoting and was rerun successfully.
See `results/engineering.json` for the measured test counts. These fixes used synthetic data
only; no research metric improved or deteriorated because none was estimated. The first
manual paper workflow succeeded through the permission gate; cron evidence is recorded
separately in `results/actions_evidence.json`.

Holdout correction: two test-season rows appeared during the initial schema preview.
They were not used to fit or select a model. Their IDs were prospectively excluded from
primary test metrics before any research fit; the full season is not claimed to be blinded.
