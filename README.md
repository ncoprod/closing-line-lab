# closing-line-lab

CI: GitHub Actions; local fallback `scripts/ci_local.sh` (ignored receipts in results/ci_local/; selected receipts are committed explicitly) while hosted minutes are unavailable.

<!-- TLDR:START -->
**TL;DR:** Held-out blend log loss 1.007961; closing benchmark 1.006958.
2 historical paper bets; mean log CLV -0.026073; no demonstrated edge.
Forward: 21 forecasts, 0 paper bets; CLV n=0 (not estimable). [Sources](results/review_corrections.json) · [Forward](results/forward.json) · [Operations](results/actions_evidence.json).
<!-- TLDR:END -->

[Read the paper (PDF)](paper/main.pdf) · [LaTeX source](paper/main.tex)

**Paper-only research.** No bookmaker account, bet placement or money handling.

<!-- RESULTS:START -->
**55476 research dataset rows; 21 forward forecasts; 0 paper bets; 0 settled bets.**
Data status: **FROZEN_MODEL_READY**. Validation: **COMPLETE**. Test season: **EVALUATED_ONCE**.

| Forward metric | Observed value |
|---|---:|
| Mean log CLV | NOT_ESTIMABLE |
| CLV denominator (settled bets with closing prices) | 0 |
| Descriptive date-bootstrap quantiles | NOT_ESTIMABLE |
| CLV inference (disabled for this pilot) | INSUFFICIENT_INFORMATION |
| Paper profit (initial account 100 units) | 0.0 |
| Pending / void forecasts | 2 / 3 |

Validation selected **blend / 0.05 minimum edge**: 11486 scored matches, log loss 1.0057639497705855 versus closing 1.002834479064554 (gap 0.002929470706031445).
Only 4 paper bets; mean log CLV -0.0398891288028935, descriptive date-bootstrap quantiles [-0.08678290542845579, 0.016520650702510617]. These are not calibrated confidence limits. The selected rule's sparse bets severely limit forward power.

| Validation model | Minimum edge | Log loss | Paper bets | Mean log CLV |
|---|---:|---:|---:|---:|
| market | 0.03 | 1.0063675492486361 | 0 | None |
| market | 0.05 | 1.0063675492486361 | 0 | None |
| dc | 0.03 | 1.0259169666789891 | 3401 | -0.0043107974661079 |
| dc | 0.05 | 1.0259169666789891 | 3192 | -0.004204388069203356 |
| elo | 0.03 | 1.0259362847864204 | 3465 | -0.007974626992547858 |
| elo | 0.05 | 1.0259362847864204 | 3272 | -0.007093607128997683 |
| blend | 0.03 | 1.0057639497705855 | 14 | -0.04823819541359959 |
| blend | 0.05 | 1.0057639497705855 | 4 | -0.0398891288028935 |

Held-out test: 3754 scored matches; log-loss gap to closing 0.0010033873760322276; 2 paper bets; mean log CLV -0.02607313191949432, descriptive bootstrap quantiles [-0.15984870094189613, 0.10770243710290749]. Paper P&L -0.8326864888550614 units; ROI -1.0.
Test DSR: NOT_ESTIMABLE (2 nonzero return days). Power planning (one-sided 5%, 80%): NOT_ESTIMABLE bets by log-CLV basis-point effect; sparse-sample estimates are unstable.

Sources: [status](results/status.json), [validation](results/validation.json), [original test](results/test.json), [corrected replay](results/review_corrections.json), [forward](results/forward.json).
![Forward-test dashboard: counts, CLV denominator, paper profit and credit budget](results/forward_dashboard.png)
![Forward calibration](results/calibration.png)
<!-- RESULTS:END -->

The research question is whether a pre-registered football model can obtain positive mean
log closing-line value (CLV) on prices recorded before kickoff. Dixon–Coles, Elo and a
market-anchored logistic blend are compared chronologically. There is no asserted edge.
More matches do not imply independent observations. This pilot has no validated CLV
significance rule; calendar-date bootstrap endpoints are descriptive.

```mermaid
flowchart LR
  A[Local private CSV download] --> B[Ignored cache + committed SHA manifest]
  B --> C[As-of Dixon-Coles + Elo + snapshot market]
  C --> D[Validation only: select and freeze]
  D --> E[Held-out test with declared exclusions]
  D --> J[Frozen parameter export]
  L[Mac launchd primary + GitHub fallback] --> K[Shared journal + durable credit guards]
  K --> O[The Odds API]
  O --> F[Pre-kickoff paper forecasts]
  J --> F
  F --> G[Hash-chain ledger + GitHub receipt]
  G --> H[Closing prices + results]
  H --> I[CLV + calibration + P&L + power]
```

Historical football-data rows are downloaded once for the owner's private research and
stay local. Only code, SHA manifests, fitted parameters and aggregate results are committed.
Hosted forward collection uses The Odds API, whose terms permit programmatic research.
See [DATA_NOTICE.md](DATA_NOTICE.md). Historical non-C prices are pre-closing snapshots,
not verified opening quotes; the provider's stale Pinnacle fields are excluded.

Python 3.12 and uv: `make install`, `make check test`, `make verify`.
The implementation includes Dixon–Coles with exponential time decay, Elo, and a regularized
multinomial logistic blend anchored to market probabilities. All eight declared validation
candidates and the frozen held-out result are reported above.

## Paper

The paper reports the negative historical comparison and the prospective protocol. Forward
forecasts are accumulating; settled betting performance remains unobserved. Its tables, numerical macros and figures are generated
from committed aggregate artifacts with `uv run python paper/make_tables.py`, then built
with `tectonic -X compile paper/main.tex`. Sources and SHA-256 hashes are recorded in
[paper provenance](paper/generated/provenance.json). The bibliography has verified
Crossref/arXiv identifiers and an official documentation URL, with
[verification metadata](paper/reference_verification.json). The local Tectonic 0.15 build
emits a bibliography rerun warning; citations and all rendered pages were checked. See
[build evidence](paper/build.json) and the matching [upstream discussion](https://github.com/tectonic-typesetting/tectonic/discussions/1186).

## Reproduce

See the [runbook](docs/RUNBOOK.md), [registered protocol](PREREGISTRATION.md) and
[iteration targets](ITERATIONS.md). Historical authoring (download → features → candidates → selection → original tag →
once-only test → parameter export) is complete. Normal clones must not repeat selection
or replace registered reports. With the matching private cache and local research permission:

```sh
uv sync --frozen
make check test
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 uv run cll replay \
  --output-dir runs/reviewer-replay --rebuild-features
# Compare runs/reviewer-replay/replay.json with results/review_corrections.json.
make verify
```

Replay regenerates monthly DC/as-of Elo features, all declared validation predictions and
the fixed selected test rule in an isolated directory. It does not reselect a model, mutate
tags or overwrite registered artifacts. Row-level outputs remain ignored. Exact source-data
replay requires the private cache matching the committed manifest; mutable URLs cannot
recover a lost historical snapshot. `make select` is for the original pre-freeze authoring
sequence only and intentionally refuses reselection. Validation and test commands now both
refuse to overwrite registered result files.

The original `forward-v1`, `forward-v1.1` and `forward-v1.2` tags are retained. The
prospective **forward-v1.3** amendment repairs evidence/budget/settlement handling and
withdraws the uncalibrated CLV significance rule before any forward observation. No fitted
coefficient, forecast formula, selected threshold or staking parameter changed.
[Corrected replay](results/review_corrections.json) preserves the original point estimates;
[original test](results/test.json) remains historical evidence. Both synthetic-only inference
candidates failed the predeclared calibration screen; this pilot reports **descriptive CLV,
with no confirmatory rejection rule**. Sparse bootstrap endpoints are quantiles, not calibrated
confidence limits. See the explicit amendment and failed experiments in the protocol.

![Validation and held-out calibration](results/historical_calibration.png)
![Selected historical paper results](results/historical_paths.png)

[Power analysis](results/power_analysis.json): the four validation bets give an unstable
planning estimate of 23,821 bets for 10 log-CLV bp (one-sided 5%, 80% power). Two test bets
cannot estimate power. The planned window is unlikely to establish a small edge for this
sparse rule. The hypothesis remains prospective; insufficient evidence will be reported.

<!-- OPERATIONS:START -->
GitHub: **7 successful scheduled runs**, checked 2026-11-02T01:05:27.865426+00:00. [Live evidence](results/actions_evidence.json) lists every schedule event, separately from manual runs. Mac log: **9 completed hourly cycles**; 4/4 forecasts have pre-kickoff receipts. Credits charged: 4/400; provider balance 496, reserve 100. Health checked 2026-10-30T13:24:05.602446+00:00. [Health evidence](results/forward_health.json); refresh with `make health`.
<!-- OPERATIONS:END -->

The Mac LaunchAgent `com.ncoprod.closing-line-lab` runs hourly at minute 05 while Nico is
logged in and the Mac is awake. GitHub Actions remains an hourly fallback at minute 17 UTC.
Both execute `ops/run_cycle.py`, acquire a compare-and-swap lease in the **same `api-budget`
branch**, refresh main, and skip an already completed UTC hour. Existing match IDs also
deduplicate forecasts across decision windows. Paid calls still reserve credits durably
before transmission; adding a runner does not increase the cap. Forecasts are published
before settlement processing using the existing deadline checks, secret scans and audit dispatch.

Install on this Mac with `uv run python ops/install_launchd.py`. It creates a separate checkout
under `~/Library/Application Support/closing-line-lab/checkout`, preserving the development
working tree. The launch script sources the owner's existing `~/.zshrc` (startup output
suppressed), loading the exported `ODDS_API_KEY` into the environment. It does not modify that
file or copy the key. An existing login Keychain item named
`com.ncoprod.closing-line-lab.ODDS_API_KEY` is an optional fallback with a bounded read timeout.
No key is written to the plist or repository. The agent logs sanitized status to the checkout's ignored
`runs/launchd.log`; inspect it and `launchctl print gui/$(id -u)/com.ncoprod.closing-line-lab`.
A locked Keychain, sleeping/offline Mac or dirty runner checkout can prevent a run. A crash or failed cycle
leaves the remote lease in place: confirm both runners have stopped before manually clearing
only `runner_lease` by a blob-SHA compare-and-swap. Never clear a pending credit reservation
without provider reconciliation. Leases do not expire automatically. Missed windows are not
backfilled. Unload while idle with `launchctl bootout gui/$(id -u)/com.ncoprod.closing-line-lab`.

Free fixture
discovery triggers league-wide EU/h2h requests only around decisions (23–25 hours before
kickoff) or closing snapshots (15–75 minutes). **The closing line means the last observed
pre-kickoff snapshot**, with bookmaker, source age and actual gap retained. Betfair EU is
preferred; Pinnacle is the fixed fallback. A 400-credit cap and 100-credit provider reserve
protect the 500-credit plan. Each paid transmission first commits a reservation to the
separate `api-budget` branch. An ambiguous request blocks further paid calls until manual
reconciliation; a failed runner cannot erase reservations. Paid requests are not retried. [API costs](https://the-odds-api.com/liveapi/guides/v4/) define this budget. Missing windows/budget-limited coverage are never backfilled.
Recent results cost two credits per league; at most one request per league/day when needed.
Forward parameters are exported locally after freezing and stay fixed for v1. No hosted
football-data download, historical row cache or retraining occurs. See the protocol for
source shifts, model drift, commission and the Actions-minute planning assumptions. Hosted CI, audits and fallback execution are currently refused by an account billing/spending
restriction; see [engineering evidence](results/engineering.json). The
[GitHub Free allowance](https://docs.github.com/en/billing/concepts/product-billing/github-actions)
is shared across the owner’s private repositories; it is not a separate allowance per repo.

`make health` audits the live GitHub receipts, local launchd log and remote budget journal
without calling The Odds API. The timestamped [health snapshot](results/forward_health.json)
reports only observed log coverage, not an uptime guarantee. The dashboard refreshes with
each `cll report`: forecast count, paper-bet count and settled CLV sample are distinct.
An empty performance panel means no eligible observations. Current model development is
closed for this registered pilot: the market-anchored blend already includes time-decayed
Dixon–Coles features. A new variant requires a separate protocol and validation-only
selection; the evaluated historical test and growing forward ledger cannot guide tuning.
Local CI audits are read-only; per-push receipts are ignored to avoid dirtying runner checkouts.

## Provenance

| Number / claim | Result file | Command | Commit |
|---|---|---|---|
| Historical row count / coverage | [data_quality.json](results/data_quality.json), [manifest](data/manifest.jsonl) | `cll download` (local only) | `c297fa0`; processed SHA in result |
| All eight validation candidates | [validation.json](results/validation.json) | `cll features`; `cll backtest --stage validation` | `source_commit` = `c297fa0` |
| Original held-out scores, CLV quantiles, P&L, DSR arithmetic | [test.json](results/test.json) | `cll features --stage test`; `cll backtest --stage test` | `source_commit` = `7c16ca0`; original `forward-v1` |
| Calibration bins, paths, paired loss quantiles | [historical_analysis.json](results/historical_analysis.json) | `cll research-report` (local saved predictions) | `source_commit` in result |
| Corrected missingness, pending stakes, DSR guard, replay agreement | [review_corrections.json](results/review_corrections.json) | `cll replay --output-dir runs/full_replay --rebuild-features` | `source_commit` and implementation hashes in result |
| Failed inference candidates | [candidate 1](results/null_calibration_candidate1.json), [candidate 2](results/null_calibration.json) | `python scripts/calibrate_inference.py` (see ITERATIONS for flags) | Source and implementation hashes in results |
| Planning power / insufficiency | [power_analysis.json](results/power_analysis.json) | Extract selected `power` from validation/test reports | Same source commits as reports above |
| Exact forward parameters / identity coverage | [fitted_model.json](config/fitted_model.json), [activation](results/forward_activation.json) | `cll prepare-forward`; exact identity check | `source_commit` and artifact SHA; frozen in `forward-v1.1` and `forward-v1.2` |
| API availability / credits | [api_smoke.json](results/api_smoke.json), [usage](data/api_usage.json) | Client `/events` and `/odds` smoke checks | `c297fa0`; response hashes in API manifest |
| Forward counts, CLV, P&L, gap/benchmark mix | [forward.json](results/forward.json) | `cll report` | `source_commit` in each result; ledger links runtime/registration SHAs |
| Backtest vs forward | [comparison.json](results/comparison.json) | `cll report` | `source_commit` in result |
| Live forward receipt coverage, launchd cadence and credit headroom | [forward_health.json](results/forward_health.json) | `make health` (no provider calls) | Source commit and ledger digest in result |
| Mac installation, real provider calls, push and same-hour deduplication | [local_runner.json](results/local_runner.json) | `python ops/install_launchd.py`; launchd cycle; local fallback probe | Runtime and publication SHAs in receipt |
| CI, audits, genuine schedule events | [actions_evidence.json](results/actions_evidence.json), [schedule check](results/schedule_check.json) | `cll actions-evidence`; `make verify` | Each run's `headSha`, server time and URL |
| Required tests / code checks | [engineering.json](results/engineering.json) | `make check test` | Source revision and environment in result |

## Limits and interpretation

- The held-out point estimates do not beat the closing line. Two selected bets and two
  dates do not support calibrated CLV inference. The original percentile endpoints are
  descriptive only; neither synthetic HAC candidate passed the calibration screen. The near-market blend
  usually abstains; thousands of forecasts do not become thousands of independent bets.
  Empty forward plots show missing observations, not a zero-return experiment.
- Two schema-previewed test fixtures are prospectively excluded from primary held-out
  metrics. No fitting or model selection used them; the full season is not fully blinded.
  Exact identifiers and the exception are recorded in `docs/source_review.json`.
- CSV prices are periodically captured snapshots. Historical decision times and result
  availability are proxies. Forward snapshots also do not prove an executable bookmaker
  price. Forward exchange paper P&L deducts 2% of winnings; liquidity, limits and slippage are unmodeled.
- Raw CLV across B365 and AvgC can reflect different margins. De-vigged CLV and same-book
  closing CLV are secondary checks. Positive CLV alone cannot establish profitable execution.
- Date clustering reduces effective sample size. Bootstrap quantiles and power calculations
  remain descriptive with assumptions. DSR is NOT_ESTIMABLE below 30 nonzero return days
  and 60 calendar days; its old arithmetic is retained only in source artifacts; no number of matches guarantees
  an edge. Lower-division/draw splits are descriptive, not another selection opportunity.
- GitHub receipts bound when ledger content existed on GitHub. Hash chaining exposes edits
  against retained history; an owner can still delete history or workflows. Private evidence
  requires reviewer access. Retain external receipts and clones; do not call this immutable.
- Hosted schedules can be delayed. Deadline checks reject late batches, and later verification
  fails any forecast lacking an on-time server receipt. No forecast is backfilled or backdated.

## Prior art

[Dixon & Coles (1997)](https://doi.org/10.1111/1467-9876.00065) motivates score modeling;
[Kaunitz, Zhong & Kreiner (2017)](https://arxiv.org/abs/1710.02824) studies market-based
football pricing; [Buchdahl's closing-line discussion](https://football-data.co.uk/blog/closing_odds.php)
motivates the benchmark. [Bailey & López de Prado (2014)](https://www.davidhbailey.com/dhbpapers/deflated-sharpe.pdf)
motivates the secondary multiple-trial Sharpe correction. None establishes that this model
has an edge. Bibliographic and licence details are in the third-party notices.

Copyright Nicolas Coquelet. Code: [MIT](LICENSE). Data and dependencies:
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
