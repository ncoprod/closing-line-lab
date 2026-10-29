import json

import pytest

from closing_line_lab.budget import BudgetUncertain, GitHubBudget


class FileJournal(GitHubBudget):
    def __init__(self, path):
        self.path = path
        if not path.exists():
            path.write_text(
                json.dumps({"months": {}, "remaining": 500, "provider_used": 0, "pending": None})
            )

    def load(self):
        return json.loads(self.path.read_text()), self.path.read_text()

    def save(self, state, revision):
        if self.path.read_text() != revision:
            raise BudgetUncertain("Concurrent write")
        self.path.write_text(json.dumps(state))
        return "synthetic-remote-commit"


def test_reservation_survives_runner_loss_and_provider_reset(tmp_path):
    journal = FileJournal(tmp_path / "remote.json")
    cfg = {"monthly_credit_cap": 400, "provider_reserve": 100}
    journal.reserve({"remaining": 500}, 1, "odds", cfg)
    # An independent runner has only the old main-branch accounting, even after a reset.
    fresh = FileJournal(journal.path)
    with pytest.raises(BudgetUncertain, match="Unreconciled"):
        fresh.reserve({"months": {}, "remaining": 500, "provider_used": 0}, 1, "odds", cfg)
    state, _ = fresh.load()
    assert sum(state["months"].values()) == 1
    assert state["pending"]["cost"] == 1


def test_first_league_success_second_league_failure_remains_durable(tmp_path):
    journal = FileJournal(tmp_path / "remote.json")
    cfg = {"monthly_credit_cap": 400, "provider_reserve": 100}
    first, _, _ = journal.reserve({"remaining": 500}, 1, "odds", cfg)
    journal.complete(first, 499, 1, 1)
    journal.reserve({"remaining": 499, "provider_used": 1}, 1, "odds", cfg)
    fresh = FileJournal(journal.path)
    with pytest.raises(BudgetUncertain):
        fresh.reserve({"remaining": 500}, 1, "odds", cfg)
    state, _ = fresh.load()
    assert sum(state["months"].values()) == 2
