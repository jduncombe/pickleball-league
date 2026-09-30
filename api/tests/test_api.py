def test_create_league_builds_teams_and_schedule(client, league):
    teams = client.get(f"/leagues/{league['id']}/teams").json()
    assert [t["name"] for t in teams] == ["Team 1", "Team 2", "Team 3", "Team 4"]

    matches = client.get(f"/leagues/{league['id']}/matches").json()
    # 2 weeks x 3 rounds x 2 matches per round
    assert len(matches) == 12
    assert {m["week"] for m in matches} == {1, 2}


def test_players_with_dupr_id(client, league):
    team = client.get(f"/leagues/{league['id']}/teams").json()[0]
    resp = client.post(
        f"/teams/{team['id']}/players",
        json={"name": "Alex", "email": "", "dupr_id": " ab12cd "},
    )
    assert resp.status_code == 201
    player = resp.json()
    assert player["dupr_id"] == "AB12CD"
    assert player["email"] is None

    bad = client.post(f"/teams/{team['id']}/players", json={"name": "B", "dupr_id": "no!"})
    assert bad.status_code == 422

    team = client.get(f"/teams/{team['id']}").json()
    assert [p["name"] for p in team["players"]] == ["Alex"]


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


def test_regenerate_schedule_blocked_after_start(client, league):
    lid = league["id"]
    assert client.post(f"/leagues/{lid}/schedule").status_code == 200
    match = client.get(f"/leagues/{lid}/matches").json()[0]
    client.post(f"/matches/{match['id']}/start", json={})
    assert client.post(f"/leagues/{lid}/schedule").status_code == 409


def test_current_week_bounds(client, league):
    lid = league["id"]
    assert client.patch(f"/leagues/{lid}", json={"current_week": 2}).status_code == 200
    assert client.patch(f"/leagues/{lid}", json={"current_week": 3}).status_code == 422
