from typing import AsyncGenerator, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.base import async_session_factory
from app.utils.security import verify_admin_token
import app.repositories.b2b_account as b2b_account_repo
from app.services.auth_service import fetch_access_token

router = APIRouter()


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class B2BProfileInput(BaseModel):
    client_id: str
    key_id: str
    public_key: str
    private_key: str
    name: str


class AccountError(BaseModel):
    client_id: str
    reason: str


class AddAccountsResponse(BaseModel):
    added: int
    errors: list[AccountError]


class AccountInfo(BaseModel):
    id: str
    client_id: str
    key_id: str
    name: str
    is_assigned: bool
    created_at: str


class ListAccountsResponse(BaseModel):
    total: int
    used: int
    free: int
    accounts: list[AccountInfo]


# ---------------------------------------------------------------------------
# DB session dependency
# ---------------------------------------------------------------------------

async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        yield session


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post(
    "/admin/accounts",
    response_model=AddAccountsResponse,
    dependencies=[Depends(verify_admin_token)],
)
async def add_accounts(
    profiles: list[B2BProfileInput],
    session: AsyncSession = Depends(get_session),
) -> AddAccountsResponse:
    added = 0
    errors: list[AccountError] = []

    for profile in profiles:
        try:
            await fetch_access_token(profile.client_id, profile.key_id, profile.private_key)
            await b2b_account_repo.create(
                session,
                {
                    "client_id": profile.client_id,
                    "key_id": profile.key_id,
                    "public_key": profile.public_key,
                    "private_key": profile.private_key,
                    "name": profile.name,
                },
                settings.master_key,
            )
            added += 1
        except Exception as e:
            errors.append(AccountError(client_id=profile.client_id, reason=str(e)))

    if added > 0:
        await session.commit()

    return AddAccountsResponse(added=added, errors=errors)


@router.get(
    "/admin/accounts",
    response_model=ListAccountsResponse,
    dependencies=[Depends(verify_admin_token)],
)
async def list_accounts(
    is_assigned: Optional[bool] = Query(None),
    session: AsyncSession = Depends(get_session),
) -> ListAccountsResponse:
    all_accounts = await b2b_account_repo.get_all(session)
    used = sum(1 for a in all_accounts if a.is_assigned)
    free = sum(1 for a in all_accounts if not a.is_assigned)

    filtered = (
        [a for a in all_accounts if a.is_assigned == is_assigned]
        if is_assigned is not None
        else all_accounts
    )

    accounts = [
        AccountInfo(
            id=str(a.id),
            client_id=a.client_id,
            key_id=a.key_id,
            name=a.name,
            is_assigned=a.is_assigned,
            created_at=a.created_at.isoformat() if a.created_at else "",
        )
        for a in filtered
    ]

    return ListAccountsResponse(
        total=len(all_accounts),
        used=used,
        free=free,
        accounts=accounts,
    )
