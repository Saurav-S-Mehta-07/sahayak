"""Public scheme-catalog endpoint."""

from fastapi import APIRouter

from ..database import connect

router = APIRouter()


@router.get("/schemes")
def schemes() -> dict[str, list[dict]]:
    with connect() as connection:
        rows = connection.execute(
            """
            SELECT schemes.*,
                (SELECT COUNT(*) FROM scheme_documents
                 WHERE scheme_id = schemes.id) AS document_count,
                (SELECT COUNT(*) FROM scheme_documents
                 WHERE scheme_id = schemes.id AND verification_status = 'verified'
                   AND indexing_status = 'indexed') AS indexed_verified_count
            FROM schemes ORDER BY name
            """
        ).fetchall()
    return {"schemes": [dict(row) for row in rows]}
