import json
from pathlib import Path

import pytest

from app import terms
from app.terms import DEFAULT_TERMS, merge_terms

from .helpers import BASICS, default_teams, set_up_league

WEB_DEFAULTS = Path(__file__).resolve().parents[2] / "web" / "src" / "lib" / "default-terms.json"


@pytest.mark.skipif(not WEB_DEFAULTS.exists(), reason="web app not alongside the API")
def test_defaults_match_the_web_app():
    assert DEFAULT_TERMS == json.loads(WEB_DEFAULTS.read_text())


def test_merge_rules():
    merged = merge_terms({"league": {"one": "ladder"}, "team": {"one": "pair", "other": "pairs"},
                          "match": {"one": "event", "article": "an"}})
    assert merged["league"] == {"one": "ladder", "other": "ladders", "article": "a"}  # simple plural
    assert merged["team"]["other"] == "pairs"
    assert merged["match"]["article"] == "an"
    assert merged["court"] == DEFAULT_TERMS["court"]  # untouched


def test_example_brand_terms_apply_to_api_messages(client, monkeypatch):
    brand = Path(__file__).resolve().parents[2] / "web" / "brands" / "example" / "terms.json"
    overrides = json.loads(brand.read_text()) if brand.exists() else {"team": {"one": "pair"}}
    monkeypatch.setattr(terms, "TERMS", merge_terms(overrides))

    # Fallback display name and setup validation use the brand's words.
    lid = client.post("/leagues", json=BASICS).json()["id"]
    assert client.get(f"/leagues/{lid}/teams").json()[0]["display_name"] == "Pair 1"
    teams = default_teams(4)
    teams[1]["players"] = []
    client.put(f"/leagues/{lid}/teams", json={"teams": teams})
    assert client.post(f"/leagues/{lid}/finalize").json()["detail"] == "Pair 2 needs at least one player"

    resp = client.post("/leagues", json={**BASICS, "num_teams": 3, "matches_per_week": 3})
    assert "With 3 pairs, each pair can play at most 2 fixtures per" in resp.text

    league = set_up_league(client)
    assert client.get("/matches/99999").json()["detail"] == "Fixture 99999 not found"
    match = client.get(f"/leagues/{league['id']}/matches").json()[0]
    resp = client.put(f"/matches/{match['id']}/result", json={"score_a": 11, "score_b": 10})
    assert "a game must be won by 2" in resp.json()["detail"][0]["msg"]
