from fastapi import APIRouter, HTTPException

from app.api.dependencies import get_runtime
from app.models.schemas import EligibilityRequest, EligibilityResult

router = APIRouter(prefix="/eligibility", tags=["eligibility"])


@router.post("/evaluate", response_model=EligibilityResult)
def evaluate_eligibility(request: EligibilityRequest) -> EligibilityResult:
    scheme = get_runtime().schemes.get_scheme(request.scheme_id)
    if scheme is None:
        raise HTTPException(status_code=404, detail="Scheme not found in indexed documents")
    return get_runtime().eligibility.evaluate(
        request.scheme_id,
        request.profile,
        scheme_name=scheme["scheme_name"],
    )
