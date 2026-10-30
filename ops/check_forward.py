"""Audit forward accumulation using GitHub receipts and the Mac log; no provider calls."""

import json
import os
import re
import subprocess
from datetime import timedelta
from pathlib import Path

from closing_line_lab.budget import GitHubBudget
from closing_line_lab.common import ROOT, digest, now_utc, read_json, timestamp, write_json
from closing_line_lab.ledger import github_receipts, read_ledger, verify_records


def cycle_health(rows, checked_at):
    completed = {r["slot"]: r for r in rows if r["status"] == "COMPLETED"}
    slots = sorted(completed)
    missing = []
    if slots:
        cursor = timestamp(slots[0] + ":00:00+00:00")
        end = timestamp(slots[-1] + ":00:00+00:00")
        while cursor <= end:
            if cursor.strftime("%Y-%m-%dT%H") not in completed:
                missing.append(cursor.isoformat())
            cursor += timedelta(hours=1)
    last = completed[slots[-1]]["checked_at"] if slots else None
    age = (checked_at - timestamp(last)).total_seconds() / 60 if last else None
    return {
        "completed_cycles": len(slots),
        "first_completed_slot": slots[0] if slots else None,
        "last_completed_at": last,
        "minutes_since_completion": age,
        "missing_between_completed_slots": missing,
        "failed_log_entries": sum(r["status"] == "FAILED" for r in rows),
        "skipped_log_entries": sum(r["status"] == "SKIPPED_BUSY_OR_COMPLETED" for r in rows),
        "fresh_within_90_minutes": age is not None and age <= 90,
    }


def publication_health(records, receipts):
    verified = verify_records(records, receipts)
    leads, delays = [], []
    for r in records:
        if r["kind"] != "forecast":
            continue
        receipt = min(
            timestamp(x["created_at"])
            for x in receipts
            if r["hash"] in x["ledger_hashes"]
            and timestamp(r["recorded_at"])
            <= timestamp(x["created_at"])
            < timestamp(r["kickoff_utc"])
        )
        leads.append((timestamp(r["kickoff_utc"]) - receipt).total_seconds() / 60)
        delays.append((receipt - timestamp(r["recorded_at"])).total_seconds())
    return {
        **verified,
        "receipted_forecasts": len(leads),
        "minimum_receipt_lead_minutes": min(leads) if leads else None,
        "maximum_publication_delay_seconds": max(delays) if delays else None,
    }


def main():
    checked = now_utc()
    records = read_ledger()
    receipts = github_receipts() if records else []
    journal, revision = GitHubBudget().load()
    cfg = read_json(ROOT / "config/forward.json")
    month = checked.strftime("%Y-%m")
    charged = journal["months"].get(month, 0)
    checkout = Path.home() / "Library/Application Support/closing-line-lab/checkout"
    log = checkout / "runs/launchd.log"
    rows = [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []
    ctl = subprocess.run(
        ["launchctl", "print", f"gui/{os.getuid()}/com.ncoprod.closing-line-lab"],
        capture_output=True,
        text=True,
    )
    exit_code = re.search(r"last exit code = (\d+)", ctl.stdout)
    account = {
        "month": month,
        "charged": charged,
        "cap": cfg["monthly_credit_cap"],
        "remaining": journal["remaining"],
        "reserve": cfg["provider_reserve"],
        "usable_credits": max(
            0,
            min(
                cfg["monthly_credit_cap"] - charged, journal["remaining"] - cfg["provider_reserve"]
            ),
        ),
        "pending_reservation": journal.get("pending"),
        "runner_lease": journal.get("runner_lease"),
        "journal_blob_revision": revision,
    }
    health = {
        "checked_at": checked.isoformat(),
        "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "ledger_digest": digest(records),
        "publication": publication_health(records, receipts),
        "launchd": {
            **cycle_health(rows, checked),
            "loaded": ctl.returncode == 0,
            "last_exit_code": int(exit_code[1]) if exit_code else None,
        },
        "budget": account,
        "paper_bets": sum(r["kind"] == "forecast" and r["bet"] is not None for r in records),
        "scope": "Observed log coverage since first completed cycle; not an uptime SLA. "
        "GitHub creation receipts prove content timing, not hosted audit success.",
        "provider_requests_made_by_check": 0,
    }
    write_json(ROOT / "results/forward_health.json", health)
    print(json.dumps(health, indent=2))


if __name__ == "__main__":
    main()
