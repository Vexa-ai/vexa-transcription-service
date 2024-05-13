from fastapi import HTTPException, Query

from app.settings import settings


async def verify_token(token: str = Query(...)) -> str:
    if token != settings.service_token:
        raise HTTPException(status_code=403, detail="Unauthorized: Invalid service token")
    return token
