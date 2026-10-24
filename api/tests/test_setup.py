"""League setup: basics -> teams & players -> create the league -> edit."""

from .helpers import BASICS, default_teams, set_up_league


def _new(client, **basics):
    resp = client.post("/leagues", json={**BASICS, **basics})
    assert resp.status_code == 201
    return resp.json()


def test_new_league_starts_in_setup_without_schedule(client):
    league = _new(client, use_team_names=True)
    assert league["status"] == "setup"
    assert league["use_team_names"] is True
    assert league["created_league_at"] is None

    teams = client.get(f"/leagues/{league['id']}/teams").json()
    assert [t["position"] for t in teams] == [1, 2, 3, 4]
    assert all(t["players"] == [] for t in teams)
    assert client.get(f"/leagues/{league['id']}/matches").json() == []


def test_basics_resize_teams_during_setup(client):
    lid = _new(client)["id"]
    client.put(f"/leagues/{lid}/teams", json={"teams": default_teams(4)})

    resp = client.put(f"/leagues/{lid}/setup", json={**BASICS, "num_teams": 6})
    assert resp.status_code == 200
    teams = client.get(f"/leagues/{lid}/teams").json()
    assert [t["position"] for t in teams] == [1, 2, 3, 4, 5, 6]
    # Existing teams keep their players; new ones start empty.
    assert [len(t["players"]) for t in teams] == [2, 2, 2, 2, 0, 0]

    client.put(f"/leagues/{lid}/setup", json={**BASICS, "num_teams": 3, "matches_per_week": 2})
    assert len(client.get(f"/leagues/{lid}/teams").json()) == 3


def test_teams_step_requires_every_team(client):
    lid = _new(client)["id"]
    resp = client.put(f"/leagues/{lid}/teams", json={"teams": default_teams(3)})
    assert resp.status_code == 422
    assert "Expected 4 teams" in resp.text


def test_players_and_dupr_ids(client):
    lid = _new(client)["id"]
    teams = default_teams(4)
    teams[0]["players"] = [{"name": " Alex ", "email": "", "dupr_id": " ab12cd "}]
    assert client.put(f"/leagues/{lid}/teams", json={"teams": teams}).status_code == 200

    player = client.get(f"/leagues/{lid}/teams").json()[0]["players"][0]
    assert player["name"] == "Alex"
    assert player["dupr_id"] == "AB12CD"
    assert player["email"] is None

    teams[0]["players"] = [{"name": "Bad", "dupr_id": "no!"}]
    assert client.put(f"/leagues/{lid}/teams", json={"teams": teams}).status_code == 422


def test_create_the_league_validates_setup(client):
    lid = _new(client, use_team_names=True)["id"]
    teams = default_teams(4)
    teams[0]["name"] = "Dink Dynasty"
    teams[2]["players"] = []
    client.put(f"/leagues/{lid}/teams", json={"teams": teams})

    resp = client.post(f"/leagues/{lid}/finalize")
    assert resp.status_code == 422
    detail = resp.json()["detail"]
    assert "Team 2 needs a name" in detail
    assert "Team 3 needs at least one player" in detail
    assert client.get(f"/leagues/{lid}").json()["status"] == "setup"


def test_display_names_follow_use_team_names(client):
    teams = [
        {"name": "Dink Dynasty", "players": [{"name": "Alex"}, {"name": "Sam"}]},
        {"name": "Kitchen Crew", "players": [{"name": "Ann"}, {"name": "Bo"}, {"name": "Cy"}]},
    ]
    named = set_up_league(client, teams=teams, num_teams=2, matches_per_week=1, use_team_names=True)
    shown = [t["display_name"] for t in client.get(f"/leagues/{named['id']}/teams").json()]
    assert shown == ["Dink Dynasty", "Kitchen Crew"]

    # Same teams in a league that doesn't use team names: shown by players.
    unnamed = set_up_league(client, teams=teams, num_teams=2, matches_per_week=1, use_team_names=False)
    shown = [t["display_name"] for t in client.get(f"/leagues/{unnamed['id']}/teams").json()]
    assert shown == ["Alex & Sam", "Ann, Bo & Cy"]

    match = client.get(f"/leagues/{unnamed['id']}/matches").json()[0]
    assert {match["team_a"]["display_name"], match["team_b"]["display_name"]} == {"Alex & Sam", "Ann, Bo & Cy"}
    standings = client.get(f"/leagues/{unnamed['id']}/standings").json()
    assert sorted(r["team"]["display_name"] for r in standings) == ["Alex & Sam", "Ann, Bo & Cy"]


def test_setup_is_fixed_once_created(client, league):
    lid = league["id"]
    assert league["created_league_at"] is not None
    assert client.put(f"/leagues/{lid}/teams", json={"teams": default_teams(4)}).status_code == 409
    assert client.put(f"/leagues/{lid}/setup", json=BASICS).status_code == 409
    assert client.post(f"/leagues/{lid}/finalize").status_code == 409


def test_edit_setup_pauses_play_and_keeps_schedule(client, league):
    lid = league["id"]
    match = client.get(f"/leagues/{lid}/matches").json()[0]
    client.put(f"/matches/{match['id']}/result", json={"score_a": 11, "score_b": 4})

    edited = client.post(f"/leagues/{lid}/edit").json()
    assert edited["status"] == "setup"
    assert edited["has_played_matches"] is True
    other = client.get(f"/leagues/{lid}/matches").json()[1]
    assert client.post(f"/matches/{other['id']}/start", json={}).status_code == 409

    # Players and names can change...
    teams = default_teams(4)
    teams[0]["players"] = [{"name": "Replacement", "dupr_id": "ZZ99ZZ"}]
    assert client.put(f"/leagues/{lid}/teams", json={"teams": teams}).status_code == 200
    resp = client.put(f"/leagues/{lid}/setup", json={**BASICS, "name": "Renamed", "num_courts": 3})
    assert resp.status_code == 200

    # ...but not the shape of the season, once matches are played.
    resp = client.put(f"/leagues/{lid}/setup", json={**BASICS, "num_teams": 6})
    assert resp.status_code == 409
    assert "num_teams" in resp.text

    recreated = client.post(f"/leagues/{lid}/finalize").json()
    assert recreated["status"] == "active"
    assert recreated["name"] == "Renamed"
    assert recreated["created_league_at"] == league["created_league_at"]
    # Same schedule, result kept.
    matches = client.get(f"/leagues/{lid}/matches").json()
    assert len(matches) == 12
    assert matches[0]["status"] == "completed" and matches[0]["score_a"] == 11
    assert client.get(f"/leagues/{lid}/teams").json()[0]["players"][0]["name"] == "Replacement"


def test_edit_before_play_can_reshape_and_rebuilds_schedule(client, league):
    lid = league["id"]
    client.post(f"/leagues/{lid}/edit")
    assert client.put(f"/leagues/{lid}/setup", json={**BASICS, "num_teams": 6}).status_code == 200
    assert client.get(f"/leagues/{lid}/matches").json() == []
    client.put(f"/leagues/{lid}/teams", json={"teams": default_teams(6)})

    recreated = client.post(f"/leagues/{lid}/finalize").json()
    assert recreated["num_teams"] == 6
    # 2 weeks x 3 rounds x 3 matches per round
    assert len(client.get(f"/leagues/{lid}/matches").json()) == 18


def test_edit_refused_while_match_on_court(client, league):
    lid = league["id"]
    match = client.get(f"/leagues/{lid}/matches").json()[0]
    client.post(f"/matches/{match['id']}/start", json={})
    assert client.post(f"/leagues/{lid}/edit").status_code == 409


def test_dupr_ready_needs_every_player_to_have_a_dupr_id(client):
    teams = [
        {"players": [{"name": "A", "dupr_id": "AAAA11"}, {"name": "B", "dupr_id": "BBBB22"}]},
        {"players": [{"name": "C", "dupr_id": "CCCC33"}, {"name": "D"}]},
        {"players": [{"name": "E"}, {"name": "F"}]},
    ]
    league = set_up_league(client, teams=teams, num_teams=3, matches_per_week=2)
    shown = {t["display_name"]: t["dupr_ready"] for t in client.get(f"/leagues/{league['id']}/teams").json()}
    assert shown == {"A & B": True, "C & D": False, "E & F": False}

    # Also on the team references inside matches (used by the live view).
    refs = {
        ref["display_name"]: ref["dupr_ready"]
        for m in client.get(f"/leagues/{league['id']}/matches").json()
        for ref in (m["team_a"], m["team_b"])
    }
    assert refs == shown


def test_points_to_win_options_and_lock_after_play(client):
    assert client.post("/leagues", json={**BASICS, "points_to_win": 13}).status_code == 422
    assert _new(client)["points_to_win"] == 11  # default

    league = set_up_league(client, points_to_win=21)
    lid = league["id"]
    client.post(f"/leagues/{lid}/edit")
    # Before any play it can still change...
    assert client.put(f"/leagues/{lid}/setup", json={**BASICS, "points_to_win": 15}).status_code == 200
    client.post(f"/leagues/{lid}/finalize")

    match = client.get(f"/leagues/{lid}/matches").json()[0]
    client.put(f"/matches/{match['id']}/result", json={"score_a": 15, "score_b": 3})
    client.post(f"/leagues/{lid}/edit")
    # ...but not once results exist under the current rules.
    resp = client.put(f"/leagues/{lid}/setup", json={**BASICS, "points_to_win": 11})
    assert resp.status_code == 409
    assert "points_to_win" in resp.text


def test_matches_per_week_limited_by_opponents(client):
    resp = client.post("/leagues", json={**BASICS, "num_teams": 4, "matches_per_week": 4})
    assert resp.status_code == 422
    assert "at most 3 matches per week" in resp.text


def test_nine_teams_four_matches_per_week_end_to_end(client):
    league = set_up_league(client, teams=default_teams(9), num_teams=9, num_weeks=1, matches_per_week=4)
    matches = client.get(f"/leagues/{league['id']}/matches").json()
    per_round = {}
    for m in matches:
        per_round[m["round"]] = per_round.get(m["round"], 0) + 1
    assert per_round == {1: 4, 2: 4, 3: 4, 4: 4, 5: 2}


def test_schedule_preview(client):
    resp = client.get("/schedule-preview", params={"num_teams": 9, "num_weeks": 8, "matches_per_week": 4})
    assert resp.json() == {
        "rounds_per_week": 5,
        "games_per_week": 18,
        "has_catch_up_round": True,
        "teams_short_per_week": 0,
        "min_meetings": 4,
        "max_meetings": 4,
    }
    odd = client.get("/schedule-preview", params={"num_teams": 7, "num_weeks": 4, "matches_per_week": 3}).json()
    assert odd["teams_short_per_week"] == 1  # 7 x 3 is odd: one team a match short each week
    assert client.get("/schedule-preview", params={"num_teams": 4, "num_weeks": 2, "matches_per_week": 4}).status_code == 422
