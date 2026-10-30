"""Shared hourly entry point for launchd and Actions; fail closed on uncertain ownership."""

import argparse
import json
import os
import subprocess
import sys
import uuid
from datetime import datetime, timedelta

from closing_line_lab.budget import BudgetUncertain, GitHubBudget
from closing_line_lab.common import ROOT, now_utc, read_json

SERVICE = "com.ncoprod.closing-line-lab.ODDS_API_KEY"


class CycleLease:
    def __init__(self, journal, runner, slot):
        self.journal = journal
        self.slot = slot
        self.owner = {"id": uuid.uuid4().hex, "runner": runner, "slot": slot}

    def acquire(self):
        state, revision = self.journal.load()
        if state.get("runner_lease") or state.get("completed_hour") == self.slot:
            return False
        state["runner_lease"] = self.owner
        # A competing writer loses the blob-SHA compare-and-swap before any API call.
        self.journal.save(state, revision)
        return True

    def release(self, completed):
        state, revision = self.journal.load()
        if state.get("runner_lease") != self.owner:
            raise BudgetUncertain("Runner ownership changed; manual reconciliation required")
        state["runner_lease"] = None
        if completed:
            state["completed_hour"] = self.slot
        self.journal.save(state, revision)


def credentials():
    env = os.environ.copy()
    if env.get("ODDS_API_KEY"):
        return env
    if sys.platform == "darwin":
        found = subprocess.run(
            ["/usr/bin/security", "find-generic-password", "-s", SERVICE, "-w"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if found.returncode == 0 and found.stdout.strip():
            env["ODDS_API_KEY"] = found.stdout.strip()
            return env
    raise RuntimeError("ODDS_API_KEY unavailable in environment or unlocked login Keychain")


def command(args, env):
    result = subprocess.run(args, cwd=ROOT, env=env, capture_output=True, text=True)
    if result.returncode:
        # Provider exception text can contain authenticated URLs; never echo captured output.
        raise RuntimeError(f"Step {args[0]} {args[1]} failed (exit {result.returncode})")
    return result.stdout


def score_due():
    now = now_utc()
    state = ROOT / "data/forward_state.json"
    dates = read_json(state).get("score_dates", {}) if state.exists() else {}
    rows = [json.loads(line) for line in (ROOT / "data/ledger.jsonl").read_text().splitlines()]
    settled = {r["match_id"] for r in rows if r["kind"] == "settlement"}
    return now.hour >= 7 and any(
        r["kind"] == "forecast"
        and r["match_id"] not in settled
        and dates.get(r["sport"]) != now.date().isoformat()
        and datetime.fromisoformat(r["kickoff_utc"]) + timedelta(hours=3) < now
        for r in rows
    )


def publication(args, env):
    output = command(args, env)
    # Git prints the commit summary before the CLI's final JSON object.
    return json.loads(output[output.rfind("\n{") + 1 :])


def run(runner):
    env = credentials()
    slot = now_utc().strftime("%Y-%m-%dT%H")
    lease = CycleLease(GitHubBudget(), runner, slot)
    if not lease.acquire():
        return {"status": "SKIPPED_BUSY_OR_COMPLETED", "slot": slot}
    completed = False
    try:
        if command(["git", "status", "--porcelain"], env).strip():
            raise RuntimeError("Runner checkout is dirty; retain it for manual inspection")
        command(["git", "pull", "--ff-only", "origin", "main"], env)
        cll = [sys.executable, "-m", "closing_line_lab.cli"]
        command([*cll, "forward"], env)
        command([*cll, "actions-evidence"], env)
        command([*cll, "report"], env)
        forecast_publication = publication([*cll, "publish"], env)
        settlement_publication = {"status": "NO_RESULTS_DUE"}
        if score_due():
            command([*cll, "score"], env)
            command([*cll, "report"], env)
            settlement_publication = publication([*cll, "publish", "--settlements-only"], env)
        completed = True
        return {
            "status": "COMPLETED",
            "runner": runner,
            "slot": slot,
            "checked_at": now_utc().isoformat(),
            "forecast_publication": forecast_publication,
            "settlement_publication": settlement_publication,
            "head": command(["git", "rev-parse", "HEAD"], env).strip(),
        }
    finally:
        # A failure after capture may precede publication. Retain ownership so another
        # runner cannot spend again for those unpublished decisions without reconciliation.
        if completed:
            lease.release(completed=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--runner", choices=["launchd", "github"], required=True)
    args = parser.parse_args()
    try:
        result = run(args.runner)
    except Exception as error:
        print(json.dumps({"status": "FAILED", "error_type": type(error).__name__}))
        return 1
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
