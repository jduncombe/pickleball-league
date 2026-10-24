"""Terminology table for user-facing API messages (white-labelling).

Same keys and defaults as the web app (web/src/lib/default-terms.json; a test
keeps them in sync). A brand's overrides (web/brands/<brand>/terms.json) are
loaded from the TERMS_FILE path or the TERMS_JSON string, so the API words
messages ("Pair 3 needs at least one player") the way the brand's UI does.
"""

import json
import os
from pathlib import Path

DEFAULT_TERMS: dict[str, dict[str, str]] = {
    "league": {"one": "league", "other": "leagues", "article": "a"},
    "season": {"one": "season", "other": "seasons", "article": "a"},
    "week": {"one": "week", "other": "weeks", "article": "a"},
    "round": {"one": "round", "other": "rounds", "article": "a"},
    "catchUpRound": {"one": "catch-up round", "other": "catch-up rounds", "article": "a"},
    "bye": {"one": "bye", "other": "byes", "article": "a"},
    "team": {"one": "team", "other": "teams", "article": "a"},
    "player": {"one": "player", "other": "players", "article": "a"},
    "match": {"one": "match", "other": "matches", "article": "a"},
    "game": {"one": "game", "other": "games", "article": "a"},
    "court": {"one": "court", "other": "courts", "article": "a"},
    "ratingSystem": {"one": "DUPR", "other": "DUPR", "article": ""},
    "ratingId": {"one": "DUPR ID", "other": "DUPR IDs", "article": "a"},
    "rating": {"one": "rating", "other": "ratings", "article": "a"},
}


def merge_terms(overrides: dict) -> dict[str, dict[str, str]]:
    """Defaults with a brand's overrides applied (same rules as the web app)."""
    merged = {}
    for key, base in DEFAULT_TERMS.items():
        override = overrides.get(key) or {}
        one = override.get("one", base["one"])
        other = override.get("other") or (f"{override['one']}s" if "one" in override else base["other"])
        merged[key] = {"one": one, "other": other, "article": override.get("article", base["article"])}
    return merged


def _load_overrides() -> dict:
    if raw := os.getenv("TERMS_JSON"):
        return json.loads(raw)
    if path := os.getenv("TERMS_FILE"):
        return json.loads(Path(path).read_text())
    return {}


TERMS = merge_terms(_load_overrides())


def term(key: str, n: int = 1) -> str:
    """'team', or 'teams' when n isn't 1."""
    forms = TERMS[key]
    return forms["one"] if n == 1 else forms["other"]


def Term(key: str, n: int = 1) -> str:  # noqa: N802 - mirrors the web helper
    """Capitalised term: 'Team'."""
    word = term(key, n)
    return word[:1].upper() + word[1:]


def count(n: int, key: str) -> str:
    """'3 teams', '1 team'."""
    return f"{n} {term(key, n)}"


def a(key: str) -> str:
    """With its article: 'a league', 'an event'."""
    forms = TERMS[key]
    return f"{forms['article']} {forms['one']}" if forms["article"] else forms["one"]
