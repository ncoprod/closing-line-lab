import copy
import importlib.util
import plistlib
from pathlib import Path

import pytest

from closing_line_lab.budget import BudgetUncertain


def load(name):
    path = Path(__file__).resolve().parents[1] / f"ops/{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


runner = load("run_cycle")
installer = load("install_launchd")


class Journal:
    def __init__(self):
        self.state = {"months": {"2026-10": 2}, "remaining": 498, "pending": None}
        self.revision = 0
        self.competitor = None

    def load(self):
        return copy.deepcopy(self.state), self.revision

    def save(self, state, revision):
        if self.competitor:
            competitor, self.competitor = self.competitor, None
            assert competitor.acquire()
        if revision != self.revision:
            raise BudgetUncertain("Lost compare-and-swap")
        self.state = copy.deepcopy(state)
        self.revision += 1


def test_two_runners_serialize_and_deduplicate_hour():
    journal = Journal()
    mac = runner.CycleLease(journal, "launchd", "2026-10-30T05")
    github = runner.CycleLease(journal, "github", mac.slot)
    assert mac.acquire()
    assert not github.acquire()
    mac.release(completed=True)
    assert not github.acquire()
    assert runner.CycleLease(journal, "github", "2026-10-30T06").acquire()


def test_racing_compare_and_swap_loser_cannot_start():
    journal = Journal()
    mac = runner.CycleLease(journal, "launchd", "hour")
    github = runner.CycleLease(journal, "github", "hour")
    journal.competitor = github
    with pytest.raises(BudgetUncertain):
        mac.acquire()
    assert journal.state["runner_lease"] == github.owner


def test_failed_cycle_preserves_credit_reservation_and_retries_same_hour():
    journal = Journal()
    mac = runner.CycleLease(journal, "launchd", "hour")
    assert mac.acquire()
    # The existing paid-call journal updates state while the whole-cycle lease is held.
    journal.state.update(pending={"cost": 1}, remaining=497, months={"2026-10": 3})
    mac.release(completed=False)
    assert journal.state["pending"] == {"cost": 1}
    assert journal.state["remaining"] == 497
    assert journal.state["months"] == {"2026-10": 3}
    assert "completed_hour" not in journal.state
    assert runner.CycleLease(journal, "github", "hour").acquire()


def test_failed_publication_does_not_mark_hour_completed(monkeypatch):
    journal = Journal()
    monkeypatch.setattr(runner, "GitHubBudget", lambda: journal)
    monkeypatch.setattr(runner, "credentials", lambda: {})
    monkeypatch.setattr(runner, "command", lambda *args: "")

    def fail(*args):
        raise RuntimeError("push failed")

    monkeypatch.setattr(runner, "publication", fail)
    with pytest.raises(RuntimeError, match="push failed"):
        runner.run("launchd")
    assert journal.state["runner_lease"] is None
    assert "completed_hour" not in journal.state


def test_plist_contains_only_paths_and_schedule(monkeypatch, tmp_path):
    monkeypatch.setenv("ODDS_API_KEY", "synthetic-placeholder")
    cfg = installer.configuration(tmp_path, "/test/uv")
    payload = plistlib.dumps(cfg)
    assert b"synthetic-placeholder" not in payload
    assert b"ODDS_API_KEY" not in payload
    assert cfg["StartCalendarInterval"] == {"Minute": 5}
    assert cfg["Label"] == "com.ncoprod.closing-line-lab"


def test_keychain_secret_is_captured_never_passed_in_argv(monkeypatch):
    monkeypatch.delenv("ODDS_API_KEY", raising=False)
    monkeypatch.setattr(runner.sys, "platform", "darwin")

    def found(args, **kwargs):
        assert "synthetic-placeholder" not in " ".join(args)
        assert kwargs["capture_output"]
        return type("Result", (), {"returncode": 0, "stdout": "synthetic-placeholder\n"})()

    monkeypatch.setattr(runner.subprocess, "run", found)
    assert runner.credentials()["ODDS_API_KEY"] == "synthetic-placeholder"


def test_publication_parses_git_summary_before_cli_json(monkeypatch):
    monkeypatch.setattr(
        runner, "command", lambda *args: 'commit summary\n{\n "status": "PUSHED"\n}\n'
    )
    assert runner.publication([], {}) == {"status": "PUSHED"}
