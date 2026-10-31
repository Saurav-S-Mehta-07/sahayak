"""Registration and session endpoints."""

from __future__ import annotations

import re
import secrets
import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field

from ..auth import (
    SESSION_COOKIE,
    create_session,
    get_optional_user,
    require_csrf,
    set_session_cookies,
)
from ..database import connect, user_view
from ..security import hash_password, token_hash, verify_password

router = APIRouter()


class Credentials(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=12, max_length=128)


def _valid_email(email: str) -> bool:
    return re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email) is not None


def _issue_session(user_id: int, user: dict, response: Response) -> dict:
    session_token, csrf_token = create_session(user_id)
    set_session_cookies(response, session_token, csrf_token)
    return {"user": user, "csrf_token": csrf_token}


@router.post("/auth/register", status_code=status.HTTP_201_CREATED)
def register(payload: Credentials, response: Response) -> dict:
    email = payload.email.lower()
    if not _valid_email(email):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Enter a valid email address")
    if len(payload.password) < 12:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Password must be at least 12 characters")
    try:
        with connect() as connection:
            cursor = connection.execute(
                "INSERT INTO users (email, password_hash, role) VALUES (?, ?, 'citizen')",
                (email, hash_password(payload.password)),
            )
            row = connection.execute(
                "SELECT * FROM users WHERE id = ?", (cursor.lastrowid,)
            ).fetchone()
    except sqlite3.IntegrityError as exc:
        if "UNIQUE constraint failed" in str(exc):
            raise HTTPException(status.HTTP_409_CONFLICT, "An account with this email already exists") from exc
        raise
    return _issue_session(row["id"], user_view(row), response)


@router.post("/auth/login")
def login(payload: Credentials, response: Response) -> dict:
    with connect() as connection:
        row = connection.execute(
            "SELECT * FROM users WHERE email = ?", (payload.email.lower(),)
        ).fetchone()
    if row is None or not verify_password(payload.password, row["password_hash"]):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Email or password is incorrect")
    return _issue_session(row["id"], user_view(row), response)


@router.get("/auth/me")
def me(request: Request) -> dict:
    user = get_optional_user(request)
    if user is None:
        return {"user": None, "csrf_token": None}
    session_token = request.cookies.get(SESSION_COOKIE)
    csrf_token = secrets.token_urlsafe(32)
    with connect() as connection:
        connection.execute(
            "UPDATE sessions SET csrf_hash = ? WHERE token_hash = ?",
            (token_hash(csrf_token), token_hash(session_token)),
        )
    return {"user": user, "csrf_token": csrf_token}


@router.post("/auth/logout")
def logout(
    response: Response, request: Request, _: dict = Depends(require_csrf)
) -> dict[str, str]:
    session_token = request.cookies.get(SESSION_COOKIE, "")
    with connect() as connection:
        connection.execute(
            "DELETE FROM sessions WHERE token_hash = ?", (token_hash(session_token),)
        )
    response.delete_cookie(SESSION_COOKIE, path="/")
    response.delete_cookie("yojana_csrf", path="/")
    return {"status": "logged_out"}
