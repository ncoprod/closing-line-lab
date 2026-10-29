# Data notice

The MIT licence covers our code, not match data or odds. Credit:
[football-data.co.uk](https://football-data.co.uk/) and [The Odds API](https://the-odds-api.com/).
Neither source is an open-data licence. No non-commercial third-party model is used.

## Local historical research — owner decision, 29 October 2026

The [football-data terms](https://football-data.co.uk/data.php) state that data is
“intended for private individuals only”. They restrict commercial uses and automated
training products. The owner authorized one local download for his private, non-commercial
research; this records his use decision, not separate written permission from the provider.

The downloader requests only the ten specified league/season CSVs sequentially, pausing
one second between new downloads. Existing hashed files are reused and refresh is disabled.
The latest partial season is downloaded once to fit the initial forward model, never polled.
`data/raw/`, `data/processed/` and row-level historical predictions/bets remain gitignored.
**Never force-add those files.** GitHub Actions explicitly cannot call this downloader or
train on football-data rows. No football-data file is cached on hosted runners.

Only `data/manifest.jsonl` (URLs, retrieval times, byte sizes, SHA-256 hashes), aggregate
metrics/coverage, figures and fitted coefficients are committed. Other researchers run the
script themselves. Upstream CSVs can change; matching the manifest requires privately
retaining the original local cache. Aggregate outputs alone do not permit exact public replay.

Non-C CSV odds are pre-closing snapshots, without verified opening or availability times.
Known-time results use a conservative 12-hour availability lag; date-only rows use 36 hours.
Dates/times follow Europe/London including DST. These assumptions cannot prove historical
execution. AvgC is the historical closing reference; B365C and de-vigged CLV are sensitivities.
The provider's Pinnacle stale-feed warning since 2025-07-23 excludes its PS/PSC columns from
modeling and benchmark selection. That warning concerns this provider's feed.

## Forward research — The Odds API

The [terms](https://the-odds-api.com/terms-and-conditions.html), updated 2026-08-31, allow
storage, research, analytics, derived values and model training. They prohibit redistribution
as a standalone raw-data product. This repository publishes a research model, selected
forecast/paper-trade audit records and analysis, not a general odds feed. Complete responses
are stored in ignored `data/api_raw/`; hosted responses are ephemeral, identified by the
committed `data/api_manifest.jsonl`. Privately retain raw responses for exact source replay.

The key is an environment/Actions secret, excluded from URLs in manifests and from errors.
No accounts are created by the project. The client uses only events, odds and scores GET
endpoints. The 400-credit local cap plus a 100-credit provider reserve protects the 500-credit
free allocation, including conservative reservations for failed requests. Actual quota
headers are recorded. Pricing and terms can change; review them before a later protocol.

Betfair EU is the preferred closing benchmark, Pinnacle the fixed fallback. Pinnacle's API
listing notes possible public-website delays. Quotes older than 30 minutes are rejected; a measured source-clock lead of at most five seconds is tolerated and recorded.
The benchmark is the last *observed pre-kickoff snapshot*, not a literal exchange close;
snapshot retrieval and source-update gaps are both retained. These indicative prices do
not establish exchange depth, executable stakes or real-world profitability.

Synthetic test objects and the attributed, trimmed documentation transport example are
never research observations. ClubElo and the earlier football-forecast-lab code are not used.
