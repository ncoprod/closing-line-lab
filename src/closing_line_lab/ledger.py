import json
import subprocess
from datetime import timedelta
from pathlib import Path

import numpy as np

from .common import ROOT, canonical, digest, now_utc, timestamp, write_json

LEDGER = ROOT / "data/ledger.jsonl"
ZERO = "0" * 64
REPO = "ncoprod/closing-line-lab"


def read_ledger(path=LEDGER):
    path = Path(path)
    if not path.exists():
        return []
    payload = path.read_text()
    if payload and not payload.endswith("\n"):
        raise ValueError("Truncated ledger")
    records = [json.loads(line) for line in payload.splitlines()]
    check_chain(records)
    return records


def check_chain(records):
    previous = ZERO
    for sequence, record in enumerate(records, 1):
        unsigned = {k: v for k, v in record.items() if k != "hash"}
        if record.get("sequence") != sequence or record.get("previous_hash") != previous:
            raise ValueError("Ledger sequence/parent mismatch")
        if digest(unsigned) != record.get("hash"):
            raise ValueError("Ledger hash mismatch")
        previous = record["hash"]


def append_event(payload, path=LEDGER):
    records = read_ledger(path)
    event = {
        **payload,
        "sequence": len(records) + 1,
        "previous_hash": records[-1]["hash"] if records else ZERO,
    }
    event["hash"] = digest(event)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as handle:
        handle.write(canonical(event) + "\n")
    return event


def verify_records(records, receipts):
    """A receipt binds server creation time to the exact ledger hashes at its head SHA."""
    check_chain(records)
    forecasts, settlements, closes = {}, set(), {}
    for record in records:
        match_id = record["match_id"]
        if record["kind"] == "forecast":
            if match_id in forecasts:
                raise ValueError("Duplicate forecast")
            forecasts[match_id] = record
            kickoff = timestamp(record["kickoff_utc"])
            decision, recorded = timestamp(record["decision_at"]), timestamp(record["recorded_at"])
            observed = timestamp(record["quote_retrieved_at"])
            feature_max = timestamp(record["feature_max_available"])
            if not observed <= decision <= recorded < kickoff or feature_max >= decision:
                raise ValueError("Forecast or features are not strictly pre-kickoff/as-of")
            p = np.array(record["probabilities"], dtype=float)
            prices = np.array(record["prices"], dtype=float)
            if (
                p.shape != (3,)
                or (p <= 0).any()
                or not np.isfinite(p).all()
                or not np.isclose(p.sum(), 1)
            ):
                raise ValueError("Invalid probabilities")
            if prices.shape != (3,) or not np.isfinite(prices).all() or (prices <= 1).any():
                raise ValueError("Invalid prices")
            bet = record["bet"]
            if bet is not None:
                if bet["side_index"] not in (0, 1, 2) or bet["odds"] != prices[bet["side_index"]]:
                    raise ValueError("Bet price differs from recorded quote")
                if not 0 < bet["stake_units"] <= record["stake_cap_units"] + 1e-9:
                    raise ValueError("Invalid stake")
            evidence = [
                receipt
                for receipt in receipts
                if record["hash"] in receipt["ledger_hashes"]
                and recorded <= timestamp(receipt["created_at"]) < kickoff
            ]
            if not evidence:
                raise ValueError(f"No pre-kickoff GitHub server receipt: {match_id}")
        elif record["kind"] == "closing_snapshot":
            if match_id not in forecasts or match_id in settlements:
                raise ValueError("Orphan or post-settlement closing snapshot")
            original = forecasts[match_id]
            if record["forecast_hash"] != original["hash"]:
                raise ValueError("Closing snapshot points to a different forecast")
            kickoff = timestamp(original["kickoff_utc"])
            observed, recorded = timestamp(record["retrieved_at"]), timestamp(record["recorded_at"])
            if not (
                timestamp(record["updated_at"]) <= observed + timedelta(seconds=5)
                and observed <= recorded < kickoff
            ):
                raise ValueError("Closing snapshot was not collected before kickoff")
            if timestamp(record["kickoff_utc"]) != kickoff:
                raise ValueError("Closing snapshot kickoff changed")
            prices = np.asarray(record["prices"], float)
            if prices.shape != (3,) or not np.isfinite(prices).all() or (prices <= 1).any():
                raise ValueError("Invalid closing snapshot prices")
            gap = (kickoff - observed).total_seconds() / 60
            if not np.isclose(record["snapshot_gap_minutes"], gap):
                raise ValueError("Closing snapshot gap does not replay")
            if not any(
                record["hash"] in r["ledger_hashes"]
                and recorded <= timestamp(r["created_at"]) < kickoff
                for r in receipts
            ):
                raise ValueError("No pre-kickoff GitHub server receipt for closing snapshot")
            if match_id in closes and observed < timestamp(closes[match_id]["retrieved_at"]):
                raise ValueError("Closing snapshots are out of order")
            closes[match_id] = record
        elif record["kind"] == "settlement":
            if match_id not in forecasts or match_id in settlements:
                raise ValueError("Orphan or duplicate settlement")
            if record["forecast_hash"] != forecasts[match_id]["hash"]:
                raise ValueError("Settlement points to a different forecast")
            if timestamp(record["recorded_at"]) < timestamp(forecasts[match_id]["kickoff_utc"]):
                raise ValueError("Settlement before kickoff")
            if record["status"] not in ("SETTLED", "VOID_SCHEDULE_CHANGED"):
                raise ValueError("Unknown settlement status")
            forecast = forecasts[match_id]
            bet = forecast["bet"]
            expected_profit, expected_clv = 0.0, None
            if "closing_snapshot_hash" not in record:
                raise ValueError("Settlement requires an explicit closing snapshot link")
            latest = closes.get(match_id) if record["status"] == "SETTLED" else None
            if record["closing_snapshot_hash"] != (latest["hash"] if latest else None):
                raise ValueError("Settlement must use the last pre-kickoff snapshot")
            closing = record["closing_prices"]
            if latest is None:
                if any(
                    record.get(k) is not None
                    for k in (
                        "closing_prices",
                        "closing_bookmaker",
                        "closing_gap_minutes",
                        "log_clv",
                        "fair_log_clv",
                        "same_book_log_clv",
                    )
                ):
                    raise ValueError("Closing values require a receipted closing snapshot")
            else:
                if closing != latest["prices"]:
                    raise ValueError("Settlement changed closing prices")
                if record.get("closing_bookmaker") != latest["bookmaker"] or not np.isclose(
                    record.get("closing_gap_minutes", np.nan), latest["snapshot_gap_minutes"]
                ):
                    raise ValueError("Settlement changed closing metadata")
            if record["status"] == "SETTLED":
                if record["result_kickoff_utc"] != forecast["kickoff_utc"]:
                    raise ValueError("Changed kickoff must be voided")
                closing = record["closing_prices"]
                if closing is not None:
                    closing = np.asarray(closing, dtype=float)
                    if (
                        closing.shape != (3,)
                        or (closing <= 1).any()
                        or not np.isfinite(closing).all()
                    ):
                        raise ValueError("Invalid settlement closing prices")
                if record["outcome"] not in (0, 1, 2):
                    raise ValueError("Invalid result")
                if bet:
                    won = bet["side_index"] == record["outcome"]
                    expected_profit = bet["stake_units"] * (bet["odds"] - 1 if won else -1)
                    if closing is not None:
                        expected_clv = float(
                            np.log(bet.get("raw_odds", bet["odds"]) / closing[bet["side_index"]])
                        )
                expected_fair, expected_same = None, None
                if bet and latest:
                    from .metrics import devig

                    side = bet["side_index"]
                    taken = bet.get("raw_odds", bet["odds"])
                    expected_fair = float(np.log(taken * devig(latest["prices"])[side]))
                    if latest.get("same_book_prices") is not None:
                        expected_same = float(np.log(taken / latest["same_book_prices"][side]))
                for name, expected in [
                    ("fair_log_clv", expected_fair),
                    ("same_book_log_clv", expected_same),
                ]:
                    actual = record.get(name)
                    if (expected is None and actual is not None) or (
                        expected is not None
                        and (actual is None or not np.isclose(actual, expected))
                    ):
                        raise ValueError("Secondary CLV does not replay")
            if not np.isclose(record["profit_units"], expected_profit):
                raise ValueError("Settlement profit does not replay")
            if (expected_clv is None and record["log_clv"] is not None) or (
                expected_clv is not None and not np.isclose(record["log_clv"], expected_clv)
            ):
                raise ValueError("Settlement CLV does not replay")
            settlements.add(match_id)
        else:
            raise ValueError("Unknown ledger event")
    return {
        "status": "VERIFIED" if forecasts else "NO_FORECASTS",
        "events": len(records),
        "forecasts": len(forecasts),
        "settlements": len(settlements),
        "chain_head": records[-1]["hash"] if records else ZERO,
    }


def github_receipts():
    output = subprocess.check_output(
        [
            "gh",
            "api",
            "--paginate",
            "--slurp",
            f"repos/{REPO}/actions/workflows/audit.yml/runs?per_page=100",
        ],
        text=True,
        cwd=ROOT,
    )
    receipts = []
    for page in json.loads(output):
        for run in page["workflow_runs"]:
            if run["event"] not in ("push", "workflow_dispatch", "schedule"):
                continue
            if run["head_repository"]["full_name"] != REPO or run["head_branch"] != "main":
                continue
            try:
                ledger = subprocess.check_output(
                    ["git", "show", f"{run['head_sha']}:data/ledger.jsonl"],
                    cwd=ROOT,
                    text=True,
                    stderr=subprocess.DEVNULL,
                )
            except subprocess.CalledProcessError:
                continue
            records = [json.loads(line) for line in ledger.splitlines()]
            check_chain(records)
            receipts.append(
                {
                    "run_id": run["id"],
                    "created_at": run["created_at"],
                    "head_sha": run["head_sha"],
                    "event": run["event"],
                    "url": run["html_url"],
                    "ledger_hashes": [x["hash"] for x in records],
                }
            )
    return receipts


def verify():
    records = read_ledger()
    receipts = github_receipts() if records else []
    report = verify_records(records, receipts)
    report["checked_at"] = now_utc().isoformat()
    report["receipt_runs"] = [
        {k: v for k, v in x.items() if k != "ledger_hashes"} for x in receipts
    ]
    write_json(ROOT / "results/verification.json", report)
    return report


def replay_account(records):
    """Cash and pending stakes; open risk is valued at cost, never at future odds."""
    cash, pending = 100.0, {}
    forecasts = {}
    for record in records:
        match_id = record["match_id"]
        if record["kind"] == "forecast":
            forecasts[match_id] = record
            if record["bet"]:
                stake = record["bet"]["stake_units"]
                cash -= stake
                pending[match_id] = stake
        elif record["kind"] == "settlement":
            if match_id not in forecasts:
                raise ValueError("Orphan account settlement")
            stake = pending.pop(match_id, 0)
            cash += stake + record["profit_units"]
        if cash < -1e-8:
            raise ValueError("Paper account spent unavailable cash")
    return {
        "cash": cash,
        "open_stakes": sum(pending.values()),
        "pending": pending,
        "equity_at_cost": cash + sum(pending.values()),
    }
