from fastapi import APIRouter

from .. import schemas
from ..deps import DB, get_or_404
from ..models import Team

router = APIRouter(tags=["teams"])

# Teams and players are created and changed only through league setup
# (routers/setup.py); once a league is created they are fixed.


@router.get("/teams/{team_id}", response_model=schemas.TeamRead)
def get_team(team_id: int, db: DB):
    return get_or_404(db, Team, team_id)
