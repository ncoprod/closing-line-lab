"""A compare-and-swap GitHub journal is committed before any paid transmission."""

import base64
import json
import subprocess
import uuid

from .common import ROOT, now_utc
from .security import check_values, publication_scan

REPO = "ncoprod/closing-line-lab"
BRANCH = "api-budget"
FILE = "data/api_reservations.json"


class BudgetExhausted(RuntimeError):
    pass


class BudgetUncertain(RuntimeError):
    pass


def api(path, payload=None):
    command = ["gh", "api", path]
    if payload is not None:
        command += ["--method", "PUT", "--input", "-"]
    result = subprocess.run(
        command,
        input=json.dumps(payload) if payload else None,
        text=True,
        capture_output=True,
        cwd=ROOT,
    )
    if result.returncode:
        raise BudgetUncertain("Durable budget read/write failed; no further paid request permitted")
    return json.loads(result.stdout)


class GitHubBudget:
    def load(self):
        response = api(f"repos/{REPO}/contents/{FILE}?ref={BRANCH}")
        return json.loads(base64.b64decode(response["content"])), response["sha"]

    def save(self, state, revision):
        payload = json.dumps(state, indent=2) + "\n"
        check_values(payload)
        publication_scan()
        response = api(
            f"repos/{REPO}/contents/{FILE}",
            {
                "message": "chore: persist conservative API credit accounting",
                "branch": BRANCH,
                "sha": revision,
                "content": base64.b64encode(payload.encode()).decode(),
            },
        )
        return response["commit"]["sha"]

    def reserve(self, usage, cost, endpoint, cfg):
        state, revision = self.load()
        if state.get("pending"):
            raise BudgetUncertain(
                "Unreconciled paid reservation; manual provider reconciliation required"
            )
        month = now_utc().strftime("%Y-%m")
        charged = state["months"].get(month, 0)
        remaining = min(state["remaining"], usage.get("remaining", state["remaining"]))
        # Only a successful provider response can establish a billing-period reset.
        if usage.get("provider_used", state["provider_used"]) < state["provider_used"]:
            remaining = usage["remaining"]
        if charged + cost > cfg["monthly_credit_cap"] or remaining - cost < cfg["provider_reserve"]:
            raise BudgetExhausted("Durable monthly cap/provider reserve reached")
        reservation = {
            "id": uuid.uuid4().hex,
            "month": month,
            "cost": cost,
            "endpoint": endpoint,
            "reserved_at": now_utc().isoformat(),
        }
        state["months"][month] = charged + cost
        state["remaining"] = remaining - cost
        state["pending"] = reservation
        commit = self.save(state, revision)
        return reservation, commit, state

    def complete(self, reservation, remaining, used, last):
        state, revision = self.load()
        if state.get("pending") != reservation:
            raise BudgetUncertain("Reservation changed; stop rather than overwrite accounting")
        month = reservation["month"]
        state["months"][month] += max(0, last - reservation["cost"])
        state.update(
            remaining=remaining, provider_used=used, pending=None, last_reservation=reservation
        )
        self.save(state, revision)
        return state
