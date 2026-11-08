from fastapi import APIRouter, Depends

from .. import schemas
from ..auth import Manager, managed, require_manager
from ..deps import DB
from ..models import Team

router = APIRouter(tags=["teams"], dependencies=[Depends(require_manager)])

# Teams and players are created and changed only through league setup
# (routers/setup.py); once a league is created they are fixed.


@router.get("/teams/{team_id}", response_model=schemas.TeamRead)
def get_team(team_id: int, user: Manager, db: DB):
    return managed(db, user, Team, team_id)
