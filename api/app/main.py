"""FastAPI application entrypoint."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import CORS_ORIGINS, ROOT_PATH
from .database import init_db
from .routers import leagues, matches, teams


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="Pickleball League API",
    version="0.1.0",
    description="Manage leagues, teams, players, schedules and match results.",
    lifespan=lifespan,
    root_path=ROOT_PATH,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(leagues.router)
app.include_router(teams.router)
app.include_router(matches.router)


@app.get("/health", tags=["meta"])
def health():
    return {"status": "ok"}
