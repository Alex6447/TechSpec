import uuid
from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.b2b_account import B2BAccount
from app.services.crypto_service import encrypt


async def create(session: AsyncSession, account_data: dict, master_key: str) -> B2BAccount:
    """Create a B2BAccount, encrypting private_key before saving."""
    account = B2BAccount(
        client_id=account_data["client_id"],
        key_id=account_data["key_id"],
        public_key=account_data["public_key"],
        private_key=encrypt(account_data["private_key"], master_key),
        name=account_data["name"],
        is_assigned=False,
    )
    session.add(account)
    await session.flush()
    return account


async def get_free_account(session: AsyncSession) -> B2BAccount | None:
    """Return the first unassigned B2BAccount, or None."""
    result = await session.execute(
        select(B2BAccount).where(B2BAccount.is_assigned == False).limit(1)  # noqa: E712
    )
    return result.scalar_one_or_none()


async def assign_account(session: AsyncSession, account_id: uuid.UUID) -> None:
    """Mark account as assigned (is_assigned=True)."""
    await session.execute(
        update(B2BAccount)
        .where(B2BAccount.id == account_id)
        .values(is_assigned=True)
    )


async def get_all(
    session: AsyncSession, is_assigned: bool | None = None
) -> list[B2BAccount]:
    """Return all accounts, optionally filtered by is_assigned."""
    query = select(B2BAccount)
    if is_assigned is not None:
        query = query.where(B2BAccount.is_assigned == is_assigned)
    result = await session.execute(query)
    return list(result.scalars().all())


async def update_access_token(
    session: AsyncSession,
    account_id: uuid.UUID,
    token: str,
    expires_at: datetime,
    master_key: str,
) -> None:
    """Save encrypted access_token and its expiry for the given account."""
    await session.execute(
        update(B2BAccount)
        .where(B2BAccount.id == account_id)
        .values(
            access_token=encrypt(token, master_key),
            access_token_expires_at=expires_at,
        )
    )
