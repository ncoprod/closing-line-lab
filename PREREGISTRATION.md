# Forward protocol v1

**Status: FROZEN by the annotated `forward-v1` tag, created prospectively on 29 October 2026.**
The tag contains this protocol, exact scientific code, configs, validation and selection.
No forecasts may be emitted until it exists. A fitted parameter export follows the frozen
test evaluation and is committed before the first forecast. No test/forward tuning is allowed.

Selected model: market-anchored multinomial logistic blend; minimum edge 0.05.
Validation: 11486 matched closing-price observations, log loss
1.0057639497705855 versus closing 1.002834479064554.
The 4 selected paper bets have mean log CLV -0.0398891288028935,
95% date-block CI [-0.08678290542845579, 0.016520650702510617]. This is not positive-edge evidence.
The calibration target (gap at most 0.01 nats) is met; no further scientific tuning occurs.
The sparse selected bets imply weak power for the planned forward window. Retain the rule
and report inconclusive results if insufficient bets accrue. Selection and validation hashes
are bound in results/selection.json. No held-out score was inspected before freezing.

## Hypothesis and window

Primary hypothesis: the unweighted mean `log(raw_odds_taken / raw_closing_odds)` is positive
on all eligible, settled paper bets with an observed close. The planned window is 29 October
2026 UTC through 29 January 2027 exclusive. Report the actual first forecast; never backfill
missed days. Scoring can continue afterward. No performance-based stopping or extension.

Report mean CLV and a 95% percentile bootstrap CI, resampling UTC kickoff dates with all
bets on a sampled date retained (5,000 resamples; seed 20261029). Evidence requires the lower
endpoint above zero. This is more conservative than a one-sided 5% test. Bets/matches are
not assumed independent. Report missing closes, unresolved results and voids explicitly.

## Data split and population

Historical: top two divisions in England, Germany, Italy, Spain and France (E0/E1, D1/D2,
I1/I2, SP1/SP2, F1/F2), 2012/13 onward. One owner-authorized local private research download,
SHA-256 manifest, no raw/processed row publication, no hosted downloads or training. Current
partial-season rows are used only for the initial forward parameter export, after freezing.

Forward: EPL (`soccer_epl`, E0) and Championship (`soccer_efl_champ`, E1), chosen for coverage,
English top/lower-tier comparison and free-API budget before inspecting strategy returns.
The official The Odds API v4 supplies events, EU/h2h odds and results. Missing/unmapped teams
are skipped visibly; no fuzzy-name matching or outcome-driven league changes.

## Schedule, budget and benchmark

GitHub Actions polls hourly at minute 17 UTC, best effort. Free `/events` calls discover
kickoffs. A league-wide `/odds?regions=eu&markets=h2h&oddsFormat=decimal` request costs one
credit and is made only when a decision or closing observation is due. Decisions use the
first complete fresh quote observed 23–25 hours before kickoff; a missed window is skipped.
No forecast replacement or price chasing. The first eligible observation wins.

Closing capture is attempted when a recorded forecast is 15–75 minutes before kickoff.
Hourly scheduling normally provides a snapshot within that interval; delays can cause a
missing close. Publication checks require at least 15 minutes remaining at both commit and
push. The **closing line is the last recorded pre-kickoff snapshot**, not a literal final
exchange price. It must itself have a pre-kickoff GitHub server receipt. Save its bookmaker,
source update time, retrieval time, hash and actual snapshot-to-kickoff gap. Source update
times permit at most five seconds of clock lead; quotes older than 30 minutes are rejected.
The actual source-update-to-kickoff gap may therefore be longer than the retrieval gap.

Fixed closing priority: `betfair_ex_eu`, then `pinnacle`; no other fallback. Within the last
snapshot use the first available complete fresh triple in that order. Decision priority:
`pinnacle`, then `betfair_ex_eu`. No best-price shopping. Record both raw and effective odds.
A fixed 2% exchange commission on winnings reduces decision odds for edge/staking and P&L;
primary CLV uses the raw displayed quotes. All prices are indicative; depth/execution is
unverified. Pinnacle's API listing warns of possible public-site delivery delays.

`/scores?daysFrom=3` costs two credits. Poll at most once per league/UTC day after 07:00,
only with unresolved forecasts at least three hours after kickoff. Delayed/missing scores
remain unresolved. The three-day provider window can leave an outage permanently unresolved.

Budget: 500 free credits per provider billing month; **400 local reserved credits per UTC
calendar month**, including smoke tests and conservative charges for failed requests.
Additionally, never issue a paid call that would reduce the last reported provider balance
below 100 credits. Quota headers `x-requests-last/used/remaining` are saved and `/events`
refreshes the provider balance without charge. The reserve also handles non-calendar billing
resets. Worst-case accepted spend is bounded by those guards, not by an assumed fixture count.
When capped, skip requests in the fixed configured league order and report lost coverage.
Never backfill a missing pre-kickoff quote from paid historical data or after-match sources.
Typical demand depends on distinct kickoff batches; this plan does not promise all matches.
Hourly single-job starts imply a 744-minute baseline in a 31-day month if each rounds to one
runner minute; audits/CI add minutes. Measure actual durations against the 2,000-minute plan.

## Model, validation and frozen forward parameters

Exact values are in config/strategy.json. Historical features use:

- Dixon–Coles: exponentially weighted Poisson likelihood with the four low-score correction
  factors, half-life 365 days, window 1,095 days, monthly UTC-month-start refits. Centered
  attack/defence effects, ridge 0.02, rho in [-0.1, 0], log rates clipped to [-2, 2], normalized
  0–30 goal grid, at least 100 past league matches. Optimizer failure stops evaluation.
- Elo: K=20, home advantage 75, Davidson draw strength 0.7, initial 1500, per-league ratings,
  no seasonal reset. Update only results available strictly before the decision.
- Market: proportional de-vig of B365 pre-closing odds.
- Blend: multinomial logistic residuals anchored to that market. Shared DC/Elo residual
  weights and three intercepts, ridge 10, bounds [-1, 1]. Each July 1 fit earlier completed
  seasons only, minimum 1,000 rows. No current-season coefficient optimization.

Eight declared validation candidates: market/DC/Elo/blend × edge 0.03/0.05. Compare only
2022/23–2024/25; features begin 2015/16 after initial history. Select lowest outcome log loss,
exact ties choose the higher edge threshold. Thresholds do not change forecasts, so this
rule intentionally does not select a threshold on CLV or P&L. No league/side/lead-time search.
Report every candidate, including negative results, with trial IDs and source revision.

Historical decision time is a 24-hour-before-kickoff proxy; known-time results become
available after 12 hours, date-only results after 36. CSV odds have no proven quote/publication
timestamps. This is strictly as-of with respect to the stated result-availability assumptions,
not a reconstruction of historically executable opening odds. Closing/current outcomes are
excluded from features. The closing baseline is AvgC, with B365C and de-vigged sensitivities.
PS/PSC are excluded due to the football-data feed warning after 23 July 2025.

2025/26 is evaluated once, **after the tag exists**, and cannot choose any strategy change.
Two schema-previewed E0 rows were displayed before fitting. Their predeclared IDs are excluded
from primary test metrics (config/strategy.json; docs/source_review.json). The full season
is therefore not completely blinded. Earlier test outcomes may enter later test features
under the same fixed as-of rule, but test aggregate results never guide fitting choices.

After the frozen test evaluation, export DC/Elo parameters using only results available
at export; retain the pre-test blend coefficients fitted through 2024/25. Export no training
rows. Commit the artifact/hash before the first forecast. **All forward parameters stay fixed
for v1**: no hosted football-data access or retraining. This deliberately differs from monthly
DC/as-of Elo historical updates and can cause model drift; the comparison must state it.
Market features are the actual decision snapshot (Pinnacle/Betfair rather than B365), another
source shift. Neither difference may be tuned using test or forward results.

## Paper account and audit

Choose the eligible side maximizing `p * effective_odds - 1`, ties H/D/A, odds [1.2, 10],
edge at least the selected threshold. Quarter Kelly: `min(0.01, 0.25*edge/(odds-1))` of equity
valued at cost. Start at 100 fictional units; aggregate open exposure cap 10%; never spend
unavailable cash. Commission-adjusted effective odds determine P&L; raw odds determine CLV.
No money, deposits, bookmaker accounts, orders or replenishment.

Forecasts and closing observations append to a SHA-256 chain and are committed/pushed
before kickoff. Audit run server created_at/head_sha binds the exact ledger hashes to an
external upper timestamp. Git author dates alone never qualify. Verification failure stops
the pipeline; records are not erased or backdated. Repository owners can delete history;
retain receipts/clones and describe this as tamper-evident, not immutable.

Full-time API results settle the original selection. Changed kickoffs produce a visible
VOID_SCHEDULE_CHANGED with zero profit. Missing closing triples still allow P&L settlement,
but CLV is missing and counted. No favorable imputation of absent results or cancelled games.

## Planned analysis

Outcome log loss and summed multiclass Brier vs de-vigged closing probabilities on identical
complete-price matches; closing-distribution cross entropy/probability squared distance are
market-distance measures, separate from result accuracy. Ask whether the model actually
beats closing outcome log loss. Historical raw CLV includes cross-book margin differences.
Report secondary `log(raw_taken * p_close_devig)` and same-book raw CLV when available.

Paper P&L uses recorded stakes/effective prices, with no liquidity or fill claim. Report
calibration curves (H/D/A, quantile bins), date-block CLV intervals, missingness, benchmark
mix and actual source/snapshot gaps. League/draw/lead-time splits are descriptive uncorrected
comparisons and cannot change v1. Historical early-week quote timing is unknowable.

DSR: unannualized daily account returns including inactive days, skewness/raw kurtosis,
Bailey–López de Prado expected-maximum correction; empirical trial-Sharpe variance with
null-SE floor. Count every logged iteration/candidate/failed attempt conservatively. Trial
and daily independence are imperfect; DSR is secondary descriptive evidence, not a CLV test.

Power: normal approximation, one-sided 5%, 80% power, observed CLV variance and UTC-date
cluster design effect floored at one, for 5/10/25/50/100 log-CLV basis points. Without enough
observations report NOT_ESTIMABLE. The primary two-sided 95% lower-CI rule requires more
power. Compare historical vs forward with coverage, source, cadence and frozen-model drift
explicit. Publish a positive, negative or inconclusive result without changing the protocol.

## Prospective identity amendment — `forward-v1.1`

Before any forward forecast, a coverage check found three exact API/football-data name
differences: Bolton Wanderers → Bolton, Cardiff City → Cardiff, Lincoln City → Lincoln.
Add those aliases only. No league, forecast formula, parameter, staking rule, threshold,
quote window or benchmark priority changes. No test re-evaluation or outcome-based tuning.
The model artifact SHA remains the one produced under the original v1 procedure.

The immutable `forward-v1` tag remains the original pre-test registration. The separate
annotated `forward-v1.1` tag freezes these identity corrections, the active tag reference
and exported parameter artifact before forward recording. Test metrics belong to original
v1 and are not relabeled as an untouched test of the amended runtime. Forecast records
name the active registration commit. The verifier's scientific-file comparison now uses
that active tag and also freezes the parameter artifact. This is an explicit prospective
amendment, not a moved tag or an invisible post-test model change.

Operational job layout: hourly forecast jobs emit a scoring-due flag; a separate scoring
job runs only when needed, under the same at-most-once-per-league/day rule. This changes
no quote window, API credit cap, model or staking rule. Its additional runner-minute budget
is normally at most two short scoring jobs/day; failed or budget-blocked attempts can add
jobs. Source data is never fetched from football-data.

## Prospective retry-accounting amendment — `forward-v1.2`

Before any forward record, reserve the provider remaining balance as well as the local
monthly counter before transmitting a paid request. A failed/ambiguous request might have
consumed a credit; a retry must not use the same stale balance near the 100-credit reserve.
A regression test checks one failed request at balance 101 stops further paid attempts.
The original v1/v1.1 tags stay intact. No forecast formula, fitted coefficient, threshold,
benchmark, window or staking change; no test re-evaluation. This operational correction
and active tag reference are frozen in v1.2. The artifact remains unchanged. Successful
responses still replace the conservative estimate with actual provider quota headers.
