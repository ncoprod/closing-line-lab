import json
import subprocess
from datetime import timedelta
from email.utils import parsedate_to_datetime

import numpy as np
import pandas as pd

from .common import ROOT, digest, file_sha, now_utc, strategy, timestamp, write_json
from .data import (
    cached_download,
    current_season,
    download_history,
    load_matches,
    normalize,
    require_permission,
    season_code,
)
from .ledger import LEDGER, REPO, append_event, read_ledger, replay_account, verify
from .metrics import clv, devig
from .models import SIDES, OffsetBlend, make_features, probability_matrix
from .research import assert_frozen, choose_bet, git, load_features


def frozen_runtime():
    selection = assert_frozen()
    cfg = {**strategy(), **selection["candidate"]}
    for filename in ["data.py", "forward.py", "ledger.py", "metrics.py"]:
        if git("diff", "forward-v1", "--", f"src/closing_line_lab/{filename}"):
            raise RuntimeError("Forward runtime differs from the registered tag")
    return cfg


def training_features(history, cfg):
    past = history[(history.season < current_season()) & history.outcome.notna()]
    fingerprint = digest(past[["match_id", "source_sha"]].to_dict("records"))
    cache = ROOT / "data/processed/forward_training.csv.gz"
    metadata = cache.with_suffix(".json")
    if (
        cache.exists()
        and metadata.exists()
        and json.loads(metadata.read_text())["fingerprint"] == fingerprint
    ):
        return load_features(cache).merge(past, on="match_id", validate="one_to_one")
    targets = past[past.season >= cfg["first_season"] + 3]
    features = make_features(past, targets, cfg)
    features.to_csv(cache, index=False, compression={"method": "gzip", "mtime": 0})
    write_json(metadata, {"fingerprint": fingerprint, "features_sha": file_sha(cache)})
    return features.merge(past, on="match_id", validate="one_to_one")


def forecast():
    require_permission(training=True)
    cfg = frozen_runtime()
    if not timestamp(cfg["forward_start"]) <= now_utc() < timestamp(cfg["forward_end"]):
        return {"status": "OUTSIDE_REGISTERED_WINDOW", "new_forecasts": 0}
    records = read_ledger()
    if records:
        verify()
    download_history()
    history = load_matches()
    path, entry = cached_download("fixtures.csv", refresh=True)
    observed = timestamp(entry["retrieved_at"])
    decision = now_utc()
    if entry["last_modified"] is None:
        raise ValueError("Fixture age unknown: Last-Modified header required")
    modified = parsedate_to_datetime(entry["last_modified"])
    if not timedelta(0) <= decision - modified <= timedelta(hours=cfg["max_lead_hours"]):
        raise ValueError("Fixture source is stale or future-dated")
    fixtures = normalize(path, entry["sha256"])
    existing = {x["match_id"] for x in records if x["kind"] == "forecast"}
    fixtures = fixtures[fixtures["div"].isin(cfg["leagues"]) & fixtures.time_known]
    fixtures = fixtures[~fixtures.match_id.isin(existing)]
    lead = fixtures.kickoff_utc - decision
    fixtures = fixtures[
        (lead >= pd.Timedelta(minutes=cfg["min_lead_minutes"]))
        & (lead <= pd.Timedelta(hours=cfg["max_lead_hours"]))
    ].copy()
    if fixtures.empty:
        return {
            "status": "NO_ELIGIBLE_FIXTURES",
            "new_forecasts": 0,
            "fixture_sha": entry["sha256"],
        }
    fixtures["decision_at"] = pd.Timestamp(decision)
    features = make_features(history, fixtures, cfg)
    if features.empty:
        raise ValueError("No fixtures have adequate model history and complete quote triples")
    if cfg["model"] == "blend":
        training = training_features(history, cfg)
        cutoff = pd.Timestamp(year=current_season(), month=7, day=1, tz="UTC")
        eligible = training[training.available_at < cutoff]
        if len(eligible) < cfg["blend_min_matches"]:
            raise ValueError("Insufficient blend training matches")
        fitted = OffsetBlend(cfg["blend_ridge"]).fit(eligible, cutoff)
        probabilities = fitted.predict(features)
        blend_sha = digest(
            {
                "theta": fitted.theta.tolist(),
                "cutoff": cutoff.isoformat(),
                "training_rows": sorted(eligible.match_id),
            }
        )
    else:
        probabilities = probability_matrix(features, cfg["model"])
        blend_sha = None
    account = replay_account(records)
    count, new_bets = 0, 0
    for feature, probabilities_row in zip(features.itertuples(), probabilities, strict=True):
        fixture = fixtures[fixtures.match_id == feature.match_id].iloc[0]
        if now_utc() + timedelta(minutes=cfg["min_lead_minutes"]) >= fixture.kickoff_utc:
            continue
        prices = np.array([fixture[cfg["odds_source"] + s] for s in SIDES])
        bet = choose_bet(probabilities_row, prices, cfg)
        cap_units = cfg["stake_cap"] * account["equity_at_cost"]
        if bet is not None:
            stake = min(
                bet["stake_fraction"] * account["equity_at_cost"],
                account["cash"],
                max(
                    0, cfg["open_exposure_cap"] * account["equity_at_cost"] - account["open_stakes"]
                ),
            )
            if stake <= 1e-10:
                bet = None
            else:
                bet["stake_units"] = stake
                account["cash"] -= stake
                account["open_stakes"] += stake
                new_bets += 1
        append_event(
            {
                "kind": "forecast",
                "match_id": feature.match_id,
                "league": fixture["div"],
                "season": int(fixture.season),
                "home": fixture.home,
                "away": fixture.away,
                "kickoff_utc": fixture.kickoff_utc.isoformat(),
                "decision_at": decision.isoformat(),
                "recorded_at": now_utc().isoformat(),
                "quote_retrieved_at": observed.isoformat(),
                "source_last_modified": modified.isoformat(),
                "quote_type": "indicative_pre_closing_snapshot",
                "feature_max_available": feature.feature_max_available.isoformat(),
                "probabilities": probabilities_row.tolist(),
                "prices": prices.tolist(),
                "odds_source": cfg["odds_source"],
                "closing_source": cfg["closing_source"],
                "bet": bet,
                "stake_cap_units": cap_units,
                "strategy_sha": digest(strategy()),
                "blend_sha": blend_sha,
                "runtime_commit": git("rev-parse", "HEAD"),
                "registration_commit": git("rev-list", "-n", "1", "forward-v1"),
                "feature_sha": digest({k: str(v) for k, v in feature._asdict().items()}),
                "history_sha": file_sha(ROOT / "data/processed/matches.csv.gz"),
                "fixture_sha": entry["sha256"],
            }
        )
        count += 1
    return {"status": "RECORDED_UNPUBLISHED", "new_forecasts": count, "new_bets": new_bets}


def settle():
    require_permission()
    frozen_runtime()
    records = read_ledger()
    settled = {r["match_id"] for r in records if r["kind"] == "settlement"}
    pending = [
        r
        for r in records
        if r["kind"] == "forecast"
        and r["match_id"] not in settled
        and timestamp(r["kickoff_utc"]) + timedelta(hours=12) < now_utc()
    ]
    if not pending:
        return {"status": "NO_SETTLED_MATCHES", "new_settlements": 0}
    verify()
    seasons = {(r["season"], r["league"]) for r in pending}
    pieces = []
    for season, league in sorted(seasons):
        path, entry = cached_download(f"mmz4281/{season_code(season)}/{league}.csv", refresh=True)
        pieces.append(normalize(path, entry["sha256"], season))
    results = pd.concat(pieces, ignore_index=True).set_index("match_id", verify_integrity=True)
    count = 0
    for forecast in pending:
        match_id = forecast["match_id"]
        if match_id not in results.index:
            continue
        row = results.loc[match_id]
        if pd.isna(row.outcome) or row.available_at >= now_utc():
            continue
        changed = row.kickoff_utc != pd.Timestamp(forecast["kickoff_utc"])
        close_prices = np.array([row[forecast["closing_source"] + s] for s in SIDES])
        # Missing closing odds stay pending and remain visible in the report.
        if not changed and (not np.isfinite(close_prices).all() or (close_prices <= 1).any()):
            continue
        bet = forecast["bet"]
        profit, log_clv, fair_clv, same_book = 0.0, None, None, None
        if bet is not None and not changed:
            won = int(row.outcome) == bet["side_index"]
            profit = bet["stake_units"] * (bet["odds"] - 1) if won else -bet["stake_units"]
            log_clv = clv(bet["odds"], close_prices[bet["side_index"]])
            fair_clv = float(np.log(bet["odds"] * devig(close_prices)[bet["side_index"]]))
            paired = row["B365C" + bet["side"]]
            same_book = clv(bet["odds"], paired) if np.isfinite(paired) and paired > 1 else None
        append_event(
            {
                "kind": "settlement",
                "match_id": match_id,
                "forecast_hash": forecast["hash"],
                "recorded_at": now_utc().isoformat(),
                "status": "VOID_SCHEDULE_CHANGED" if changed else "SETTLED",
                "result_kickoff_utc": row.kickoff_utc.isoformat(),
                "outcome": int(row.outcome),
                "closing_prices": None if changed else close_prices.tolist(),
                "profit_units": float(profit),
                "log_clv": log_clv,
                "fair_log_clv": fair_clv,
                "same_book_log_clv": same_book,
                "result_source_sha": row.source_sha,
            }
        )
        count += 1
    return {"status": "SCORED", "new_settlements": count}


def publish(settlements_only=False):
    if git("branch", "--show-current") != "main":
        raise RuntimeError("Publish requires main")
    subprocess.run(["git", "fetch", "origin", "main"], check=True, cwd=ROOT)
    if git("rev-parse", "HEAD") != git("rev-parse", "origin/main"):
        raise RuntimeError("Remote advanced; retry from a clean checkout without rebasing ledger")
    records = read_ledger()
    try:
        committed = git("show", "HEAD:data/ledger.jsonl").splitlines()
    except subprocess.CalledProcessError:
        committed = []
    current = LEDGER.read_text().splitlines() if LEDGER.exists() else []
    if current[: len(committed)] != committed:
        raise ValueError("Ledger publication must be append-only")
    new = records[len(committed) :]
    if settlements_only and any(r["kind"] == "forecast" for r in new):
        raise ValueError("Settlement publication includes a forecast")
    forecast_rows = [r for r in new if r["kind"] == "forecast"]

    def check_deadline():
        if any(
            timestamp(r["kickoff_utc"]) <= now_utc() + timedelta(minutes=15) for r in forecast_rows
        ):
            raise ValueError("Too late to publish this forecast batch")

    check_deadline()
    paths = ["data/ledger.jsonl", "data/manifest.jsonl", "results", "README.md"]
    paths = [p for p in paths if (ROOT / p).exists()]
    subprocess.run(["git", "add", "--", *paths], check=True, cwd=ROOT)
    # Required pre-commit check. Match only tracked content; never print matched secrets.
    scan = subprocess.run(
        ["git", "grep", "-nE", r"nvapi-[A-Za-z0-9]{10}|" + "KGA" + r'T_|"key"\s*:'],
        cwd=ROOT,
        capture_output=True,
    )
    if scan.returncode != 1:
        raise RuntimeError("Secret scan matched content or failed; publication stopped")
    if not git("diff", "--cached", "--name-only"):
        return {"status": "NO_CHANGES"}
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=closing-line-lab[bot]",
            "-c",
            "user.email=closing-line-lab[bot]@users.noreply.github.com",
            "commit",
            "-m",
            "results: append paper research observations",
        ],
        check=True,
        cwd=ROOT,
    )
    check_deadline()
    subprocess.run(["git", "push", "origin", "HEAD:main"], check=True, cwd=ROOT)
    if forecast_rows:
        subprocess.run(
            ["gh", "workflow", "run", "audit.yml", "--repo", REPO, "--ref", "main"],
            check=True,
            cwd=ROOT,
        )
    return {
        "status": "PUSHED",
        "new_forecasts": len(forecast_rows),
        "commit": git("rev-parse", "HEAD"),
    }
