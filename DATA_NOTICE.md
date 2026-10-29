# Data notice

Football results and odds are credited to [football-data.co.uk](https://football-data.co.uk/).
The MIT licence covers this repository's code, not third-party match data or odds.

## Terms review — 29 October 2026

The current [data page](https://football-data.co.uk/data.php) restricts use to private
individuals and excludes commercial or automated data-training products. No open-data
licence or permission to redistribute is established. This research involves automated
model fitting and a future public repository; attribution alone does not settle permission.
Collection, training and publication of provider data are therefore disabled pending
documented permission covering the intended use. This is an observed source constraint.

No provider dataset is included. Small synthetic fixtures used in tests are generated
locally and are never reported as research results. Initial terms/schema checks inspected
the provider's documentation and a few CSV header/sample lines; these are not a backtest.

`config/data_permission.json` records collection, training and redistribution separately.
An actual permission reference belongs in its `evidence` field; merely changing a boolean
does not establish permission. Do not commit private correspondence or personal data.

When permitted, `make download` uses the documented season CSV and fixtures endpoints.
Raw responses are cached by SHA-256 in ignored `data/raw/`; `data/manifest.jsonl` records
the URL, retrieval time, hash, size and Last-Modified header. Processed data is ignored
unless redistribution is explicitly allowed. If allowed, commit the exact processed
snapshot with `git add -f data/processed/` so a mutable upstream URL is not the only replay
path. If not allowed, reproducibility is conditional on access to the original snapshot;
the repository must state that limitation. A changed source response gets a new hash.

## Interpretation

- Odds without `C` are **pre-closing snapshots**, not timestamped opening prices.
  The [fixtures page](https://football-data.co.uk/matches.php) describes Friday/Tuesday
  collection. A retrieval timestamp cannot prove a quote remained executable at retrieval.
- `AvgC` is the primary closing reference. `B365C` is a same-book sensitivity check.
  BFE/BFEC, Max/MaxC and PS/PSC fields are retained when present; missing prices stay missing.
- The provider warns Pinnacle's feed has been systematically stale since 23 July 2025.
  Pinnacle fields are excluded from modeling and the primary benchmark.
- Times are interpreted as Europe/London, including DST. Historical files without a
  kickoff time use midnight for a conservative feature cutoff and a 36-hour result lag;
  these cannot qualify as timed forward forecasts. Known times use a 12-hour result lag.
  Actual historical result publication times are unavailable, so this is an assumption.
- Historical CLV and P&L are snapshot-based proxies. Forward paper quotes also remain
  indicative: no bookmaker access, exchange depth, liquidity or execution is verified.

Optional ClubElo is **not used**; its HTTP endpoint is not contacted.
