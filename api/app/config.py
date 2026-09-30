"""Runtime configuration, read from environment variables."""

import os

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./data/pickleball.db")

# Comma-separated list of origins allowed to call the API from a browser.
CORS_ORIGINS = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
    if origin.strip()
]
