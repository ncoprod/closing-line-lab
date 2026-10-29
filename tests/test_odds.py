import json
from pathlib import Path

import pytest

from closing_line_lab import odds


def event():
    return {
        "id": "synthetic",
        "sport_key": "soccer_epl",
        "commence_time": "2026-11-01T15:00:00Z",
        "home_team": "A",
        "away_team": "B",
        "bookmakers": [
            {
                "\u006bey": "betfair_ex_eu",
                "last_update": "2026-11-01T14:00:00Z",
                "markets": [
                    {
                        "\u006bey": "h2h",
                        "outcomes": [
                            {"name": "B", "price": 4.0},
                            {"name": "Draw", "price": 3.2},
                            {"name": "A", "price": 2.2},
                        ],
                    }
                ],
            }
        ],
    }


def test_three_way_mapping_freshness_commission_and_no_in_play():
    e, cfg = event(), odds.forward_config()
    observed = odds.quote(e, cfg["benchmark_priority"], "2026-11-01T14:01:00Z", cfg)
    assert observed["prices"] == [2.2, 3.2, 4.0]
    assert observed["effective_prices"] == pytest.approx([2.176, 3.156, 3.94])
    assert odds.quote(e, cfg["benchmark_priority"], "2026-11-01T14:45:00Z", cfg) is None
    assert odds.quote(e, cfg["benchmark_priority"], e["commence_time"], cfg) is None
    e["bookmakers"][0]["last_update"] = "2026-11-01T14:01:02Z"
    assert odds.quote(e, cfg["benchmark_priority"], "2026-11-01T14:01:00Z", cfg)
    e["bookmakers"][0]["last_update"] = "2026-11-01T14:01:06Z"
    assert odds.quote(e, cfg["benchmark_priority"], "2026-11-01T14:01:00Z", cfg) is None
    e["bookmakers"][0]["last_update"] = "2026-11-01T14:00:00Z"
    e["bookmakers"][0]["markets"][0]["outcomes"].pop(1)
    assert odds.quote(e, cfg["benchmark_priority"], "2026-11-01T14:01:00Z", cfg) is None


def test_client_documented_response_cache_headers_and_budget(tmp_path, monkeypatch):
    documented = (Path(__file__).parent / "fixtures/docs_odds.json").read_bytes()
    monkeypatch.setenv("ODDS_API_KEY", "synthetic-credential-never-persist")
    monkeypatch.setattr(odds, "ROOT", tmp_path)
    monkeypatch.setattr(odds, "USAGE", tmp_path / "usage.json")
    monkeypatch.setattr(odds, "MANIFEST", tmp_path / "manifest.jsonl")
    cfg = json.loads((Path(__file__).parents[1] / "config/forward.json").read_text())
    monkeypatch.setattr(odds, "forward_config", lambda: cfg)

    class Response:
        headers = {"x-requests-remaining": "499", "x-requests-used": "1", "x-requests-last": "1"}

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def read(self):
            return documented

    calls = []

    def respond(request, **kw):
        calls.append(request)
        return Response()

    monkeypatch.setattr(odds.urllib.request, "urlopen", respond)
    client = odds.OddsClient()
    data, entry = client.get("soccer_epl", "odds")
    assert data[0]["bookmakers"][0]["key"]
    assert entry["credits_remaining"] == 499
    assert "apiKey" not in odds.MANIFEST.read_text()
    assert "synthetic-credential" not in odds.MANIFEST.read_text()
    client.usage["remaining"] = 100
    with pytest.raises(odds.BudgetExhausted):
        client.get("soccer_epl", "odds")
    assert len(calls) == 1
    client.usage["remaining"] = 500
    client.usage["months"] = {odds.now_utc().strftime("%Y-%m"): 400}
    with pytest.raises(odds.BudgetExhausted):
        client.get("soccer_epl", "scores")
    assert len(calls) == 1


def test_credential_not_in_error_message(monkeypatch, tmp_path):
    monkeypatch.setenv("ODDS_API_KEY", "synthetic-do-not-reveal")
    monkeypatch.setattr(odds, "USAGE", tmp_path / "usage.json")

    def fail(request, **kw):
        raise odds.urllib.error.HTTPError(request.full_url, 401, "invalid", {}, None)

    monkeypatch.setattr(odds.urllib.request, "urlopen", fail)
    with pytest.raises(RuntimeError, match="HTTP 401") as caught:
        odds.OddsClient().get("soccer_epl", "events")
    assert "synthetic-do-not-reveal" not in str(caught.value)
