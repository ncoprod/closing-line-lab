import numpy as np
import pandas as pd
import pytest

from closing_line_lab.common import strategy


@pytest.fixture
def cfg():
    return strategy()


@pytest.fixture
def history():
    """Locally generated engineering data, never evidence about a betting edge."""
    rng = np.random.default_rng(123)
    dates = pd.date_range("2018-01-01", periods=180, freq="3D", tz="UTC")
    frame = pd.DataFrame(
        {
            "match_id": [f"synthetic-{i}" for i in range(len(dates))],
            "season": 2018,
            "div": "E0",
            "kickoff_utc": dates,
            "available_at": dates + pd.Timedelta(hours=12),
            "home": [f"Team {i % 6}" for i in range(len(dates))],
            "away": [f"Team {(i + 1 + i // 6) % 6}" for i in range(len(dates))],
            "hg": rng.poisson(1.5, len(dates)),
            "ag": rng.poisson(1.1, len(dates)),
            "B365H": 2.1,
            "B365D": 3.3,
            "B365A": 3.4,
            "AvgCH": 2.0,
            "AvgCD": 3.4,
            "AvgCA": 3.5,
            "B365CH": 2.05,
            "B365CD": 3.3,
            "B365CA": 3.3,
            "time_known": True,
            "source_sha": "synthetic",
        }
    )
    same = frame.home == frame.away
    frame.loc[same, "away"] = "Team other"
    frame["outcome"] = np.select([frame.hg > frame.ag, frame.hg == frame.ag], [0, 1], default=2)
    return frame
