from fastapi import APIRouter, HTTPException, Request, Response

from app.security import create_session, require_api_session


router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.get("/session")
def get_session(request: Request, response: Response) -> dict[str, int | bool]:
    try:
        identity = require_api_session(request)
        return {"authenticated": True, "expires_at": identity.expires_at}
    except HTTPException as error:
        if error.status_code != 401:
            raise
    return create_session(request, response)
