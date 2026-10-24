"""Shared test helpers for driving league setup."""

BASICS = {"name": "Autumn", "num_teams": 4, "num_weeks": 2, "rounds_per_week": 3, "num_courts": 1}


def default_teams(num_teams: int) -> list[dict]:
    return [
        {"players": [{"name": f"P{pos}a"}, {"name": f"P{pos}b"}]}
        for pos in range(1, num_teams + 1)
    ]


def set_up_league(client, teams=None, **basics) -> dict:
    """Run the whole setup flow: basics -> teams & players -> create the league."""
    body = {**BASICS, **basics}
    league = client.post("/leagues", json=body)
    assert league.status_code == 201, league.text
    lid = league.json()["id"]
    resp = client.put(f"/leagues/{lid}/teams", json={"teams": teams or default_teams(body["num_teams"])})
    assert resp.status_code == 200, resp.text
    resp = client.post(f"/leagues/{lid}/finalize")
    assert resp.status_code == 200, resp.text
    return resp.json()
