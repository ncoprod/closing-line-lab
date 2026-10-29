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

## Iteration 2 — 2026-10-29: owner-approved data split and real baseline

The owner superseded the earlier source gate: one local private research download,
no historical row publication, and The Odds API for hosted forward collection. No new
permission is being inferred from a boolean. The 150 league/season files are cached once
with SHA-256 identities; interrupted downloads resume without re-fetching existing files.
One Windows-encoded CSV stopped normalization; a tested decoding fallback fixed it.
No historical row is staged. Validation features now exist; metrics are not yet inspected.

Focused change: separate local training from official API collection and export model
parameters for hosted inference. The API client was checked against an attributed docs
sample and live responses, with quota headers, freshness checks and a strict budget.
This iteration and all eight declared validation candidates count as trials. The held-out
season remains unevaluated; its two predeclared exclusions remain in force.

The first post-split CI run failed: a local-permission unit test inherited Actions' hosted
runner environment. Its fixture now explicitly simulates local execution; a separate test
continues to reject real hosted football-data access. This changes no research model.
An additional ledger test rejects closing snapshots without their own on-time server receipt.

## Iteration 2 measurement and stopping decision

Validation evaluated eight predeclared candidates on 11486 common
closing-price rows. The deterministic winner is blend / 0.05: outcome log-loss gap
0.002929470706031445 nats, below the predeclared 0.01 target. Only 4 bets
were selected; mean log CLV -0.0398891288028935 with 95% date-block CI
[-0.08678290542845579, 0.016520650702510617]. Calibration proximity is not an edge: the close scores better,
and CLV is negative and inconclusive. No extra threshold/league/model search is justified.
Stop scientific iteration at the target and freeze before evaluating 2025/26. All candidates,
including the substantially negative standalone DC/Elo results, remain in validation.json.
The trial registry contains 10 entries before opening test.

The reboot killed the uncommitted command sequence, but completed raw caches and validation
features survived. They were reused exactly; no historical source file was redownloaded.

## Frozen held-out evaluation — no further model changes

`forward-v1` was pushed before the first test-feature generation/evaluation. The frozen
blend scores 3754 complete-price test matches after the two predeclared
exclusions and missing-price filtering. Log-loss gap to closing is 0.0010033873760322276,
summed multiclass Brier 0.6034158390490296 versus closing 0.602787224497548.
Only 2 paper bets occurred. Mean log CLV -0.02607313191949432, 95% date-block
CI [-0.15984870094189613, 0.10770243710290749]; P&L -0.8326864888550614 fictional units and ROI -1.0.
The close scores better and no positive CLV is established. Two dates do not support useful
power estimation; the bootstrap CI is extremely coarse. These results are final v1 evidence,
not inputs to another threshold/model search. The test report refuses overwrite.
The registry now has 11 entries, conservatively counting this fixed test evaluation.

## Prospective engineering amendment — club identifiers

Initial live coverage: all 20 EPL team names mapped; three of 24 Championship team names
did not. This check should have preceded the original tag. Before the first forward record,
add the three exact identity aliases in a separately tagged v1.1 amendment, retaining the
original v1 tag and test results. No refit, test rerun, bet-rule change or metric selection.
The parameter artifact is unchanged and is now explicitly frozen by the runtime tag too.
This engineering correction is conservatively logged as an additional iteration/trial.

## Reporting correction — same saved predictions, unchanged test metrics

One historical test target has closing prices but no result. The original metric evaluator
already excluded it and neither selected paper bet belongs to it. The calibration/paired-loss
report initially cast that missing label and included it. Filter missing results before
plotting; regenerate aggregates from saved predictions only, with no refit or re-evaluation
of strategy choices. The corrected calibration count matches the 3,754 core scored rows.
The test report field named missing_closing_triples counts all unscorable rows; its one
excluded row is actually a missing result, not absent closing odds. Preserve the original
test report and make that naming limitation explicit.
