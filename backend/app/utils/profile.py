from __future__ import annotations

import re
from typing import Any


def update_user_profile(profile: dict[str, Any], message: str) -> dict[str, Any]:
    age = re.search(
        r"\b(?:age|umr|umar)\s*(?:is|hai|:)?\s*(\d{1,3})\b"
        r"|\b(?:i am|i'm)\s+(\d{1,3})\s*(?:years?\s*old|saal)\b",
        message,
        re.IGNORECASE,
    )
    if age:
        profile["age"] = int(age.group(1) or age.group(2))

    income = re.search(
        r"\b(?:annual income|income|aay|varshik aay)\s*(?:is|hai|:)?\s*"
        r"(?:₹|rs\.?\s*)?([\d,]+)",
        message,
        re.IGNORECASE,
    )
    if income:
        profile["annual_income"] = int(income.group(1).replace(",", ""))

    occupation = re.search(
        r"\b(?:i am|i'm|occupation is)\b.{0,60}?"
        r"\b(farmer|student|teacher|laborer|artisan|fisher|fisherman|"
        r"self[- ]employed|unemployed|homemaker)\b",
        message,
        re.IGNORECASE,
    )
    has_negative_occupation = re.search(
        r"\bnot\s+(?:a\s+|an\s+)?(?:farmer|student|teacher|laborer|artisan|"
        r"fisher|fisherman|self[- ]employed|unemployed|homemaker)\b",
        message,
        re.IGNORECASE,
    )
    if occupation and not has_negative_occupation:
        profile["occupation"] = occupation.group(1).strip().lower()
        if occupation.group(1).lower() in {"farmer", "fisher", "fisherman"}:
            profile["farmer"] = True
        if occupation.group(1).lower() == "student":
            profile["student_status"] = True

    if re.search(r"\b(?:not a student|not student)\b", message, re.IGNORECASE):
        profile["student_status"] = False

    for field in ("state", "district"):
        match = re.search(
            rf"\b{field}\s*(?:is|hai|:)\s*"
            r"([A-Za-z][A-Za-z .-]{1,50}?)(?=,|\.|;|\band\b|$)",
            message,
            re.IGNORECASE,
        )
        if match:
            profile[field] = match.group(1).strip()
    return profile
