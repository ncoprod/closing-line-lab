# Reproduce and operate

Paper only. No account creation, bet-placement endpoint or payments exist. Python 3.12/uv:
`make install`, `make check test`, `make verify`. Tests use synthetic data and a trimmed,
attributed API documentation example. Tests never download historical provider data.

## Local research

Read DATA_NOTICE.md. `make download` is the owner's authorized one-off private download:
ten leagues, 2012/13 through the current partial season, sequential with a one-second delay.
Cache/processed rows and row-level historical predictions/bets stay local and ignored.
Refresh is disabled, including for the partial current season. Never force-add these files.
If a cache is lost, a mutable URL may no longer reproduce the manifest; privately retain it.

1. `make features`: chronological monthly Dixon–Coles, as-of Elo and pre-closing market
   features for training/validation only. Inspect aggregate `results/data_quality.json`.
2. Commit the declared candidates/code/protocol before `make backtest`. Every evaluation
   and iteration is appended to `results/trials.jsonl`. Read every candidate report.
3. `make select`: deterministic validation log-loss selection, higher threshold on ties.
   If the target fails, two focused training/validation changes maximum, then explain the gap.
4. Finalize PREREGISTRATION.md, commit/push, create and push annotated `forward-v1`.
   Never move this tag. It freezes scientific code, config, selection and validation hash.
5. `uv run cll features --stage test` and `uv run cll backtest --stage test`, once.
   The latter refuses to overwrite results. Never tune using these metrics.
6. `uv run cll prepare-forward`: once, locally, after the frozen test evaluation. Export
   fitted coefficients/ratings only. DC/Elo use results available at export; blend uses
   pre-test labels only. Parameters stay fixed throughout v1. No hosted retraining.
7. Commit/push the parameter artifact before any forward forecast, then dispatch paper.yml.

Long commands log to ignored `runs/` and resume at completed file/stage boundaries. Keep
BLAS at one thread on the shared machine. These fits do not require heavy-ML locks.

## Hosted collection

The owner supplies ODDS_API_KEY as a GitHub Actions secret. Never print it or put it in
command arguments. The hourly `:17` UTC job first checks key, active v1.2 runtime tag and model availability.
It never downloads, restores or trains on football-data rows. Complete API responses are
not committed. API hashes, sanitized endpoint parameters and quota headers are retained.

Free `/events` discovers EPL/Championship schedules. A league-wide EU/h2h `/odds` request
is made only for a new decision at 23–25 hours or a recorded forecast at 15–75 minutes
before kickoff. Quotes over 30 minutes old are rejected. Near-kickoff snapshots are added
before kickoff too; scoring selects the last recorded one, never an after-match price.
Book priority, exchange commission and all limits are in config/forward.json.

`/scores?daysFrom=3` runs at most once per league/day after 07:00 UTC, only with unresolved
matches older than three hours. Missing scores remain unresolved. Missing closes do not
prevent P&L settlement; they prevent CLV/calibration scoring and are counted explicitly.
Changed kickoffs are visibly voided. Cancellations are never assigned favorable results.

Hard caps: 400 reserved credits per UTC calendar month and provider remaining balance at
least 100. Reserve costs before transmission, including ambiguous/failed requests. Provider
billing resets can differ from calendar months; the remaining-balance guard handles that.
Requests stop when either guard binds; coverage losses are reported, never backfilled.
The two live odds smoke calls count against this same budget.

At 24 short jobs/day the 31-day baseline is 744 one-minute runner jobs. Dependency caches
keep the forecast job short; a separate scoring job starts only when scores are due,
at most once per league/day. With normally completed requests that adds at most 62 short
scoring jobs in a 31-day month; failed/budget-blocked attempts can start additional jobs,
before audit and CI minutes. This is a planning estimate, not a measured billing guarantee. Review actual
durations and remaining minutes. Schedules can be delayed or dropped. No lateness is hidden.

## Publication and audit

`cll forward` appends forecasts and closing observations. `cll publish` requires current
main, an unchanged prior ledger prefix and at least 15 minutes remaining at commit and push.
It runs the owner's required secret scan, pushes without force/rebase and dispatches audit.
`cll score` appends results; `cll publish --settlements-only` cannot publish new forecasts.

`make verify` replays the chain, prices, stakes, CLV, P&L and pre-kickoff timing. Each
forecast and closing snapshot must occur in a ledger blob bound to a GitHub audit run's
server-side created_at/head_sha before kickoff. Local author dates do not qualify.
GITHUB_TOKEN pushes do not trigger push workflows, so the explicit audit dispatch matters.
Retain run URLs/artifacts and independent clones. Owners can delete history/runs; this is
tamper-evident, not trustless or immutable. Private evidence needs reviewer access.

Refresh evidence with `uv run cll actions-evidence`. A manual dispatch is not a scheduled
run; a readiness-gated schedule success is not proof of an actual forecast. Missing data,
late publication and verifier failures stay visible and stop claimed timing verification.
