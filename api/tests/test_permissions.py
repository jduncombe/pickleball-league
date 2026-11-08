"""Who can see and do what: admin, user (organiser) and umpire."""

import pytest

from app.models import League, UserRole

from .helpers import BASICS, set_up_league


@pytest.fixture()
def alice(client_for):
    return client_for(UserRole.USER, "alice@example.com")


@pytest.fixture()
def bob(client_for):
    return client_for(UserRole.USER, "bob@example.com")


@pytest.fixture()
def umpire(client_for):
    return client_for(UserRole.UMPIRE, "ump@example.com")


def _match_on_court(organiser, league, court=1):
    match = organiser.get(f"/leagues/{league['id']}/matches?week=1").json()[0]
    assert organiser.post(f"/matches/{match['id']}/start", json={"court": court}).status_code == 200
    return match


# --- Organisers (users) ---------------------------------------------------------


def test_users_see_only_their_own_leagues(client, alice, bob):
    mine = set_up_league(alice, name="Alice's")
    set_up_league(bob, name="Bob's")
    assert [lg["name"] for lg in alice.get("/leagues").json()] == ["Alice's"]
    assert [lg["name"] for lg in bob.get("/leagues").json()] == ["Bob's"]
    # Admins see everything.
    assert {lg["name"] for lg in client.get("/leagues").json()} == {"Alice's", "Bob's"}
    assert client.get(f"/leagues/{mine['id']}").status_code == 200


def test_other_peoples_leagues_look_missing(alice, bob):
    league = set_up_league(alice)
    lid = league["id"]
    match = alice.get(f"/leagues/{lid}/matches").json()[0]
    team_id = match["team_a"]["id"]
    for method, url, body in [
        ("get", f"/leagues/{lid}", None),
        ("patch", f"/leagues/{lid}", {"current_week": 2}),
        ("delete", f"/leagues/{lid}", None),
        ("get", f"/leagues/{lid}/teams", None),
        ("get", f"/leagues/{lid}/matches", None),
        ("get", f"/leagues/{lid}/dashboard", None),
        ("get", f"/leagues/{lid}/standings", None),
        ("put", f"/leagues/{lid}/setup", BASICS),
        ("put", f"/leagues/{lid}/teams", {"teams": []}),
        ("post", f"/leagues/{lid}/finalize", None),
        ("post", f"/leagues/{lid}/edit", None),
        ("get", f"/teams/{team_id}", None),
        ("get", f"/matches/{match['id']}", None),
        ("post", f"/matches/{match['id']}/start", {}),
        ("put", f"/matches/{match['id']}/result", {"score_a": 11, "score_b": 2}),
        ("post", f"/matches/{match['id']}/verify", None),
        ("get", f"/scoring/leagues/{lid}/courts", None),
        ("post", f"/scoring/leagues/{lid}/courts/1/claim", None),
    ]:
        resp = bob.request(method, url, json=body)
        assert resp.status_code == 404, (method, url, resp.text)
    assert alice.get(f"/leagues/{lid}").status_code == 200  # untouched


def test_new_leagues_belong_to_their_creator(alice, session_factory):
    lid = set_up_league(alice)["id"]
    with session_factory() as db:
        assert db.get(League, lid).owner_id == alice.user.id


def test_leagues_from_before_accounts_are_admin_only(client, alice, session_factory):
    lid = set_up_league(client)["id"]
    with session_factory() as db:
        db.get(League, lid).owner_id = None
        db.commit()
    assert client.get(f"/leagues/{lid}").status_code == 200
    assert alice.get(f"/leagues/{lid}").status_code == 404


def test_users_cant_manage_accounts(alice):
    assert alice.get("/users").status_code == 404
    body = {"email": "x@example.com", "name": "X", "role": "admin", "password": "long enough password"}
    assert alice.post("/users", json=body).status_code == 404


# --- Umpires -------------------------------------------------------------------


def test_umpires_cant_manage_leagues(umpire, alice):
    lid = set_up_league(alice)["id"]
    for method, url, body in [
        ("get", "/leagues", None),
        ("post", "/leagues", BASICS),
        ("get", f"/leagues/{lid}", None),
        ("get", f"/leagues/{lid}/dashboard", None),
        ("post", f"/leagues/{lid}/edit", None),
        ("get", "/schedule-preview?num_teams=4&num_weeks=1&matches_per_week=1", None),
        ("get", "/users", None),
    ]:
        assert umpire.request(method, url, json=body).status_code == 404, url


def test_umpires_score_any_active_league(umpire, alice, bob):
    set_up_league(alice, name="Alice's")
    set_up_league(bob, name="Bob's")
    bob.post("/leagues", json={**BASICS, "name": "Bob's draft"})
    assert {lg["name"] for lg in umpire.get("/scoring/leagues").json()} == {"Alice's", "Bob's"}
    # Organisers only see their own there too.
    assert [lg["name"] for lg in alice.get("/scoring/leagues").json()] == ["Alice's"]


def test_umpire_scores_only_the_court_they_claimed(umpire, client_for, alice):
    league = set_up_league(alice, num_courts=2)
    lid = league["id"]
    match = _match_on_court(alice, league, court=1)
    result = {"score_a": 11, "score_b": 4}

    # Not claimed yet.
    assert umpire.put(f"/scoring/matches/{match['id']}/result", json=result).status_code == 409
    # Claimed by someone else.
    other = client_for(UserRole.UMPIRE, "other@example.com")
    assert other.post(f"/scoring/leagues/{lid}/courts/1/claim").status_code == 201
    assert umpire.put(f"/scoring/matches/{match['id']}/result", json=result).status_code == 409
    assert umpire.post(f"/scoring/leagues/{lid}/courts/1/claim").status_code == 409
    # Umpires can't release each other's claims...
    assert umpire.delete(f"/scoring/leagues/{lid}/courts/1/claim").status_code == 409
    # ...but the organiser can.
    assert alice.delete(f"/scoring/leagues/{lid}/courts/1/claim").status_code == 204

    claim = umpire.post(f"/scoring/leagues/{lid}/courts/1/claim", json={"device_name": "Tablet 1"})
    assert claim.status_code == 201
    assert claim.json()["claimed_by"]["name"] == umpire.user.name
    resp = umpire.put(f"/scoring/matches/{match['id']}/result", json=result)
    assert resp.status_code == 200, resp.text
    # Once it's finished, it's no longer theirs to change.
    assert (
        umpire.put(f"/scoring/matches/{match['id']}/result", json={"score_a": 11, "score_b": 6}).status_code
        == 409
    )
    assert umpire.delete(f"/scoring/leagues/{lid}/courts/1/claim").status_code == 204


def test_umpires_cant_see_leagues_in_setup(umpire, alice):
    lid = set_up_league(alice)["id"]
    alice.post(f"/leagues/{lid}/edit")
    assert umpire.get(f"/scoring/leagues/{lid}/matches").status_code == 404


# --- Admins --------------------------------------------------------------------


def test_admin_manages_accounts(client, anon):
    body = {
        "email": "Carol@Example.com",
        "name": "Carol",
        "role": "umpire",
        "password": "long enough password",
    }
    created = client.post("/users", json=body)
    assert created.status_code == 201, created.text
    user = created.json()
    assert user["email"] == "carol@example.com"
    assert user["mfa_enabled"] is False
    assert "password" not in str(user).lower()
    assert client.post("/users", json=body).status_code == 409

    updated = client.patch(f"/users/{user['id']}", json={"role": "user", "name": "Carol C"})
    assert updated.json()["role"] == "user" and updated.json()["name"] == "Carol C"
    assert any(u["email"] == "carol@example.com" for u in client.get("/users").json())


def test_role_change_and_mfa_reset_sign_the_user_out(client, alice):
    assert alice.get("/leagues").status_code == 200
    client.patch(f"/users/{alice.user.id}", json={"role": "umpire"})
    assert alice.get("/scoring/leagues").status_code == 401

    resp = client.post(f"/users/{alice.user.id}/reset-mfa")
    assert resp.json()["mfa_enabled"] is False


def test_admin_cant_lock_themselves_out(client):
    me = client.get("/auth/me").json()
    assert client.patch(f"/users/{me['id']}", json={"role": "user"}).status_code == 409
    assert client.patch(f"/users/{me['id']}", json={"is_active": False}).status_code == 409
    assert client.patch(f"/users/{me['id']}", json={"name": "Renamed"}).status_code == 200
