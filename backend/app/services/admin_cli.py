"""Create the first administrator without exposing a public role-escalation API."""

from __future__ import annotations

import getpass
import re

from ..database import connect
from ..security import hash_password


def main() -> None:
    email = input("Administrator email: ").strip().lower()
    if re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email) is None:
        raise SystemExit("A valid email address is required.")
    password = getpass.getpass("Password (minimum 12 characters): ")
    if len(password) < 12:
        raise SystemExit("Password must contain at least 12 characters.")
    with connect() as connection:
        existing = connection.execute(
            "SELECT id, role FROM users WHERE email = ?", (email,)
        ).fetchone()
        if existing and existing["role"] == "admin":
            raise SystemExit("That email already has administrator access.")
        if existing:
            connection.execute(
                "UPDATE users SET role = 'admin', password_hash = ? WHERE id = ?",
                (hash_password(password), existing["id"]),
            )
        else:
            connection.execute(
                "INSERT INTO users (email, password_hash, role) VALUES (?, ?, 'admin')",
                (email, hash_password(password)),
            )
    print("Administrator account created.")


if __name__ == "__main__":
    main()
