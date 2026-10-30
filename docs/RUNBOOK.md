# Reproduce and operate

Paper only. No account creation, bet-placement endpoint or payments exist. Python 3.12/uv:
`make install`, `make check test`, `make verify`. Tests use synthetic data and a trimmed,
attributed API documentation example. Tests never download historical provider data.

## Historical authoring (already complete)

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

## Reviewer replay on main

Do not run the authoring selection sequence again. With the matching private cache:
`OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 uv run cll replay --output-dir runs/reviewer-replay --rebuild-features`.
Compare the isolated replay.json with results/review_corrections.json. Registered artifacts
and tags are preserved; row-level replay files stay ignored. Without the cache, unit tests,
ledger verification and aggregate paper regeneration remain available, but exact historical
feature replay does not. Never delete tags or bypass the holdout guards to reproduce a run.

## Forward collection

The owner supplies ODDS_API_KEY as a GitHub Actions secret. Never print it or put it in
command arguments. The Mac `:05` primary and GitHub `:17` UTC fallback use `ops/run_cycle.py`.
Install with `uv run python ops/install_launchd.py`; see README for credentials, logs and recovery.
The shared api-budget lease serializes runners; the completed UTC hour suppresses duplicate cycles.
Any failed cycle retains its lease until manual reconciliation to prevent re-spending on unpublished data.
The pipeline checks the key, active v1.3 runtime tag and model availability.
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

The authoritative journal is data/api_reservations.json on the dedicated api-budget branch.
A GitHub Contents compare-and-swap commit reserves credits before every paid transmission;
a second commit records quota headers. Main's api_usage.json is only a mirror. Unavailable
remote writes prevent HTTP; a pending ambiguous reservation blocks all subsequent paid calls,
even after runner loss or provider reset. Paid calls have no automatic retry. Free events
retain bounded backoff retries. CI/audit push triggers are restricted to main to avoid billing
runner minutes for accounting commits.

Manual reconciliation after an ambiguous call: keep collection paused; read the remote
journal and compare the provider's current quota via free events/account dashboard. Retain
the month charge (never refund ambiguous reservations), update remaining/provider_used from
the provider, and clear pending only after resolving whether another runner can still send
that request. Commit the reconciled state on api-budget with the same SHA-based Contents API
update. Run both staged and full-history secret scans before publication. Never publish
failed/late forecast working files as accounting recovery; restart from fresh main afterward.

GitHub remains configured hourly, but skips an already completed UTC hour. Scoring runs
within the same lease only when due, after forecast publication, at most once per league/day.
The Mac must be logged in, awake and online. Both runners share the original credit cap and
provider reserve; the added scheduler does not grant extra credits. Review hosted minutes
and account availability. CI and audit jobs were refused by an account billing/spending
restriction at the recorded check; see results/engineering.json. Schedules can be delayed
or dropped. No lateness is hidden.

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

## End of the registered window

New forecasts stop at the configured forward_end (29 January 2027, exclusive). Allow
closing collection for decisions already inside the window, then settlement/reporting
until resolved or explicitly unavailable. Inclusion is by decision time, so an eligible
28 January decision may have a 29 January kickoff. New decisions outside the window are
forbidden; existing forecasts retain their closing window. Unresolved bets remain exposure. Once
the final analysis is saved and scoring is no longer useful, stop the hourly runner cost
with `gh workflow disable paper.yml -R ncoprod/closing-line-lab`. Retain the audit workflow,
ledger history and verification artifacts. The cron does not disable itself automatically.
