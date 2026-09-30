from fastapi import APIRouter

from .. import schemas
from ..deps import DB, get_or_404
from ..models import Player, Team

router = APIRouter(tags=["teams & players"])


@router.get("/teams/{team_id}", response_model=schemas.TeamRead)
def get_team(team_id: int, db: DB):
    return get_or_404(db, Team, team_id)


@router.patch("/teams/{team_id}", response_model=schemas.TeamRead)
def rename_team(team_id: int, payload: schemas.TeamUpdate, db: DB):
    team = get_or_404(db, Team, team_id)
    team.name = payload.name
    db.commit()
    return team


@router.post("/teams/{team_id}/players", response_model=schemas.PlayerRead, status_code=201)
def add_player(team_id: int, payload: schemas.PlayerCreate, db: DB):
    get_or_404(db, Team, team_id)
    player = Player(team_id=team_id, **payload.model_dump())
    db.add(player)
    db.commit()
    return player


@router.patch("/players/{player_id}", response_model=schemas.PlayerRead)
def update_player(player_id: int, payload: schemas.PlayerUpdate, db: DB):
    player = get_or_404(db, Player, player_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(player, field, value)
    db.commit()
    return player


@router.delete("/players/{player_id}", status_code=204)
def delete_player(player_id: int, db: DB):
    db.delete(get_or_404(db, Player, player_id))
    db.commit()
