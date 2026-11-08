"""The scoring-app endpoints and their bearer token."""

import pytest

from app import config

from .helpers import BASICS, set_up_league

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


# --- Leagues and courts -------------------------------------------------------


def _courts(client, lid):
    resp = client.get(f"/scoring/leagues/{lid}/courts", headers=AUTH)
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_court_routes_need_token(client, league):
    lid = league["id"]
    for method, url in [
        ("get", "/scoring/leagues"),
        ("get", f"/scoring/leagues/{lid}/courts"),
        ("post", f"/scoring/leagues/{lid}/courts/1/claim"),
        ("delete", f"/scoring/leagues/{lid}/courts/1/claim"),
        ("get", f"/scoring/leagues/{lid}/courts/1/match"),
    ]:
        assert client.request(method, url).status_code == 401, url


def test_list_leagues_only_active(client, league):
    client.post("/leagues", json={**BASICS, "name": "Still in setup"})
    body = client.get("/scoring/leagues", headers=AUTH).json()
    assert [lg["name"] for lg in body] == ["Autumn"]
    assert body[0] == {
        "id": league["id"],
        "name": "Autumn",
        "num_courts": 1,
        "current_week": 1,
        "points_to_win": 11,
    }


def test_claiming_hides_court_from_free_list(client):
    lid = set_up_league(client, num_courts=3)["id"]
    assert _courts(client, lid) == [
        {"court": 1, "in_use": False},
        {"court": 2, "in_use": False},
        {"court": 3, "in_use": False},
    ]

    resp = client.post(
        f"/scoring/leagues/{lid}/courts/2/claim", json={"device_name": "Tablet B"}, headers=AUTH
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["court"] == 2 and resp.json()["device_name"] == "Tablet B"
    assert [c["court"] for c in _courts(client, lid)] == [1, 3]

    # A second app can't take it, and is told who has it.
    resp = client.post(f"/scoring/leagues/{lid}/courts/2/claim", headers=AUTH)
    assert resp.status_code == 409
    assert "Tablet B" in resp.json()["detail"]

    # Releasing offers it again; releasing a free court is a no-op.
    assert client.delete(f"/scoring/leagues/{lid}/courts/2/claim", headers=AUTH).status_code == 204
    assert client.delete(f"/scoring/leagues/{lid}/courts/2/claim", headers=AUTH).status_code == 204
    assert [c["court"] for c in _courts(client, lid)] == [1, 2, 3]
    assert client.post(f"/scoring/leagues/{lid}/courts/2/claim", headers=AUTH).status_code == 201


def test_claims_are_per_league(client):
    first = set_up_league(client, num_courts=2)["id"]
    second = set_up_league(client, num_courts=2)["id"]
    assert client.post(f"/scoring/leagues/{first}/courts/1/claim", headers=AUTH).status_code == 201
    assert [c["court"] for c in _courts(client, second)] == [1, 2]
    assert client.post(f"/scoring/leagues/{second}/courts/1/claim", headers=AUTH).status_code == 201


def test_free_courts_show_which_are_in_use(client):
    lid = set_up_league(client, num_courts=2)["id"]
    match = _first_match(client, {"id": lid})
    client.post(f"/matches/{match['id']}/start", json={"court": 2})
    assert _courts(client, lid) == [{"court": 1, "in_use": False}, {"court": 2, "in_use": True}]


def test_claim_rejects_unknown_court_and_setup_league(client, league):
    lid = league["id"]
    assert client.post(f"/scoring/leagues/{lid}/courts/0/claim", headers=AUTH).status_code == 404
    assert client.post(f"/scoring/leagues/{lid}/courts/4/claim", headers=AUTH).status_code == 404
    assert client.post("/scoring/leagues/999/courts/1/claim", headers=AUTH).status_code == 404

    client.post(f"/leagues/{lid}/edit")
    assert client.post(f"/scoring/leagues/{lid}/courts/1/claim", headers=AUTH).status_code == 409
    assert client.get(f"/scoring/leagues/{lid}/courts", headers=AUTH).status_code == 409


def test_fewer_courts_drops_claims_beyond_them_from_view(client):
    lid = set_up_league(client, num_courts=3)["id"]
    client.post(f"/scoring/leagues/{lid}/courts/3/claim", headers=AUTH)
    client.post(f"/leagues/{lid}/edit")
    resp = client.put(f"/leagues/{lid}/setup", json={**BASICS, "num_courts": 2})
    assert resp.status_code == 200, resp.text
    client.post(f"/leagues/{lid}/finalize")
    assert [c["court"] for c in _courts(client, lid)] == [1, 2]
    assert client.get(f"/scoring/leagues/{lid}/courts/3/match", headers=AUTH).status_code == 404


def test_deleting_a_league_deletes_its_claims(client, league):
    lid = league["id"]
    client.post(f"/scoring/leagues/{lid}/courts/1/claim", headers=AUTH)
    assert client.delete(f"/leagues/{lid}").status_code == 204
    # SQLite reuses the id, so a leftover claim would block the new league's court.
    other = set_up_league(client)["id"]
    assert [c["court"] for c in _courts(client, other)] == [1]


# --- The match on a court -----------------------------------------------------


def test_court_match(client):
    lid = set_up_league(client, num_courts=2, points_to_win=15)["id"]
    url = f"/scoring/leagues/{lid}/courts/2/match"

    body = client.get(url, headers=AUTH).json()
    assert body == {
        "league_id": lid,
        "league_name": "Autumn",
        "court": 2,
        "points_to_win": 15,
        "claim": None,
        "match": None,
    }

    client.post(f"/scoring/leagues/{lid}/courts/2/claim", json={"device_name": "Tablet"}, headers=AUTH)
    match = _first_match(client, {"id": lid})
    client.post(f"/matches/{match['id']}/start", json={"court": 2})
    body = client.get(url, headers=AUTH).json()
    assert body["claim"]["device_name"] == "Tablet"
    assert body["match"]["id"] == match["id"]
    assert body["match"]["status"] == "in_progress"
    assert body["match"]["team_a"]["display_name"] == match["team_a"]["display_name"]

    # Once the score is in, the court is free again.
    resp = client.put(
        f"/scoring/matches/{match['id']}/result", json={"score_a": 15, "score_b": 9}, headers=AUTH
    )
    assert resp.status_code == 200, resp.text
    assert client.get(url, headers=AUTH).json()["match"] is None


def test_court_match_unknown_court(client, league):
    lid = league["id"]
    assert client.get(f"/scoring/leagues/{lid}/courts/9/match", headers=AUTH).status_code == 404
    assert client.get("/scoring/leagues/999/courts/1/match", headers=AUTH).status_code == 404


def test_simultaneous_claims_one_wins(client, league, monkeypatch):
    """The unique constraint settles a race the up-front check misses."""
    from app.routers import scoring

    lid = league["id"]
    url = f"/scoring/leagues/{lid}/courts/1/claim"
    assert client.post(url, json={"device_name": "First"}, headers=AUTH).status_code == 201

    real_claim = scoring._claim
    calls = []

    def miss_first_check(db, league_id, court):
        calls.append(court)
        return None if len(calls) == 1 else real_claim(db, league_id, court)

    monkeypatch.setattr(scoring, "_claim", miss_first_check)
    resp = client.post(url, json={"device_name": "Second"}, headers=AUTH)
    assert resp.status_code == 409
    assert "First" in resp.json()["detail"]
