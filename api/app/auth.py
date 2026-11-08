"""Temporary bearer-token check for the scoring-app endpoints.

One shared token (``SCORING_API_TOKEN``) until proper authentication lands.
Failures are 401, never 403: CloudFront turns any 403 into the site's 404
page (see infra/app/web.tf).
"""

import secrets
from typing import Annotated

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from . import config

# auto_error=False so a missing header is our 401, not FastAPI's default error.
_bearer = HTTPBearer(auto_error=False, description="The scoring-app token (SCORING_API_TOKEN)")


def require_scoring_token(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> None:
    if credentials is None or not secrets.compare_digest(
        credentials.credentials.encode(), config.SCORING_API_TOKEN.encode()
    ):
        raise HTTPException(
            401, "Missing or invalid scoring token", headers={"WWW-Authenticate": "Bearer"}
        )
