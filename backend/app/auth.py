"""Session authentication and role dependencies."""

from __future__ import annotations

import hmac
import os
import time
from typing import Any

from fastapi import Depends, HTTPException, Request, status

from .database import connect, user_view
from .security import new_token, token_hash

SESSION_COOKIE = "yojana_session"
SESSION_TTL_SECONDS = 60 * 60 * 24 * 7


def create_session(user_id: int) -> tuple[str, str]:
    session_token, csrf_token = new_token(), new_token()
    with connect() as connection:
        connection.execute(
            """
            INSERT INTO sessions (token_hash, user_id, csrf_hash, expires_at)
            VALUES (?, ?, ?, ?)
            """,
            (
                token_hash(session_token),
                user_id,
                token_hash(csrf_token),
                time.time() + SESSION_TTL_SECONDS,
            ),
        )
    return session_token, csrf_token


def set_session_cookies(response: Any, session_token: str, csrf_token: str) -> None:
    secure = os.getenv("SESSION_COOKIE_SECURE", "false").lower() == "true"
    response.set_cookie(
        SESSION_COOKIE,
        session_token,
        httponly=True,
        secure=secure,
        samesite="none" if secure else "lax",
        max_age=SESSION_TTL_SECONDS,
        path="/",
    )
    response.set_cookie(
        "yojana_csrf",
        csrf_token,
        httponly=False,
        secure=secure,
        samesite="none" if secure else "lax",
        max_age=SESSION_TTL_SECONDS,
        path="/",
    )


def get_current_user(request: Request) -> dict[str, Any]:
    session_token = request.cookies.get(SESSION_COOKIE)
    if not session_token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Authentication required")
    with connect() as connection:
        row = connection.execute(
            """
            SELECT users.*, sessions.token_hash
            FROM sessions JOIN users ON users.id = sessions.user_id
            WHERE sessions.token_hash = ? AND sessions.expires_at > ?
            """,
            (token_hash(session_token), time.time()),
        ).fetchone()
        if row is None:
            connection.execute(
                "DELETE FROM sessions WHERE expires_at <= ?", (time.time(),)
            )
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session expired")
    return user_view(row)


def get_optional_user(request: Request) -> dict[str, Any] | None:
    session_token = request.cookies.get(SESSION_COOKIE)
    if not session_token:
        return None
    with connect() as connection:
        row = connection.execute(
            """
            SELECT users.* FROM sessions
            JOIN users ON users.id = sessions.user_id
            WHERE sessions.token_hash = ? AND sessions.expires_at > ?
            """,
            (token_hash(session_token), time.time()),
        ).fetchone()
    return user_view(row) if row is not None else None


def require_csrf(
    request: Request, user: dict[str, Any] = Depends(get_current_user)
) -> dict[str, Any]:
    token = request.headers.get("X-CSRF-Token", "")
    session_token = request.cookies.get(SESSION_COOKIE, "")
    if not token or not session_token:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "CSRF token required")
    with connect() as connection:
        row = connection.execute(
            "SELECT csrf_hash FROM sessions WHERE token_hash = ? AND user_id = ?",
            (token_hash(session_token), user["id"]),
        ).fetchone()
    if row is None or not hmac.compare_digest(row["csrf_hash"], token_hash(token)):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Invalid CSRF token")
    return user


def require_user(user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    return user


def require_user_csrf(
    user: dict[str, Any] = Depends(require_csrf),
) -> dict[str, Any]:
    return user


def require_admin(user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    if user["role"] != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Administrator access required")
    return user


def require_admin_csrf(
    user: dict[str, Any] = Depends(require_csrf),
) -> dict[str, Any]:
    if user["role"] != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Administrator access required")
    return user
