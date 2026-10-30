# Targets and iteration log

Targets were specified before a real-data evaluation. Quality targets are not promises
of a profitable strategy; a well-measured negative result is useful research.

| Target | Threshold | Evidence now |
|---|---|---|
| Validation outcome log loss vs closing | gap ≤ 0.01 nats, on identical eligible matches | MET: 0.002929470706031445; `results/validation.json` |
| Held-out CLV estimate | report mean, 95% date-block CI, missingness and count; no positivity requirement | MET: negative/inconclusive, two bets; `results/test.json`, `results/test_coverage.json` |
| Primary forward hypothesis | lower 95% CLV CI endpoint > 0 | NOT_ESTIMABLE: no bets |
| Forward pipeline on GitHub | real forecast pushed and server-receipt verified before kickoff | LIVE API workflow passes; first eligible quote window has not opened; no timing claim yet |
| Scheduled execution | at least one `event=schedule` run succeeds | UNMET at the 14:35 UTC checkpoint: no genuine run observed; `results/schedule_check.json`; timer remains active |
| Code verification | ruff and required tests green on GitHub | MET: 38 tests; `results/engineering.json` and CI run URLs |

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

## Pre-activation retry audit

A boundary check found that failed API requests reserved local monthly credits but left
the cached provider balance unchanged. Near the 100-credit reserve, a retry could consume
that reserve. Prospectively fix reservation of both balances, add a failing-request regression
test, and retain earlier tags as v1.2 freezes this operational correction. No real API
failure or overspend occurred. No model/refit/test re-evaluation. Log this conservatively
as another engineering trial; no performance improvement is claimed.

## Delivery status after the interrupted run

All completed download/feature stages were reused. No killed fit needs restarting.
Scientific iteration stopped because the predeclared calibration target was met, with no
positive edge established. The trial registry has 16 entries including the held-out run,
two prospective engineering amendments, two reporting corrections and the deployment check.
The original test DSR retains its 11-trial count at evaluation, while subsequent forward reporting uses the full current registry.

The hourly workflow has successfully queried live fixture discovery, without paid odds
requests outside the registered windows. This does not meet the real-forecast timing
target: the ledger is still empty. The prospective observation window and final CLV
analysis remain pending; no extra observations or profitable result are invented.
The default-branch workflow is active, but no genuine `schedule` event has yet appeared.
Manual dispatches are retained as manual evidence. Schedules are best effort and can be
delayed or dropped; see [GitHub documentation](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule).

## Forward reporting completion — before any forward record

The forward report lacked the closing outcome-score baseline and registered secondary
CLV summaries, despite retaining the underlying fields. Add the paired closing baseline,
log-loss gap, secondary CLV date-block summaries, and separate settled versus scoreable
forecast counts. A synthetic missing-close regression verifies identical scoring coverage
and that paper P&L still includes settlements without closes. All 38 tests pass. No model,
forecast, staking, historical selection or original test metric changes. Both this change
and the earlier saved-prediction reporting correction are conservatively added to the trial
registry now, without backdating their registration or changing the original test report.

## Deployment observation checkpoint — 29 October 2026

The live manual run succeeds. Repository settings show private, non-fork, default main,
Actions enabled, and an active hourly cron. Re-enabled the same workflow without changing
its schedule. Monitored through the next 14:17 UTC boundary and a delay window ending at
14:35 UTC: no genuine schedule event appeared. See `results/schedule_check.json` for the
query, observation interval and counts. The cause is unknown; do not attribute this to
a diagnosed outage or call a manual run scheduled evidence. This failed verification
iteration is conservatively trial 16. The automatic-run target remains unmet; cron remains
enabled. No scientifically justified model change remains after the calibration target.
The first projected decision window opens at 19:00 UTC, so no real forecast receipt can
yet be claimed. The full forward analysis remains prospective.

## Independent review correction, batch 1

Findings 1, 4, 5 and 8 are accepted. Require a receipted latest closing snapshot and
replay its metadata/secondary CLV; distinguish no-close P&L from closing-derived values.
Gate new decisions at forward_end while keeping existing forecasts eligible for closes.
Unresolved historical bets retain pending stakes and cannot affect realized P&L/ROI/CLV.
Split missing outcomes from missing prices. All 21 affected regression tests pass.
Original tags, validation, test metrics and coefficients remain intact. Collection is
paused until the prospective runtime/inference amendment is frozen. Commit references
for every finding are collected in the final review-resolution table below.

## Independent review: inference and operational correction

Candidate 1 (`results/null_calibration_candidate1.json`): weekly HAC-t lag 4, 30-week/100-bet
minimum, 99% critical parameter. Synthetic normal/t(5)/negative-lognormal shocks with
weekly AR(1) 0/0.3/0.6, unequal 4–10 bets/week, 30/60/120 weeks, 10,000 replications per
scenario. Required every Wilson 95% upper false-positive bound ≤0.05. FAILED: worst false
positive rate 0.1264; upper 0.13305674427638517. Reproduce with:
`uv run python scripts/calibrate_inference.py --min-weeks 30 --critical-coverage 0.99 --output results/null_calibration_candidate1.json`.

One focused synthetic-only change: 60-week minimum and 99.9% critical parameter. Candidate 2
(`results/null_calibration.json`) also FAILED: worst rate 0.0484; upper 0.052782457999490946.
Reproduce with `uv run python scripts/calibrate_inference.py`. No observed validation,
test or forward outcome selected these inference parameters. Both attempts count in the
trial registry. After two failed attempts, stop inferential tuning and disable confirmatory
CLV inference for this pilot. The original two-date rule has exact null rejection 0.25 and
coverage 0.5 under independent symmetric continuous zero-mean observations. Bootstrap
quantiles are retained descriptively. A future confirmatory study needs a new protocol.

Full private-cache replay regenerates monthly DC and chronological Elo features, all eight
validation rules and the selected held-out rule into `runs/full_replay`, without reselection.
Headline agreement and maximum probability deviation are in `results/review_corrections.json`.
Original validation/test files and fitted coefficients are preserved. Corrected test missingness
is zero closing triples, one result; the unknown result was not selected. DSR is now
NOT_ESTIMABLE on two nonzero return days, with its original arithmetic retained as a diagnostic.

## Independent review disposition

No BLOCKER findings were issued. All five MAJOR findings are accepted and fixed. Collection
was temporarily paused during amendment; no forward record existed. Commit references below
identify the fixes (the prospective v1.3 tag resolves to the exact correction commit).

| Finding | Disposition / verification | Fix commit |
|---|---|---|
| 1 MAJOR, closing evidence | Fixed: mandatory latest receipted snapshot link; replay metadata and secondary CLV; absent/null-link attacks rejected; no-close P&L allowed | `d4a1159` |
| 2 MAJOR, bootstrap evidence | Fixed: old quantiles labeled descriptive; both failed synthetic candidates retained; prospective v1.3 disables confirmation for all sample sizes | `8b59f2a` (`forward-v1.3`) |
| 3 MAJOR, lost budget reservations | Fixed: remote CAS journal commits before HTTP; uncertain pending state blocks paid calls across fresh runners; first-league success/second failure and no-journal/no-HTTP tests | `8b59f2a` (`forward-v1.3`) |
| 4 MAJOR, end-window close | Fixed: decision-time inclusion; existing forecasts still close after end; boundary integration test spans final decision, close and settlement | `d4a1159` |
| 5 MAJOR, unresolved loss | Fixed: pending exposure retained before subsequent decisions; no realized loss/ROI/settled CLV; exposure-cap regression | `d4a1159` |
| 6 MINOR, reproduction | Fixed: isolated full-feature replay; no reselection or registered-file overwrite; validation guard regression | `8b59f2a` (`forward-v1.3`) |
| 7 MINOR, sparse DSR | Fixed: require 30 nonzero / 60 calendar days, expose counts, hide probability below threshold; preserve original arithmetic | `8b59f2a` (`forward-v1.3`) |
| 8 MINOR, missingness label | Fixed: price/label/union separated, frozen original preserved, corrected companion + independent missingness tests | `d4a1159`, `8b59f2a` (`forward-v1.3`) |
| 9 MINOR, scheduler claim | Fixed: configured versus observed wording; schedule and actual receipt acceptance remain separate pending checks | `8b59f2a` (`forward-v1.3`) |
| 10 MINOR, secret scan | Fixed staged value patterns and all-reachable-history scan. Partially disagreed: ordinary JSON member fixture restoration conflicts with the owner's explicit mandatory legacy scan; retain escaped example member names and the exact legacy scan alongside stronger value detection | `8b59f2a` (`forward-v1.3`) |

The broad legacy false positive is retained solely because the owner explicitly requires that
exact scan before every commit. Value patterns additionally cover NVIDIA/Kaggle/OpenAI,
GitHub, AWS, Google and private-key headers without logging matches. No claim that pattern
scanning proves the absence of arbitrary unknown credentials. The review file stays ignored.

Review verification: `make check test` passes 59 tests. One temporary-directory guard test
initially failed because the new validation-tag check preceded the existing test guard;
restricting that check to validation restored the intended holdout error without a Git call
in a synthetic directory. No experiment result was changed by this test-harness correction.
The full-history value scan is clean. Frozen validation/test/selection/parameters remain
byte-identical to v1.1; only the correction companion carries revised reporting semantics.

Review completion: v1.3 resolves to `8b59f2a755a99fc3bc8399c3ef944002a0681cb8`.
The frozen-source full-feature replay reproduces all original headline values, maximum
probability deviation 1.1102230246251565e-16. No original test/validation or parameter bytes
changed. CI 40900469164 and audit 40900469115 pass at that commit. The remote budget journal
was initialized from the two prior smoke credits and read back (498 remaining, no pending
reservation). The workflow is re-enabled; manual run 40900625519 passes free fixture
discovery with zero forecasts. This is not genuine schedule or live receipt acceptance.

## Paper delivery

`paper/main.tex` reports the negative historical comparison, prospective protocol, all
validation candidates and both failed inference candidates. Tables, numeric macros and
figures are generated from committed aggregate blobs at `1e5fd9d` by paper/make_tables.py;
input/generator SHA-256 hashes are saved alongside them. Crossref resolves Dixon–Coles,
Bailey–López de Prado and Efron; the arXiv API resolves Kaunitz–Zhong–Kreiner, and the API
reference is verified against official documentation. No unverifiable references are used.

`tectonic -X compile paper/main.tex` exits successfully. The initial ten-page layout had a
single reference on its final page; removing redundant DOI URLs yields nine pages without
changing results. All nine final pages were rendered and inspected. No undefined reference,
citation or LaTeX layout warning remains. Tectonic 0.15 emits its bibliography consistency/
rerun warning; this is retained in paper/build.json with an upstream discussion link rather
than hidden. Bibliography content, source hashes and PDF metadata were checked directly.
No arXiv submission is attempted. `make check test` remains clean with 59 tests.
This publication work changes no scientific parameters or selection rule.

Final provenance verification caught a stale metrics.py implementation fingerprint in the
null reports after the paper commit. The fingerprint assertion failed; the shell sequence
continued and created the paper commit, so this is corrected explicitly in new commits.
Re-ran both fixed synthetic candidates with current frozen source. Every policy, null rate,
coverage value and failure status is identical; only source commit/fingerprints change.
`results/null_replay_check.json` records comparison hashes. The full historical replay's
source fingerprints already match. Rebuild the paper manifest from the corrected committed
inputs. No history rewrite, parameter adjustment or hidden new inference candidate.

Final paper refresh uses corrected committed inputs at `9298f83`. All scientific null
fields are unchanged, and every current experiment implementation hash now matches.
The rebuilt PDF still has nine pages; rendered-page comparison finds only the intended
source-commit text on page 8 changed, which was inspected again. All remaining pages are
pixel-identical to the inspected version. `make check test` passes 59 tests. This completes
the provenance correction without altering any original test/validation estimate or tag.

## Final review: scheduling reliability and paper presentation

1. Stale schedule evidence: fixed the evidence collector to paginate all main-branch
   `paper.yml` schedule events independently of recent CI/manual runs. README TL;DR and
   operations blocks read the result file; the paper macro already reads that same file.
   The old schedule polling checkpoint is explicitly historical and superseded.
2. Runner availability: add a macOS hourly LaunchAgent and a shared entry point with
   a blob-SHA compare-and-swap whole-cycle lease and UTC-hour completion marker in the
   existing `api-budget` journal. Both runners retain the original paid-call reservations,
   cap, reserve, forecast deduplication and pre-kickoff publication/audit path. A killed
   runner leaves a non-expiring lease for manual reconciliation. The final launcher sources
   the owner's existing .zshrc with startup output suppressed; no credential enters argv,
   repository files or the LaunchAgent plist. Installation and live verification follow
   the code milestone. No scientific experiment, parameter or registration tag changes.
3. Readability: add the generated three-line README TL;DR. Trim the paper's correction
   narrative while retaining failed inference results and relevant limitations in the
   subsequent PDF milestone.

Verification: `make check test` passes 67 tests; new tests cover competing runner CAS,
completed-hour deduplication, preserved paid reservations after failure, failed publication,
Keychain capture and a secret-free plist. This is an operational iteration, counted as
such in the trial registry; it does not change historical trial counts or model selection.

The first live installation (`d64fc9e`) stalled on a macOS Keychain authorization prompt,
before lease acquisition or any provider request. It was stopped and its newly created
Keychain item removed. The simpler final launcher uses the owner's already exported key
from the existing .zshrc; that file is never modified. Optional Keychain retrieval has a
bounded timeout. No credit was consumed by the failed installation attempt.

GitHub CI/audit at `d64fc9e` did not start any steps. The check annotation states:
“The job was not started because recent account payments have failed or your spending
limit needs to be increased.” This is an external account restriction, not a failing
code check. No spending setting is changed. Local checks continue; keep hosted fallback
configured but disclose that hosted execution currently requires owner billing resolution.

Code milestones: shared scheduling/evidence `d64fc9e`; unattended environment loading
`47771f8`. The real launchd cycle completed at 2026-10-30T05:04:35Z and pushed `039b2be`.
Its two new /events manifest entries carry zero credits; the durable journal remains at
2 consumed, 498 remaining, no pending reservation. The scheduled :05 launch then skipped
the same completed hour; a local invocation with the GitHub runner flag also skips.
`results/local_runner.json` stores sanitized receipts, plist hash and before/after journal
states. These checks do not substitute for a live forecast/close/settlement receipt.

Failure handling is tightened: any failed cycle retains the whole-cycle lease, including
publication failure after a successful capture. This avoids spending again on unpublished
decisions from another runner. Only a confirmed manual reconciliation may release it.
The runbook and dated scheduling note document the single shared cycle. Frozen strategy,
source features and original registration tags remain unchanged. The latest local check
passes 67 tests. No scientific experiment was started for these final review items.

Final-review code/live-evidence milestone: `c1a294e`. Both runners retain a failed-cycle
lease; unit checks pass 67 tests. Hosted evidence records the exact account rejection and
zero started steps in results/engineering.json. The historical estimates and inferential
status are unchanged. The final PDF will use committed live schedule and Mac-run evidence.

Final-review paper refresh uses committed aggregate inputs at `a66736c`: the schedule macro
reads the paginated live evidence and the Mac-run macro reads results/local_runner.json.
The three-line README TL;DR is also generated from committed-result fields. Process and
review-history prose is shortened; all historical estimates, failed inference candidates,
source limitations and reproducibility commands remain. `tectonic -X compile paper/main.tex`
succeeds; nine pages rendered, tables/status/references inspected at page resolution, no
undefined citations/references or layout warnings. The known Tectonic bibliography rerun
warning remains documented in paper/build.json. `make check test` passes 67 tests; `make
verify` reports NO_FORECASTS rather than claiming on-time receipt acceptance. Frozen
scientific sources and original validation/test/selection/parameter bytes are unchanged.

Final-review delivery commits: item 1 (paginated live schedule evidence) `d64fc9e` and
`c1a294e`; item 2 (Mac scheduling, durable shared lease, actual provider discovery/push,
and deduplication) `47771f8` and `c1a294e`; item 3 (generated TL;DR and shorter rebuilt
paper) `d64fc9e` and `e5bf5cb`. The installed checkout was fast-forwarded to `e5bf5cb`.
`results/final_review_verification.json` records final source/PDF checks, agent exit 0,
498 remaining credits and the live hosted rejection annotations at that release. No new
scientific experiment was run. Hosted CI/audits remain BLOCKED_ACCOUNT_BILLING; owner
billing/spending resolution is required for hosted execution. This is not reported green.

## Improvement round 3 — accumulation, visible denominators and local CI

Targets: independently replay all live pre-kickoff forecast receipts; distinguish forecast,
bet and settled-with-close counts in the README figure; expose live credit headroom without
a provider request; ensure local CI leaves tracked files untouched. Keep the active model,
threshold, staking, test artifacts and registration tags fixed. No new fitting or historical
experiment is warranted: the active blend already anchors to market probabilities and uses
time-decayed Dixon–Coles features; there are no settled forward bets on which to assess it.

Iteration 1: `make health` checks the remote api-budget journal and audit-run creation
receipts, plus observed launchd log slots. It finds four receipted forecasts, all abstentions,
nine completed hourly cycles and no missing slots between the first and last observed
completion. These are observed log checks, not an uptime SLA or successful hosted audit.
The minimum server-receipt lead is 1464.1833333333334 minutes and maximum publication
latency 27.152447 seconds. Source values are in results/forward_health.json. The check
makes zero provider calls. Credits are 4/400 charged, balance 496, reserve 100; 396 remain
usable under both guards. Existing forecast/closing/scoring logic is unchanged.

The new automatic dashboard presents forecast count, paper-bet count, settled CLV sample,
cumulative CLV and paper P&L with capture time and budget. Missing closes are excluded only
from the CLV series. With no settled bets, neither performance plot draws an artificial
zero-return line. README TL;DR and operational evidence use explicit denominators and dates.
Report budget fields omit old runner-lease copies from cached usage; the health command
reads current lock/reservation state directly from the durable remote journal.

A third focused improvement fixes local CI's tracked-file mutation: the audit calls the
same verifier without writing results/verification.json. Per-push CI receipts stay in the
ignored receipt directory; selected receipts can be published explicitly. This prevents
CI itself from making a clean runner checkout dirty. The original owner's d017cef receipt
is preserved and explicitly committed. Tests cover missing cycles, unknown freshness,
receipt timing, empty dashboard and differing P&L/CLV denominators. Stop after verification:
further model selection or new tuning would fragment the ongoing registered pilot.

Round-3 milestone `ff27fd1` passed its pre-push local CI on a clean committed tree:
72 tests, lint/format and the four-forecast receipt audit all pass. The hook leaves tracked
files unchanged; its receipt is results/ci_local/ff27fd1.json. No provider call was made
by this round, so balance remains 496. The model and historical metrics are unchanged.
The updated paper will distinguish four recorded forecasts from the zero settled-bet
CLV denominator. Further work now depends on prospective observations, not another tune.
