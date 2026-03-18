import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.group import Group


async def create(
    session: AsyncSession, b2b_account_id: uuid.UUID, invite_hash: str
) -> Group:
    """Create a new Group linked to a B2BAccount."""
    group = Group(b2b_account_id=b2b_account_id, invite_hash=invite_hash)
    session.add(group)
    await session.flush()
    return group


async def get_by_invite_hash(session: AsyncSession, invite_hash: str) -> Group | None:
    """Find a Group by its invite hash, or return None."""
    result = await session.execute(
        select(Group).where(Group.invite_hash == invite_hash)
    )
    return result.scalar_one_or_none()
