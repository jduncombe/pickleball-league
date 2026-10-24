def test_create_league_builds_teams_and_schedule(client, league):
    teams = client.get(f"/leagues/{league['id']}/teams").json()
    # No team details given: unnamed teams, shown by position.
    assert [t["name"] for t in teams] == [None, None, None, None]
    assert [t["display_name"] for t in teams] == ["Team 1", "Team 2", "Team 3", "Team 4"]

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


def _setup_league(client, teams, **overrides):
    body = {"name": "Setup", "num_teams": len(teams), "num_weeks": 1,
            "rounds_per_week": 1, "num_courts": 2, "teams": teams, **overrides}
    return client.post("/leagues", json=body)


def test_teams_created_at_setup_with_optional_names(client):
    resp = _setup_league(client, [
        {"name": "Dink Dynasty", "players": [{"name": "Alex"}, {"name": "Sam", "dupr_id": "ab12cd"}]},
        {"name": "  ", "players": [{"name": "Jo"}, {"name": "Kim"}]},
        {"players": [{"name": "Lee"}]},
        {},
    ])
    assert resp.status_code == 201
    teams = client.get(f"/leagues/{resp.json()['id']}/teams").json()

    assert [t["position"] for t in teams] == [1, 2, 3, 4]
    assert [t["name"] for t in teams] == ["Dink Dynasty", None, None, None]
    assert [t["display_name"] for t in teams] == ["Dink Dynasty", "Jo & Kim", "Lee", "Team 4"]
    assert [p["dupr_id"] for p in teams[0]["players"]] == [None, "AB12CD"]


def test_display_name_used_in_matches_and_standings(client):
    resp = _setup_league(client, [
        {"players": [{"name": "Alex"}, {"name": "Sam"}]},
        {"name": "Kitchen Crew"},
    ])
    lid = resp.json()["id"]
    match = client.get(f"/leagues/{lid}/matches").json()[0]
    names = {match["team_a"]["display_name"], match["team_b"]["display_name"]}
    assert names == {"Alex & Sam", "Kitchen Crew"}

    standings = client.get(f"/leagues/{lid}/standings").json()
    assert sorted(r["team"]["display_name"] for r in standings) == ["Alex & Sam", "Kitchen Crew"]


def test_team_count_must_match_num_teams(client):
    resp = _setup_league(client, [{"name": "A"}, {"name": "B"}], num_teams=3)
    assert resp.status_code == 422
    assert "expected 3 teams" in resp.text


def test_team_name_can_be_cleared(client):
    resp = _setup_league(client, [
        {"name": "Named", "players": [{"name": "Alex"}, {"name": "Sam"}]},
        {"name": "Other"},
    ])
    team = client.get(f"/leagues/{resp.json()['id']}/teams").json()[0]

    cleared = client.patch(f"/teams/{team['id']}", json={"name": ""}).json()
    assert cleared["name"] is None
    assert cleared["display_name"] == "Alex & Sam"

    renamed = client.patch(f"/teams/{team['id']}", json={"name": "Renamed"}).json()
    assert renamed["display_name"] == "Renamed"
