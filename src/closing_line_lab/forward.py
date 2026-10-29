import subprocess
from datetime import timedelta

import numpy as np

from .artifact import ARTIFACT, predict
from .common import (
    REGISTRATION_TAG,
    ROOT,
    digest,
    now_utc,
    read_json,
    strategy,
    timestamp,
    write_json,
)
from .ledger import LEDGER, REPO, append_event, read_ledger, replay_account, verify
from .metrics import clv, devig
from .odds import BudgetExhausted, OddsClient, forward_config, quote
from .research import assert_frozen, choose_bet, git

STATE = ROOT / "data/forward_state.json"


def frozen_runtime():
    selection = assert_frozen()
    return {**strategy(), **selection["candidate"]}


def record_forecast(event, observed, entry, cfg, fc, artifact):
    league = fc["sports"][event["sport_key"]]
    try:
        probabilities = predict(
            artifact, league, event["home_team"], event["away_team"], observed["prices"], cfg
        )
    except ValueError as error:
        if "Unknown team alias" in str(error):
            return False
        raise
    account = replay_account(read_ledger())
    bet = choose_bet(probabilities, observed["effective_prices"], cfg)
    if bet:
        stake = min(
            bet["stake_fraction"] * account["equity_at_cost"],
            account["cash"],
            max(0, cfg["open_exposure_cap"] * account["equity_at_cost"] - account["open_stakes"]),
        )
        if stake <= 1e-10:
            bet = None
        else:
            bet.update(stake_units=stake, raw_odds=observed["prices"][bet["side_index"]])
    decision = now_utc()
    append_event(
        {
            "kind": "forecast",
            "match_id": event["id"],
            "league": league,
            "sport": event["sport_key"],
            "home": event["home_team"],
            "away": event["away_team"],
            "kickoff_utc": timestamp(event["commence_time"]).isoformat(),
            "decision_at": decision.isoformat(),
            "recorded_at": now_utc().isoformat(),
            "quote_retrieved_at": observed["retrieved_at"],
            "source_last_modified": observed["updated_at"],
            "quote_type": "the_odds_api_decision_snapshot",
            "feature_max_available": artifact["feature_max_available"],
            "probabilities": probabilities.tolist(),
            "prices": observed["effective_prices"],
            "raw_prices": observed["prices"],
            "odds_source": observed["bookmaker"],
            "exchange_commission": observed["commission"],
            "closing_source": "last pre-kickoff snapshot; Betfair EU then Pinnacle",
            "bet": bet,
            "stake_cap_units": cfg["stake_cap"] * account["equity_at_cost"],
            "strategy_sha": digest(strategy()),
            "model_artifact_sha": artifact["artifact_sha"],
            "runtime_commit": git("rev-parse", "HEAD"),
            "registration_commit": git("rev-list", "-n", "1", REGISTRATION_TAG),
            "fixture_sha": entry["sha256"],
            "decision_gap_minutes": (timestamp(event["commence_time"]) - decision).total_seconds()
            / 60,
        }
    )
    return True


def forecast():
    cfg, fc = frozen_runtime(), forward_config()
    if not ARTIFACT.exists():
        return {"status": "AWAITING_LOCAL_PARAMETER_EXPORT", "new_forecasts": 0}
    decision_window = timestamp(cfg["forward_start"]) <= now_utc() < timestamp(cfg["forward_end"])
    records = read_ledger()
    if records:
        verify()
    artifact, client = read_json(ARTIFACT), OddsClient()
    forecasts = {r["match_id"]: r for r in records if r["kind"] == "forecast"}
    counts = {"new_forecasts": 0, "new_closing_snapshots": 0, "unknown_teams": 0}
    budget_limited = False
    for sport in fc["sports"]:
        events, _ = client.get(sport, "events")
        due = set()
        for event in events:
            lead = (timestamp(event["commence_time"]) - now_utc()).total_seconds() / 60
            if (
                decision_window
                and event["id"] not in forecasts
                and fc["decision_min_hours"] * 60 <= lead <= fc["decision_max_hours"] * 60
            ) or (
                event["id"] in forecasts
                and fc["publish_buffer_minutes"] < lead <= fc["closing_max_minutes"]
            ):
                due.add(event["id"])
        if not due:
            continue
        try:
            priced, entry = client.get(sport, "odds")
        except BudgetExhausted:
            budget_limited = True
            continue
        for event in sorted(priced, key=lambda e: (e["commence_time"], e["id"])):
            if event["id"] not in due:
                continue
            lead = (timestamp(event["commence_time"]) - now_utc()).total_seconds() / 60
            if event["id"] not in forecasts:
                if (
                    not decision_window
                    or not fc["decision_min_hours"] * 60 <= lead <= fc["decision_max_hours"] * 60
                ):
                    continue
                observed = quote(event, fc["decision_book_priority"], entry["retrieved_at"], fc)
                if observed:
                    ok = record_forecast(event, observed, entry, cfg, fc, artifact)
                    counts["new_forecasts"] += int(ok)
                    counts["unknown_teams"] += int(not ok)
            elif fc["publish_buffer_minutes"] < lead <= fc["closing_max_minutes"]:
                original = forecasts[event["id"]]
                if timestamp(original["kickoff_utc"]) != timestamp(event["commence_time"]):
                    continue
                observed = quote(event, fc["benchmark_priority"], entry["retrieved_at"], fc)
                if observed:
                    same = quote(event, [original["odds_source"]], entry["retrieved_at"], fc)
                    append_event(
                        {
                            "kind": "closing_snapshot",
                            "match_id": event["id"],
                            "forecast_hash": original["hash"],
                            "kickoff_utc": original["kickoff_utc"],
                            "recorded_at": now_utc().isoformat(),
                            **observed,
                            "same_book_prices": same["prices"] if same else None,
                            "snapshot_gap_minutes": (
                                timestamp(event["commence_time"]) - timestamp(entry["retrieved_at"])
                            ).total_seconds()
                            / 60,
                            "source_sha": entry["sha256"],
                        }
                    )
                    counts["new_closing_snapshots"] += 1
    return {"status": "BUDGET_LIMITED" if budget_limited else "CAPTURED", **counts}


def settle():
    frozen_runtime()
    fc, records = forward_config(), read_ledger()
    forecasts = {r["match_id"]: r for r in records if r["kind"] == "forecast"}
    settled = {r["match_id"] for r in records if r["kind"] == "settlement"}
    pending = [
        r
        for mid, r in forecasts.items()
        if mid not in settled and timestamp(r["kickoff_utc"]) + timedelta(hours=3) < now_utc()
    ]
    if not pending or now_utc().hour < fc["score_hour_utc"]:
        return {"status": "NO_RESULTS_DUE", "new_settlements": 0}
    verify()
    state = read_json(STATE) if STATE.exists() else {"score_dates": {}}
    client, count = OddsClient(), 0
    closes = {r["match_id"]: r for r in records if r["kind"] == "closing_snapshot"}
    for sport in sorted({r["sport"] for r in pending}):
        today = now_utc().date().isoformat()
        if state["score_dates"].get(sport) == today:
            continue
        try:
            results, entry = client.get(sport, "scores")
        except BudgetExhausted:
            continue
        state["score_dates"][sport] = today
        write_json(STATE, state)
        for result in results:
            mid = result["id"]
            if mid not in forecasts or mid in settled or not result.get("completed"):
                continue
            original = forecasts[mid]
            changed = timestamp(result["commence_time"]) != timestamp(original["kickoff_utc"])
            points = {s["name"]: int(s["score"]) for s in result.get("scores") or []}
            if original["home"] not in points or original["away"] not in points:
                continue
            h, a = points[original["home"]], points[original["away"]]
            outcome = 0 if h > a else 1 if h == a else 2
            closing = closes.get(mid) if not changed else None
            bet = original["bet"]
            profit, raw_clv, fair_clv, same_book = 0.0, None, None, None
            if bet and not changed:
                profit = bet["stake_units"] * (
                    bet["odds"] - 1 if outcome == bet["side_index"] else -1
                )
                if closing:
                    side = bet["side_index"]
                    raw_clv = clv(bet["raw_odds"], closing["prices"][side])
                    fair_clv = float(np.log(bet["raw_odds"] * devig(closing["prices"])[side]))
                    if closing["same_book_prices"]:
                        same_book = clv(bet["raw_odds"], closing["same_book_prices"][side])
            append_event(
                {
                    "kind": "settlement",
                    "match_id": mid,
                    "forecast_hash": original["hash"],
                    "recorded_at": now_utc().isoformat(),
                    "status": "VOID_SCHEDULE_CHANGED" if changed else "SETTLED",
                    "result_kickoff_utc": timestamp(result["commence_time"]).isoformat(),
                    "outcome": outcome,
                    "closing_prices": closing["prices"] if closing else None,
                    "closing_snapshot_hash": closing["hash"] if closing else None,
                    "closing_bookmaker": closing["bookmaker"] if closing else None,
                    "closing_gap_minutes": closing["snapshot_gap_minutes"] if closing else None,
                    "profit_units": float(profit),
                    "log_clv": raw_clv,
                    "fair_log_clv": fair_clv,
                    "same_book_log_clv": same_book,
                    "result_source_sha": entry["sha256"],
                }
            )
            settled.add(mid)
            count += 1
    return {"status": "SCORED", "new_settlements": count}


def publish(settlements_only=False):
    frozen_runtime()
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
    forecast_rows = [r for r in new if r["kind"] in ("forecast", "closing_snapshot")]

    def check_deadline():
        if any(
            timestamp(r["kickoff_utc"]) <= now_utc() + timedelta(minutes=15) for r in forecast_rows
        ):
            raise ValueError("Too late to publish this forecast batch")

    check_deadline()
    paths = [
        "data/ledger.jsonl",
        "data/api_manifest.jsonl",
        "data/api_usage.json",
        "data/forward_state.json",
        "results",
        "README.md",
    ]
    paths = [p for p in paths if (ROOT / p).exists()]
    subprocess.run(["git", "add", "--", *paths], check=True, cwd=ROOT)
    from .security import publication_scan

    publication_scan()
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
        "new_pre_kickoff_events": len(forecast_rows),
        "commit": git("rev-parse", "HEAD"),
    }
