from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.card import Card


async def create(
    session: AsyncSession, card_id: str, group_id: int, label: str | None = None
) -> Card:
    """Create a new Card entry."""
    card = Card(card_id=card_id, group_id=group_id, label=label)
    session.add(card)
    await session.flush()
    return card


async def get_by_group(session: AsyncSession, group_id: int) -> list[Card]:
    """Return all cards belonging to the given group."""
    result = await session.execute(
        select(Card).where(Card.group_id == group_id)
    )
    return list(result.scalars().all())


async def update_label(session: AsyncSession, card_id: str, label: str | None) -> None:
    """Update the label of a card."""
    await session.execute(
        update(Card).where(Card.card_id == card_id).values(label=label)
    )
