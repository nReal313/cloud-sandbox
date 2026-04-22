from __future__ import annotations

from typing import Mapping


class AuthenticationError(PermissionError):
    pass


def parse_bearer_token(headers: Mapping[str, str]) -> str | None:
    authorization = headers.get("Authorization")
    if not authorization:
        return None
    if not authorization.startswith("Bearer "):
        raise AuthenticationError("authorization must use a bearer token")
    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise AuthenticationError("authorization token is missing")
    return token


def require_bearer_auth(headers: Mapping[str, str], expected_token: str | None) -> None:
    if not expected_token:
        return
    token = parse_bearer_token(headers)
    if token is None:
        raise AuthenticationError("authorization is required")
    if token != expected_token:
        raise AuthenticationError("unauthorized")
