"""The scoring-app endpoints and their bearer token."""

import pytest

from app import config

AUTH = {"Authorization": f"Bearer {config.SCORING_API_TOKEN}"}


def _first_match(client, league):
    return client.get(f"/scoring/leagues/{league['id']}/matches", headers=AUTH).json()["matches"][0]


@pytest.mark.parametrize(
    "headers",
    [{}, {"Authorization": "Bearer wrong"}, {"Authorization": f"Basic {config.SCORING_API_TOKEN}"}],
    ids=["missing", "wrong-token", "wrong-scheme"],
)
def test_token_required(client, league, headers):
    lid = league["id"]
    for resp in (
        client.get(f"/scoring/leagues/{lid}/matches", headers=headers),
        client.put("/scoring/matches/1/result", json={"score_a": 11, "score_b": 7}, headers=headers),
    ):
        # 401, never 403 (CloudFront rewrites 403s to the site's 404 page).
        assert resp.status_code == 401
        assert resp.headers["WWW-Authenticate"] == "Bearer"
    assert client.get(f"/leagues/{lid}/matches?week=1").json()[0]["status"] == "scheduled"


def test_token_can_be_overridden(client, league, monkeypatch):
    monkeypatch.setattr(config, "SCORING_API_TOKEN", "local-token")
    url = f"/scoring/leagues/{league['id']}/matches"
    assert client.get(url, headers=AUTH).status_code == 401
    assert client.get(url, headers={"Authorization": "Bearer local-token"}).status_code == 200


def test_list_matches_defaults_to_current_week(client, league):
    lid = league["id"]
    body = client.get(f"/scoring/leagues/{lid}/matches", headers=AUTH).json()
    assert body["league_name"] == "Autumn"
    assert body["points_to_win"] == 11
    assert body["week"] == 1
    assert body["matches"] and {m["week"] for m in body["matches"]} == {1}
    assert body["matches"][0]["team_a"]["display_name"]

    client.patch(f"/leagues/{lid}", json={"current_week": 2})
    body = client.get(f"/scoring/leagues/{lid}/matches", headers=AUTH).json()
    assert body["week"] == 2 and {m["week"] for m in body["matches"]} == {2}

    body = client.get(f"/scoring/leagues/{lid}/matches?week=1&status=completed", headers=AUTH).json()
    assert body["week"] == 1 and body["matches"] == []


def test_list_matches_unknown_league(client):
    assert client.get("/scoring/leagues/999/matches", headers=AUTH).status_code == 404


def test_record_result(client, league):
    match = _first_match(client, league)
    resp = client.put(
        f"/scoring/matches/{match['id']}/result", json={"score_a": 11, "score_b": 7}, headers=AUTH
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "completed"
    assert (resp.json()["score_a"], resp.json()["score_b"]) == (11, 7)


def test_record_result_applies_score_rules_and_lock(client, league):
    match = _first_match(client, league)
    url = f"/scoring/matches/{match['id']}/result"

    resp = client.put(url, json={"score_a": 11, "score_b": 10}, headers=AUTH)
    assert resp.status_code == 422
    assert resp.json()["detail"][0]["type"] == "score_rules"

    assert client.put(url, json={"score_a": 11, "score_b": 9}, headers=AUTH).status_code == 200
    client.post(f"/matches/{match['id']}/verify")
    assert client.put(url, json={"score_a": 11, "score_b": 5}, headers=AUTH).status_code == 409
