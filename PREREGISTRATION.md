# Forward protocol v1

**Status: DRAFT, NOT FROZEN.** Source permission is unresolved; validation has not run.
The `forward-v1` tag must not be created until the selection, validation artifacts, this
protocol and the exact runtime are committed. A draft protocol is not a pre-registered
forward result. No forward forecast can be emitted without that tag and matching files.

## Question and window

Primary hypothesis: mean `log(odds_taken / AvgC_selected)` exceeds zero on all eligible,
settled forward paper bets. The planned recording window is 29 October 2026 (UTC) through
29 January 2027 (exclusive). The actual first forecast is reported; missed days are not
backfilled. Settlement may continue after the window. If permission delays prevent a
meaningful window, publish a new dated protocol before any forecast; never backdate v1.

The unit is a single 1X2 selection per match. Matches and bets are not assumed independent.
The primary estimate is the unweighted mean bet CLV, with a 95% percentile bootstrap CI
over UTC kickoff calendar dates (5,000 resamples, seed 20261029). Evidence for the directional
hypothesis requires the lower endpoint of this two-sided interval to exceed zero. This is
more conservative than a one-sided 5% test. No interim significance stopping or extension
based on performance. Report every missing close, unresolved match and void separately.

## Population and snapshots

E0/E1, D1/D2, I1/I2, SP1/SP2, F1/F2: the top two tiers in England, Germany, Italy, Spain
and France. All are retained irrespective of validation or forward profitability. Known
kickoff times, all three B365 pre-closing decimal odds, and adequate model history are
required. Quote source: the retrieved `fixtures.csv` snapshot. Treat these as indicative
paper prices; no real-time executable quote or opening-time claim is made.

First observation only, between 30 minutes and 96 hours before the listed kickoff; never
replace a prior forecast or chase a later price. Reject absent Last-Modified headers,
future-dated sources and snapshots last modified more than 96 hours ago. Forecasts may
be recorded even when the bet rule abstains. Save snapshot hashes, retrieval time and
the decision/recording timestamps. Calendar times use Europe/London and convert to UTC.

## Frozen model and training procedure

Exact numeric settings live in `config/strategy.json`; the selected model and threshold
live in `results/selection.json`, both inside the eventual `forward-v1` tag.

- Dixon–Coles: weighted Poisson score likelihood with the four low-score correction
  factors; 365-day half-life, 1,095-day window, monthly refits at UTC month start. Centered
  attack/defence effects, ridge 0.02; rho restricted to [-0.1, 0]. Log goal rates clipped
  to [-2, 2]; probabilities normalize a 0–30 goal grid. Promoted/unseen teams use neutral
  effects. At least 100 prior matches in the league. Optimizer failure stops the run.
- Elo: K=20, home advantage 75 rating points, Davidson draw strength 0.7. New teams start
  at 1500; ratings remain per league. No season reset. Update only as-of available results.
- Blend: multinomial logistic residuals anchored on proportionally de-vigged B365
  probabilities. Shared DC and Elo residual weights and three outcome intercepts; ridge
  10, parameter bounds [-1, 1]. Refit each July 1 using earlier completed seasons, with
  at least 1,000 training rows. No current-season coefficient optimization.
- Candidate market baseline: proportionally de-vigged B365 probabilities.

Historical features use a decision proxy 24 hours before listed kickoff. Known-time results
become available after 12 hours, date-only results after 36 hours. This cannot reconstruct
unknown publication or quote times. Forward features additionally require a downloaded
source snapshot present at the decision. Closing fields, results after cutoff, xG, full-time
match statistics and current match outcomes are excluded from model inputs.

Eight candidates are declared before evaluation: four models × edge thresholds 0.03 and
0.05. Train/calibrate on earlier seasons, compare on 2022/23–2024/25 only. Select lowest
validation outcome log loss; exact ties choose the higher threshold (0.05). Since thresholds
do not alter forecasts, this intentionally does not optimize threshold on CLV or P&L.
2012/13 onward supplies training history; feature evaluation begins in 2015/16. July refits
on prior validation seasons follow the same predetermined expanding training procedure.

2025/26 is the single held-out season. Open it only after the strategy tag exists; evaluate
once and preserve its predictions. Earlier test outcomes may enter later test *features*
strictly as-of, and forward training by the frozen expanding procedure. Test-season or
forward aggregate results never choose a model, threshold, league or parameter.

## Paper selection and account

At decision time choose the eligible side maximizing `p * B365_odds - 1`, with H/D/A as
the deterministic tie order. Eligible odds lie in [1.2, 10]. Require the selected threshold.
Stake fraction = `min(0.01, 0.25 * (p*odds-1)/(odds-1))`, applied to paper account equity
valued at cost. Start at 100 fictional units; cap aggregate open stakes at 10% of that
equity and do not spend unavailable cash. No deposit, leverage or bankroll replenishment.
Settle only after official full-time results are present and the availability lag has passed.

Publication requires at least 15 minutes remaining at both commit and push checks. A
GitHub audit-workflow server receipt must contain the forecast hash at its `head_sha`
before kickoff. A network stall can still cause late publication: verify it, flag failure,
never erase or rewrite the forecast, and exclude it from claimed pre-kickoff evidence.
The pipeline must stop on verification failure. Git author dates are insufficient proof.

If result data changes the kickoff from the recorded schedule, append a visible
`VOID_SCHEDULE_CHANGED` event with zero paper profit; do not silently move its timestamp.
Missing closing triples stay pending and remain in the denominator/coverage table.
Unresolved or cancelled matches stay pending until a documented append-only adjudication;
there is no automatic favorable imputation. Report the number still unresolved at analysis.

## Analysis and reporting

Report outcome log loss and multiclass Brier (sum, not mean across classes), on the same
complete-price matches as the closing baseline. Also report closing-distribution cross
entropy and squared probability distance; these measure distance to market, not accuracy
against results. A base-rate comparison asks whether log loss improves on the close.

Primary CLV compares the snapshot B365 quote with `AvgC` (raw odds). Its value includes
cross-book margin differences. Secondary checks: `log(odds_taken * p_close_devig)` and
same-book `B365C` CLV. Pinnacle is excluded because the provider warns of stale prices.
Profit uses the recorded indicative odds and actual stakes; it is never called executable
profit. Report commission-free bookmaker paper P&L, date-block CLV intervals and coverage.

DSR uses unannualized daily paper-account returns, sample skewness/raw kurtosis and the
expected-maximum Sharpe correction of Bailey & López de Prado. Count all logged candidate
evaluations and iteration attempts, including failed attempts conservatively. The variance
of trial Sharpes has a null-SE floor. Independence assumptions are imperfect; DSR is a
descriptive secondary diagnostic, not the CLV hypothesis test. Log every attempted variant
and failed run in `results/trials.jsonl`; no invisible grid search.

Power: normal approximation for a one-sided 5% test with 80% power, using observed CLV
variance and the date-cluster design effect (floored at one), for 5/10/25/50/100 log-CLV bp.
Without observed CLV the answer is NOT_ESTIMABLE. The actual conservative primary CI rule
needs more power than that planning approximation; report this difference explicitly.

Calibration: home/draw/away reliability plots with quantile bins. League, outcome-side
and observed lead-time analyses are descriptive, uncorrected multiple comparisons, and
cannot alter v1. Historical data has no quote-time lead-time measurement, so no early-week
advantage can be claimed from historical CSV rows. Compare backtest and forward with these
market, availability, source-age and selection differences explicit. Publish negative results.
