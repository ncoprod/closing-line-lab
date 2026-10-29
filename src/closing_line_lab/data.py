import csv
import hashlib
import io
import json
import time
import urllib.error
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd

from .common import ROOT, canonical, file_sha, now_utc, read_json, strategy, write_json

BASE = "https://football-data.co.uk"
PERMISSION = ROOT / "config/data_permission.json"
MANIFEST = ROOT / "data/manifest.jsonl"
PROCESSED = ROOT / "data/processed/matches.csv.gz"


class PermissionMissing(RuntimeError):
    pass


def require_permission(training=False):
    permission = read_json(PERMISSION)
    if not permission.get("evidence") or not permission.get("automated_collection"):
        raise PermissionMissing("Automated source access needs documented provider permission")
    if training and not permission.get("model_training"):
        raise PermissionMissing("Model training is outside the documented permission")


def cached_download(relative, refresh=False):
    require_permission()
    url = f"{BASE}/{relative}"
    entries = (
        [json.loads(line) for line in MANIFEST.read_text().splitlines()]
        if MANIFEST.exists()
        else []
    )
    previous = [x for x in entries if x["url"] == url]
    if previous and not refresh:
        entry = previous[-1]
        path = ROOT / entry["path"]
        if path.exists():
            if file_sha(path) != entry["sha256"]:
                raise ValueError("Raw cache hash mismatch")
            return path, entry
    request = urllib.request.Request(
        url, headers={"User-Agent": "closing-line-lab/0.1 personal research"}
    )
    for attempt in range(4):
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                payload = response.read()
                last_modified = response.headers.get("Last-Modified")
            break
        except (urllib.error.URLError, TimeoutError):
            if attempt == 3:
                raise
            time.sleep(2**attempt)
    header = payload.decode("utf-8-sig", errors="replace").splitlines()[0]
    if "HomeTeam" not in header or "AwayTeam" not in header:
        raise ValueError(f"Source is not a football CSV: {url}")
    sha = hashlib.sha256(payload).hexdigest()
    path = ROOT / "data/raw" / f"{sha}.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    entry = {
        "url": url,
        "retrieved_at": now_utc().isoformat(),
        "sha256": sha,
        "bytes": len(payload),
        "path": str(path.relative_to(ROOT)),
        "last_modified": last_modified,
    }
    MANIFEST.parent.mkdir(exist_ok=True)
    with MANIFEST.open("a") as handle:
        handle.write(canonical(entry) + "\n")
    return path, entry


def season_code(year):
    return f"{year % 100:02d}{(year + 1) % 100:02d}"


def current_season(at=None):
    at = at or now_utc()
    return at.year if at.month >= 7 else at.year - 1


def normalize(path, source_sha, season=None):
    # csv.DictReader tolerates historical files with surplus empty trailing columns.
    rows = list(csv.DictReader(io.StringIO(Path(path).read_text(encoding="utf-8-sig"))))
    source = pd.DataFrame(rows)
    if source.empty:
        return pd.DataFrame()
    source = source[source["HomeTeam"].notna() & source["AwayTeam"].notna()].copy()
    source = source[source.HomeTeam.str.strip().ne("")].reset_index(drop=True)
    dates = pd.to_datetime(source.Date, dayfirst=True, format="mixed", errors="raise")
    times = source.get("Time", pd.Series("", index=source.index)).fillna("")
    known = times.str.fullmatch(r"\d{1,2}:\d{2}")
    local = pd.to_datetime(dates.dt.strftime("%Y-%m-%d") + " " + times.where(known, "00:00"))
    kickoff = local.dt.tz_localize(
        "Europe/London", ambiguous="raise", nonexistent="raise"
    ).dt.tz_convert("UTC")
    years = (
        pd.Series(season, index=source.index) if season else dates.dt.year - (dates.dt.month < 7)
    )
    result = pd.DataFrame(
        {
            "season": years.astype(int),
            "div": source.Div,
            "kickoff_utc": kickoff,
            "time_known": known,
            "home": source.HomeTeam.str.strip(),
            "away": source.AwayTeam.str.strip(),
            "source_sha": source_sha,
        }
    )
    # Without publication timestamps, historical availability is a conservative proxy.
    result["available_at"] = kickoff + pd.to_timedelta(np.where(known, 12, 36), unit="h")
    for old, new in [("FTHG", "hg"), ("FTAG", "ag")]:
        result[new] = pd.to_numeric(
            source.get(old, pd.Series(index=source.index, dtype=float)), errors="coerce"
        )
    result["outcome"] = np.select(
        [result.hg > result.ag, result.hg == result.ag, result.hg < result.ag],
        [0, 1, 2],
        default=np.nan,
    )
    for prefix in ["B365", "B365C", "Avg", "AvgC", "Max", "MaxC", "BFE", "BFEC", "PS", "PSC"]:
        for side in "HDA":
            name = prefix + side
            old = name
            if name not in source and prefix == "Avg":
                old = "BbAv" + side
            result[name] = pd.to_numeric(
                source.get(old, pd.Series(index=source.index, dtype=float)), errors="coerce"
            )
    result["match_id"] = [
        hashlib.sha256(f"{y}|{d}|{h}|{a}".encode()).hexdigest()[:24]
        for y, d, h, a in zip(result.season, result["div"], result.home, result.away, strict=True)
    ]
    if result.match_id.duplicated().any():
        raise ValueError("Duplicate season/league/home/away fixture; reconcile manually")
    invalid = result.hg.notna() & (
        (result.hg < 0) | (result.ag < 0) | (result.hg % 1 != 0) | (result.ag % 1 != 0)
    )
    if invalid.any():
        raise ValueError("Invalid goal counts")
    return result


def quality_report(frame):
    rows = []
    for (season, div), group in frame.groupby(["season", "div"], sort=True):
        entry = {
            "season": int(season),
            "league": div,
            "matches": len(group),
            "results": int(group.outcome.notna().sum()),
            "known_kickoff_times": int(group.time_known.sum()),
        }
        for prefix in ["B365", "Avg", "AvgC", "B365C", "BFE", "BFEC", "PS", "PSC"]:
            prices = group[[prefix + s for s in "HDA"]].to_numpy(float)
            entry[prefix + "_complete"] = int(
                (np.isfinite(prices).all(1) & (prices > 1).all(1)).sum()
            )
        rows.append(entry)
    return {
        "matches": len(frame),
        "duplicate_ids": int(frame.match_id.duplicated().sum()),
        "coverage": rows,
        "pinnacle_excluded": "Unreliable feed since 2025-07-23",
    }


def download_history():
    require_permission(training=True)
    cfg = strategy()
    pieces = []
    for year in range(cfg["first_season"], current_season() + 1):
        for league in cfg["leagues"]:
            path, entry = cached_download(
                f"mmz4281/{season_code(year)}/{league}.csv", refresh=year == current_season()
            )
            pieces.append(normalize(path, entry["sha256"], year))
    frame = pd.concat(pieces, ignore_index=True).sort_values(["kickoff_utc", "match_id"])
    if frame.match_id.duplicated().any():
        raise ValueError("Duplicate historical matches")
    PROCESSED.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(PROCESSED, index=False, compression={"method": "gzip", "mtime": 0})
    report = quality_report(frame)
    report["processed_sha256"] = file_sha(PROCESSED)
    write_json(ROOT / "results/data_quality.json", report)
    return report


def load_matches(path=PROCESSED):
    frame = pd.read_csv(path)
    for col in ["kickoff_utc", "available_at"]:
        frame[col] = pd.to_datetime(frame[col], utc=True)
    return frame.sort_values(["kickoff_utc", "match_id"]).reset_index(drop=True)
