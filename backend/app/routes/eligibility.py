"""Private eligibility evaluation and evidence-based scheme recommendations."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ..auth import require_user_csrf
from ..services.eligibility_service import evaluate_scheme, recommend_schemes

router = APIRouter(prefix="/eligibility")
EligibilityAnswer = str | int | float | bool | list[str]


class EligibilityEvaluationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scheme_id: str = Field(min_length=1, max_length=100)
    answers: dict[str, EligibilityAnswer] = Field(default_factory=dict, max_length=40)

    @field_validator("answers")
    @classmethod
    def validate_answers(
        cls, answers: dict[str, EligibilityAnswer]
    ) -> dict[str, EligibilityAnswer]:
        return _validate_answers(answers)


class SchemeRecommendationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answers: dict[str, EligibilityAnswer] = Field(default_factory=dict, max_length=40)

    @field_validator("answers")
    @classmethod
    def validate_answers(
        cls, answers: dict[str, EligibilityAnswer]
    ) -> dict[str, EligibilityAnswer]:
        return _validate_answers(answers)


def _validate_answers(
    answers: dict[str, EligibilityAnswer],
) -> dict[str, EligibilityAnswer]:
    for key, value in answers.items():
        if not re.fullmatch(r"[a-zA-Z0-9_]{1,64}", key):
            raise ValueError("Answer keys must contain only letters, numbers, and underscores.")
        if isinstance(value, str) and len(value) > 200:
            raise ValueError("Answer text must be at most 200 characters.")
        if isinstance(value, list) and (
            len(value) > 20 or any(len(item) > 100 for item in value)
        ):
            raise ValueError("Answer lists are limited to 20 items of 100 characters.")
    return answers


@router.post("/evaluate")
def evaluate(
    request: EligibilityEvaluationRequest,
    _: dict[str, Any] = Depends(require_user_csrf),
) -> dict[str, Any]:
    try:
        return evaluate_scheme(request.scheme_id, request.answers)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.post("/recommendations")
def recommendations(
    request: SchemeRecommendationRequest,
    _: dict[str, Any] = Depends(require_user_csrf),
) -> dict[str, Any]:
    return recommend_schemes(request.answers)
