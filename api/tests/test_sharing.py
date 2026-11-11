"""Sharing a league with other users."""

import pytest

from app.models import UserRole

from .helpers import set_up_league


@pytest.fixture()
def alice(client_for):
    return client_for(UserRole.USER, "alice@example.com")


@pytest.fixture()
def bob(client_for):
    return client_for(UserRole.USER, "bob@example.com")


@pytest.fixture()
def carol(client_for):
    return client_for(UserRole.USER, "carol@example.com")


def _share(owner, lid, email):
    return owner.post(f"/leagues/{lid}/members", json={"email": email})


def test_sharing_gives_access(alice, bob):
    league = set_up_league(alice, name="Alice's")
    lid = league["id"]
    assert bob.get(f"/leagues/{lid}").status_code == 404

    resp = _share(alice, lid, " Bob@Example.com ")
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["owner"]["email"] == "alice@example.com"
    assert [m["user"]["email"] for m in body["members"]] == ["bob@example.com"]
    assert body["members"][0]["added_by"]["email"] == "alice@example.com"

    # Bob now sees and manages it, including in the scoring app.
    assert [lg["name"] for lg in bob.get("/leagues").json()] == ["Alice's"]
    got = bob.get(f"/leagues/{lid}").json()
    assert got["owner"]["name"] == alice.user.name
    assert bob.patch(f"/leagues/{lid}", json={"current_week": 2}).status_code == 200
    match = bob.get(f"/leagues/{lid}/matches?week=1").json()[0]
    assert bob.put(f"/matches/{match['id']}/result", json={"score_a": 11, "score_b": 3}).status_code == 200
    assert [lg["name"] for lg in bob.get("/scoring/leagues").json()] == ["Alice's"]
    assert bob.get(f"/leagues/{lid}/members").status_code == 200


def test_only_the_owner_deletes_or_reshares(alice, bob, carol):
    lid = set_up_league(alice)["id"]
    _share(alice, lid, "bob@example.com")
    assert bob.delete(f"/leagues/{lid}").status_code == 409
    assert _share(bob, lid, "carol@example.com").status_code == 409
    assert bob.delete(f"/leagues/{lid}/members/{alice.user.id}").status_code == 409
    assert carol.get(f"/leagues/{lid}").status_code == 404


def test_member_can_leave_and_owner_can_remove(alice, bob, carol):
    lid = set_up_league(alice)["id"]
    _share(alice, lid, "bob@example.com")
    _share(alice, lid, "carol@example.com")

    assert bob.delete(f"/leagues/{lid}/members/{bob.user.id}").status_code == 204
    assert bob.get(f"/leagues/{lid}").status_code == 404

    assert alice.delete(f"/leagues/{lid}/members/{carol.user.id}").status_code == 204
    assert carol.get(f"/leagues/{lid}").status_code == 404
    assert alice.get(f"/leagues/{lid}/members").json()["members"] == []
    # Removing someone it isn't shared with is a no-op.
    assert alice.delete(f"/leagues/{lid}/members/{carol.user.id}").status_code == 204


def test_who_it_can_be_shared_with(alice, bob, client_for, client):
    lid = set_up_league(alice)["id"]
    client_for(UserRole.UMPIRE, "ump@example.com")
    assert _share(alice, lid, "nobody@example.com").status_code == 404
    assert _share(alice, lid, "ump@example.com").status_code == 422
    assert _share(alice, lid, client.get("/auth/me").json()["email"]).status_code == 422  # an admin
    assert _share(alice, lid, "alice@example.com").status_code == 409  # the owner
    assert _share(alice, lid, "bob@example.com").status_code == 201
    assert _share(alice, lid, "bob@example.com").status_code == 409  # already
    # Deactivated accounts can't be added.
    client.patch(f"/users/{bob.user.id}", json={"is_active": False})
    alice.delete(f"/leagues/{lid}/members/{bob.user.id}")
    assert _share(alice, lid, "bob@example.com").status_code == 404


def test_admins_can_share_any_league(client, alice, bob):
    lid = set_up_league(alice)["id"]
    assert _share(client, lid, "bob@example.com").status_code == 201
    assert bob.get(f"/leagues/{lid}").status_code == 200
    assert client.delete(f"/leagues/{lid}/members/{bob.user.id}").status_code == 204


def test_sharing_goes_with_the_league(alice, bob):
    lid = set_up_league(alice)["id"]
    _share(alice, lid, "bob@example.com")
    assert alice.delete(f"/leagues/{lid}").status_code == 204
    assert bob.get("/leagues").json() == []
