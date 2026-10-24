"""Play once a league is active: dashboard, courts, results, standings."""

from .helpers import set_up_league


def test_created_league_has_schedule(client, league):
    assert league["status"] == "active"
    matches = client.get(f"/leagues/{league['id']}/matches").json()
    # 2 weeks x 3 rounds x 2 matches per round
    assert len(matches) == 12
    assert {m["week"] for m in matches} == {1, 2}


def test_dashboard_start_and_result_flow(client, league):
    lid = league["id"]
    dash = client.get(f"/leagues/{lid}/dashboard").json()
    assert dash["week"] == 1
    assert dash["free_courts"] == [1]
    assert dash["in_progress"] == []
    assert len(dash["available"]) == 6

    first = dash["available"][0]
    started = client.post(f"/matches/{first['id']}/start", json={}).json()
    assert started["status"] == "in_progress"
    assert started["court"] == 1

    dash = client.get(f"/leagues/{lid}/dashboard").json()
    assert dash["free_courts"] == []
    assert [m["id"] for m in dash["in_progress"]] == [first["id"]]
    busy = {first["team_a"]["id"], first["team_b"]["id"]}
    for m in dash["available"]:
        assert not busy & {m["team_a"]["id"], m["team_b"]["id"]}
    assert all(busy & {m["team_a"]["id"], m["team_b"]["id"]} for m in dash["waiting"])

    # Only one court: another match can't start.
    other = dash["available"][0]
    assert client.post(f"/matches/{other['id']}/start", json={}).status_code == 409

    resp = client.put(f"/matches/{first['id']}/result", json={"score_a": 11, "score_b": 7})
    assert resp.json()["status"] == "completed"

    dash = client.get(f"/leagues/{lid}/dashboard").json()
    assert dash["free_courts"] == [1]
    assert dash["completed_count"] == 1

    standings = client.get(f"/leagues/{lid}/standings").json()
    assert standings[0]["team"]["id"] == first["team_a"]["id"]
    assert standings[0]["wins"] == 1
    assert standings[0]["point_diff"] == 4


def test_result_rejects_tie(client, league):
    match = client.get(f"/leagues/{league['id']}/matches").json()[0]
    resp = client.put(f"/matches/{match['id']}/result", json={"score_a": 9, "score_b": 9})
    assert resp.status_code == 422


def test_current_week_bounds(client, league):
    lid = league["id"]
    assert client.patch(f"/leagues/{lid}", json={"current_week": 2}).status_code == 200
    assert client.patch(f"/leagues/{lid}", json={"current_week": 3}).status_code == 422


def test_result_must_follow_league_scoring_rules(client):
    league = set_up_league(client, points_to_win=15)
    assert league["points_to_win"] == 15
    match = client.get(f"/leagues/{league['id']}/matches").json()[0]

    resp = client.put(f"/matches/{match['id']}/result", json={"score_a": 15, "score_b": 14})
    assert resp.status_code == 422
    errors = resp.json()["detail"]
    assert [e["loc"] for e in errors] == [["body", "score_b"]]
    assert errors[0]["msg"].startswith("15-14 isn't finished: a game must be won by 2")

    resp = client.put(f"/matches/{match['id']}/result", json={"score_a": 16, "score_b": 13})
    assert [e["loc"][-1] for e in resp.json()["detail"]] == ["score_a"]

    resp = client.put(f"/matches/{match['id']}/result", json={"score_a": 14, "score_b": 16})
    assert resp.status_code == 200
    assert resp.json()["status"] == "completed"


def test_verified_result_is_locked(client, league):
    match = client.get(f"/leagues/{league['id']}/matches").json()[0]
    assert client.post(f"/matches/{match['id']}/verify").status_code == 409  # not played yet

    client.put(f"/matches/{match['id']}/result", json={"score_a": 11, "score_b": 8})
    verified = client.post(f"/matches/{match['id']}/verify").json()
    assert verified["verified_at"] is not None

    resp = client.put(f"/matches/{match['id']}/result", json={"score_a": 11, "score_b": 9})
    assert resp.status_code == 409
    assert client.get(f"/matches/{match['id']}").json()["score_b"] == 8
