# Third-party notices

Original code: MIT, copyright Nicolas Coquelet. No pretrained weights, vendored source,
or code from `football-forecast-lab` is used. Models are independently implemented from their mathematical descriptions.

| Component | Licence / terms | Attribution and handling |
|---|---|---|
| football-data.co.uk results and odds | Proprietary source restrictions; no open-data licence established | Credit football-data.co.uk; one local private research download authorized by the owner; no raw/processed row redistribution or hosted collection. See DATA_NOTICE.md. |
| Dixon–Coles, Elo, offset multinomial logistic blend | Mathematical methods; implementations here MIT | Cite Dixon & Coles (1997); no external model code or weights copied. |
| NumPy | BSD-3-Clause; bundled notices include 0BSD, MIT, Zlib, CC0-1.0 | [Upstream LICENSE](https://github.com/numpy/numpy/blob/main/LICENSE.txt); installed distribution retains bundled notices. |
| pandas | BSD-3-Clause | [Upstream LICENSE](https://github.com/pandas-dev/pandas/blob/main/LICENSE). |
| SciPy | BSD-3-Clause with bundled third-party notices | [Upstream LICENSE](https://github.com/scipy/scipy/blob/main/LICENSE.txt); retain distribution notices. |
| scikit-learn | BSD-3-Clause | [Upstream COPYING](https://github.com/scikit-learn/scikit-learn/blob/main/COPYING). |
| Matplotlib | Matplotlib licence (PSF-based), BSD-compatible | [Upstream LICENSE](https://github.com/matplotlib/matplotlib/blob/main/LICENSE/LICENSE); no Matplotlib code vendored. |
| pytest | MIT | [Upstream LICENSE](https://github.com/pytest-dev/pytest/blob/main/LICENSE). |
| Hypothesis | MPL-2.0 | [Upstream LICENSE](https://github.com/HypothesisWorks/hypothesis/blob/master/hypothesis-python/LICENSE.txt); unmodified test dependency. |
| Ruff | MIT | [Upstream LICENSE](https://github.com/astral-sh/ruff/blob/main/LICENSE). |
| uv | MIT OR Apache-2.0 | [Upstream licences](https://github.com/astral-sh/uv#license). |

Versions and transitive dependencies are pinned in `uv.lock`. Dependencies are installed,
not repackaged or sublicensed as this project. Their original licence texts remain in
the installed distributions. No non-commercial model is used. The data source's restricted
use is a separate constraint and prevents treating the whole project as MIT-licensed data.

References (papers are linked, not redistributed):

- Dixon & Coles (1997), *Modelling Association Football Scores and Inefficiencies in the
  Football Betting Market*, [DOI](https://doi.org/10.1111/1467-9876.00065).
- Kaunitz, Zhong & Kreiner (2017), *Beating the bookies with their own numbers*,
  [arXiv:1710.02824](https://arxiv.org/abs/1710.02824).
- Bailey & López de Prado (2014), *The Deflated Sharpe Ratio*,
  [author manuscript](https://www.davidhbailey.com/dhbpapers/deflated-sharpe.pdf).
- Buchdahl, [closing-odds discussion](https://football-data.co.uk/blog/closing_odds.php)
  and [market-efficiency discussion](https://football-data.co.uk/blog/pinnacle_efficiency.php).
  CLV is a diagnostic of market-relative pricing, not proof of profitability or independence.

Upstream licence texts were retrieved and hashed on 2026-10-29; see
[verification records](docs/license_verification.json).

Automation actions (upstream MIT licences verified on 2026-10-29):

- actions/checkout: [MIT](https://github.com/actions/checkout/blob/main/LICENSE). The workflow pins a commit SHA.
- actions/cache: [MIT](https://github.com/actions/cache/blob/main/LICENSE). The workflow pins a commit SHA.
- actions/upload-artifact: [MIT](https://github.com/actions/upload-artifact/blob/main/LICENSE). The workflow pins a commit SHA.
- astral-sh/setup-uv: [MIT](https://github.com/astral-sh/setup-uv/blob/main/LICENSE). The workflow pins a commit SHA.

## The Odds API

Market data and the trimmed documentation transport example are provided by The Odds API
Pty Ltd under its [terms](https://the-odds-api.com/terms-and-conditions.html), reviewed
2026-10-29 (updated 2026-08-31). No MIT or open-data licence is asserted. Research, storage
and derived analytics are permitted; standalone data-feed redistribution is prohibited.
Credit is given voluntarily; see DATA_NOTICE.md and tests/fixtures/NOTICE.md.
