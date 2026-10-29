# Reproduce and operate

No bookmaker credentials, API key, account, bet-placement endpoint or payment integration
exists. Only GitHub authentication is used to publish/audit paper records.

```sh
make install
make check test
make verify
uv run cll report
```

With no forecasts `make verify` returns `NO_FORECASTS`, not proof of a working forward run.
All tests use local synthetic fixtures; none quietly downloads restricted provider data.

## Obtain source permission first

Read DATA_NOTICE.md and obtain permission that covers automated research, training,
GitHub-hosted collection and any intended redistribution. Record a non-sensitive reference
and exact scope in `config/data_permission.json`. Collection and training are separate
flags; keep redistribution false unless permitted. Do not interpret booleans as a licence.
The scheduled workflow checks the gate before installing dependencies or calling the source.

## Research sequence

Long jobs should be started in the background with ignored logs, e.g.:

```sh
mkdir -p runs
nohup uv run cll download > runs/download.log 2>&1 &
```

Downloads are resumable at the file level using a content-addressed cache and manifest.
The active season refreshes; completed seasons use the exact cached snapshot. If a raw
cache has been lost and the remote file changed, the new hash is explicit; it is not an
exact reproduction of the original experiment. Restore the archived snapshot for replay.

1. `make download`: seasons 2012/13 through the current one, ten leagues. Inspect
   `results/data_quality.json`. A missing requested league/season is an error, not a silent
   exclusion. This may require a deliberate documented coverage revision before research.
2. `make features`: generates only pre-test features, with monthly DC and chronological
   Elo updates. Commit the fixed protocol/code before evaluating variants.
3. `make backtest`: eight validation-only model/threshold combinations. Read all reports,
   CLV missingness and diagnostics. Each trial is logged even if later optimization fails.
4. `make select`: deterministic validation log-loss selection. Update the iteration log.
   If the target fails, allow at most two focused validation changes, log every attempt,
   then freeze and report the residual gap rather than mining further.
5. If redistribution is permitted, `git add -f data/processed/` and archive the exact raw
   snapshots as well, within the permission scope. Otherwise do not claim full public
   data replay: privately retain snapshots and restore the GitHub Actions data cache.
6. Finalize PREREGISTRATION.md with the measured selection, actual freeze date and result
   paths. Change its status to FROZEN. Commit and push after the required secret scan.
   Create the annotated tag only now: `git tag -a forward-v1 -m 'Freeze forward protocol v1'`
   and `git push origin forward-v1`. Never move the tag or rewrite history.
7. Open the held-out season once: `uv run cll features --stage test`, then
   `uv run cll backtest --stage test`. The second command refuses to overwrite a test
   result. Saved predictions permit deterministic analysis without choosing a new strategy.
8. Prime `data/processed/forward_training.csv.gz` on the first permitted forward run.
   GitHub Actions caches raw/derived data. A cold cache may need a separate preparation run
   before the short forecast job; never let a slow fit excuse a late forecast.
9. `gh workflow run paper.yml --ref main`; inspect logs. A successful `schedule` event is
   separate from a manual dispatch. Refresh evidence with `uv run cll actions-evidence`.

The frozen runtime includes models, data transformations, betting rules, CLV, ledger and
publication code. Documentation/report-only edits are possible; a scientific runtime
change needs a new prospective protocol, not a patch to an existing claim.

## Ledger and publication

`cll forward` records first-observed pre-kickoff snapshots; `cll publish` accepts only
append-only ledger changes on an up-to-date main, checks deadlines twice, scans for secrets,
commits and pushes without force/rebase, then dispatches `audit.yml`.

GitHub's dispatch run `created_at` plus `head_sha` supplies an external upper bound on
when that exact ledger content existed. The verifier obtains runs from GitHub, reads each
run's ledger blob by SHA and requires a matching hash before kickoff. A locally selected
commit date never qualifies. `GITHUB_TOKEN` pushes do not trigger ordinary push workflows;
the explicit audit dispatch is required. Allow Actions to write repository contents and
dispatch workflows. The workflow token has only contents/actions scope, not bookmaker access.

If a push stalls beyond kickoff, the record stays visible and verification fails. Do not
delete it to restore a green badge. Recover by recording the incident and introducing a
prospectively defined protocol amendment; no such amendment is silently automated.
Missing closes remain pending. Replays must retain original forecasts and append settlements.

This is tamper-evident research, not an immutable trustless archive. A repository owner can
change workflows or delete history/runs. Retain external run URLs, artifact receipts and
independent clones. Private-repository timestamps become inspectable by reviewers with
access; they are not publicly auditable until the owner publishes the repo.

## Budget

Four cron triggers/day, two jobs when enabled, each with an eight-minute limit. Disabled
permission-gate runs take one short job. Cached uv and data minimize normal execution;
monthly cold-data research is not a cron job. The limits are failure bounds, not a promise
to fit the free minutes quota: measure actual billable durations before enabling. If
forecast+score averaged two runner minutes per trigger, the nominal monthly use would be
240 minutes (30 days), excluding CI/audits. Hosted schedules are best effort and can be late.

## Required pre-commit secret check

Run the owner's exact `git grep -nE` check from the task before every commit, including
research results. The publisher runs the equivalent pattern without logging matches.
Do not put secrets in config, source, result files, manifests or logs. No env dump is needed.
