"""Eligibility evaluation against administrator-reviewed documentary criteria."""

from __future__ import annotations

import json
import operator
import re
from typing import Any

from ..database import connect

_COMPARATORS = {
    "eq": operator.eq,
    "ne": operator.ne,
    "gte": operator.ge,
    "lte": operator.le,
}


def _compare(actual: Any, comparator: str, expected: Any) -> bool | None:
    if comparator in {"gte", "lte"}:
        try:
            actual_number = float(actual)
            expected_number = float(expected)
        except (TypeError, ValueError):
            return None
        return bool(_COMPARATORS[comparator](actual_number, expected_number))
    if comparator == "in":
        if not isinstance(expected, list):
            return None
        return str(actual).casefold() in {
            str(value).casefold() for value in expected
        }
    if comparator == "contains":
        if not isinstance(actual, (list, str)):
            return None
        if isinstance(actual, list):
            return str(expected).casefold() in {
                str(value).casefold() for value in actual
            }
        return str(expected).casefold() in actual.casefold()
    if comparator in {"eq", "ne"}:
        return bool(
            _COMPARATORS[comparator](
                str(actual).casefold(), str(expected).casefold()
            )
        )
    return None


def evaluate_scheme(scheme_id: str, answers: dict[str, Any]) -> dict[str, Any]:
    with connect() as connection:
        scheme = connection.execute(
            "SELECT id, name FROM schemes WHERE id = ?", (scheme_id,)
        ).fetchone()
        if scheme is None:
            raise LookupError("Scheme not found.")
        rows = connection.execute(
            """
            SELECT criteria.*, documents.filename, documents.source_url
            FROM scheme_eligibility_criteria AS criteria
            JOIN scheme_documents AS documents
              ON documents.id = criteria.source_document_id
            WHERE criteria.scheme_id = ?
              AND documents.verification_status = 'verified'
              AND documents.indexing_status = 'indexed'
            ORDER BY criteria.id
            """,
            (scheme_id,),
        ).fetchall()
    if not rows:
        return {
            "scheme_id": scheme_id,
            "scheme_name": scheme["name"],
            "status": "more_information_required",
            "message": (
                "No administrator-reviewed eligibility criteria linked to a "
                "verified, indexed document are available for this scheme."
            ),
            "criteria": [],
        }

    criteria_results: list[dict[str, Any]] = []
    for row in rows:
        expected = json.loads(row["expected_value_json"])
        actual = answers.get(row["field_key"])
        if actual is None:
            status = "unknown"
        else:
            matched = _compare(actual, row["operator"], expected)
            status = (
                "unknown" if matched is None else "satisfied" if matched else "not_satisfied"
            )
        criteria_results.append(
            {
                "field": row["field_key"],
                "description": row["description"],
                "status": status,
                "provided_value": actual,
                "expected": expected,
                "operator": row["operator"],
                "source": {
                    "filename": row["filename"],
                    "page": row["source_page"],
                    "excerpt": row["source_excerpt"],
                    "url": row["source_url"],
                },
            }
        )

    statuses = {criterion["status"] for criterion in criteria_results}
    if "not_satisfied" in statuses:
        outcome = "not_eligible_based_on_provided_information"
    elif "unknown" in statuses:
        outcome = "more_information_required"
    else:
        outcome = "potentially_eligible"
    return {
        "scheme_id": scheme_id,
        "scheme_name": scheme["name"],
        "status": outcome,
        "message": (
            "This is a preliminary comparison with recorded criteria only; it "
            "is not an official eligibility decision or guarantee."
        ),
        "criteria": criteria_results,
    }


def recommend_schemes(answers: dict[str, Any]) -> dict[str, Any]:
    """Recommend only schemes with verified documentary criteria and a full match."""
    with connect() as connection:
        rows = connection.execute(
            """
            SELECT DISTINCT schemes.id
            FROM schemes
            JOIN scheme_eligibility_criteria AS criteria
              ON criteria.scheme_id = schemes.id
            JOIN scheme_documents AS documents
              ON documents.id = criteria.source_document_id
            WHERE documents.verification_status = 'verified'
              AND documents.indexing_status = 'indexed'
            ORDER BY schemes.name
            """
        ).fetchall()
    evaluations = [evaluate_scheme(row["id"], answers) for row in rows]
    matches = [
        {
            "scheme_id": result["scheme_id"],
            "scheme_name": result["scheme_name"],
            "criteria": result["criteria"],
            "message": result["message"],
        }
        for result in evaluations
        if result["status"] == "potentially_eligible"
    ]
    return {
        "recommendations": matches,
        "requires_more_information": not evaluations or any(
            result["status"] == "more_information_required" for result in evaluations
        ),
        "evaluated_schemes": len(evaluations),
        "message": (
            "Recommendations are limited to schemes whose recorded, "
            "document-linked criteria match the information provided."
        ),
    }


def validate_criterion_excerpt(excerpt: str) -> str:
    excerpt = " ".join(excerpt.split())
    if len(excerpt) < 12:
        raise ValueError("Provide a source excerpt that supports this criterion.")
    if len(excerpt) > 2000:
        raise ValueError("The source excerpt must be at most 2,000 characters.")
    return excerpt


def normalize_field_key(value: str) -> str:
    key = re.sub(r"[^a-z0-9_]+", "_", value.casefold()).strip("_")
    if not key or len(key) > 64:
        raise ValueError("Field key must contain 1 to 64 letters, numbers, or underscores.")
    return key
