from fastapi import Header, HTTPException

from app.config import settings


async def verify_admin_token(x_admin_token: str | None = Header(None)) -> None:
    if not x_admin_token or x_admin_token != settings.admin_token:
        raise HTTPException(status_code=403, detail="Forbidden")
