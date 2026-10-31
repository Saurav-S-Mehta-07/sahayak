from fastapi import APIRouter, HTTPException, Query

from app.api.dependencies import get_runtime

router = APIRouter(prefix="/schemes", tags=["schemes"])


@router.get("")
def list_schemes(q: str | None = Query(default=None, max_length=200)) -> list[dict]:
    return get_runtime().schemes.list_schemes(q)


@router.get("/search")
def search_schemes(q: str = Query(min_length=1, max_length=200)) -> list[dict]:
    return get_runtime().schemes.list_schemes(q)


@router.get("/{scheme_id}")
def get_scheme(scheme_id: str) -> dict:
    scheme = get_runtime().schemes.get_scheme(scheme_id)
    if scheme is None:
        raise HTTPException(status_code=404, detail="Scheme not found in indexed documents")
    return scheme
