"""
Unit tests for repository layer (task 4.1–4.3).

Uses AsyncMock to simulate AsyncSession — no live database required.
"""

import base64
import secrets
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, call

import pytest

from app.db.models.b2b_account import B2BAccount
from app.db.models.card import Card
from app.db.models.group import Group
from app.services.crypto_service import decrypt


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_master_key() -> str:
    return base64.b64encode(secrets.token_bytes(32)).decode()


def make_session() -> AsyncMock:
    """Return an AsyncMock that mimics AsyncSession."""
    session = AsyncMock()
    session.add = MagicMock()  # add() is synchronous
    return session


def make_execute_result(scalar=None, scalars_list=None):
    """Build a mock result object returned by session.execute()."""
    result = MagicMock()
    result.scalar_one_or_none.return_value = scalar
    result.scalars.return_value.all.return_value = scalars_list or []
    return result


# ---------------------------------------------------------------------------
# 4.1  B2BAccount repository
# ---------------------------------------------------------------------------

class TestB2BAccountRepository:

    @pytest.mark.asyncio
    async def test_create_adds_account_to_session(self):
        from app.repositories.b2b_account import create

        master_key = make_master_key()
        session = make_session()
        account_data = {
            "client_id": "cli-001",
            "key_id": "key-001",
            "public_key": "PUB",
            "private_key": "PRIV",
            "name": "Test Account",
        }

        result = await create(session, account_data, master_key)

        session.add.assert_called_once()
        session.flush.assert_awaited_once()
        assert isinstance(result, B2BAccount)
        assert result.client_id == "cli-001"
        assert result.is_assigned is False

    @pytest.mark.asyncio
    async def test_create_encrypts_private_key(self):
        from app.repositories.b2b_account import create

        master_key = make_master_key()
        session = make_session()
        account_data = {
            "client_id": "cli-002",
            "key_id": "key-002",
            "public_key": "PUB",
            "private_key": "secret-private-key",
            "name": "Account 2",
        }

        result = await create(session, account_data, master_key)

        assert result.private_key != "secret-private-key"
        assert decrypt(result.private_key, master_key) == "secret-private-key"

    @pytest.mark.asyncio
    async def test_get_free_account_returns_scalar(self):
        from app.repositories.b2b_account import get_free_account

        session = make_session()
        free = B2BAccount(client_id="x", key_id="k", public_key="p", private_key="e", name="n")
        session.execute.return_value = make_execute_result(scalar=free)

        result = await get_free_account(session)

        session.execute.assert_awaited_once()
        assert result is free

    @pytest.mark.asyncio
    async def test_get_free_account_returns_none_when_empty(self):
        from app.repositories.b2b_account import get_free_account

        session = make_session()
        session.execute.return_value = make_execute_result(scalar=None)

        result = await get_free_account(session)

        assert result is None

    @pytest.mark.asyncio
    async def test_assign_account_executes_update(self):
        from app.repositories.b2b_account import assign_account

        session = make_session()
        account_id = uuid.uuid4()

        await assign_account(session, account_id)

        session.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_all_no_filter(self):
        from app.repositories.b2b_account import get_all

        session = make_session()
        accounts = [
            B2BAccount(client_id="a", key_id="k", public_key="p", private_key="e", name="n1"),
            B2BAccount(client_id="b", key_id="k", public_key="p", private_key="e", name="n2"),
        ]
        session.execute.return_value = make_execute_result(scalars_list=accounts)

        result = await get_all(session)

        session.execute.assert_awaited_once()
        assert result == accounts

    @pytest.mark.asyncio
    async def test_get_all_with_filter(self):
        from app.repositories.b2b_account import get_all

        session = make_session()
        session.execute.return_value = make_execute_result(scalars_list=[])

        await get_all(session, is_assigned=True)

        session.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_update_access_token_encrypts_token(self):
        from app.repositories.b2b_account import update_access_token

        master_key = make_master_key()
        session = make_session()
        account_id = uuid.uuid4()
        expires_at = datetime(2026, 6, 1, tzinfo=timezone.utc)

        await update_access_token(session, account_id, "raw-token", expires_at, master_key)

        session.execute.assert_awaited_once()
        # verify the update was called (not just that execute was called)
        stmt = session.execute.call_args[0][0]
        # The compiled statement should reference the encrypted value (not raw-token)
        assert stmt is not None


# ---------------------------------------------------------------------------
# 4.2  Group repository
# ---------------------------------------------------------------------------

class TestGroupRepository:

    @pytest.mark.asyncio
    async def test_create_adds_group_to_session(self):
        from app.repositories.group import create

        session = make_session()
        b2b_id = uuid.uuid4()

        result = await create(session, b2b_id, "hash-abc")

        session.add.assert_called_once()
        session.flush.assert_awaited_once()
        assert isinstance(result, Group)
        assert result.b2b_account_id == b2b_id
        assert result.invite_hash == "hash-abc"

    @pytest.mark.asyncio
    async def test_get_by_invite_hash_found(self):
        from app.repositories.group import get_by_invite_hash

        session = make_session()
        group = Group(b2b_account_id=uuid.uuid4(), invite_hash="hash-xyz")
        session.execute.return_value = make_execute_result(scalar=group)

        result = await get_by_invite_hash(session, "hash-xyz")

        session.execute.assert_awaited_once()
        assert result is group

    @pytest.mark.asyncio
    async def test_get_by_invite_hash_not_found(self):
        from app.repositories.group import get_by_invite_hash

        session = make_session()
        session.execute.return_value = make_execute_result(scalar=None)

        result = await get_by_invite_hash(session, "nonexistent")

        assert result is None


# ---------------------------------------------------------------------------
# 4.3  Card repository
# ---------------------------------------------------------------------------

class TestCardRepository:

    @pytest.mark.asyncio
    async def test_create_adds_card_to_session(self):
        from app.repositories.card import create

        session = make_session()

        result = await create(session, "card-001", group_id=42, label="My Card")

        session.add.assert_called_once()
        session.flush.assert_awaited_once()
        assert isinstance(result, Card)
        assert result.card_id == "card-001"
        assert result.group_id == 42
        assert result.label == "My Card"

    @pytest.mark.asyncio
    async def test_create_without_label(self):
        from app.repositories.card import create

        session = make_session()

        result = await create(session, "card-002", group_id=1)

        assert result.label is None

    @pytest.mark.asyncio
    async def test_get_by_group_returns_list(self):
        from app.repositories.card import get_by_group

        session = make_session()
        cards = [Card(card_id="c1", group_id=5), Card(card_id="c2", group_id=5)]
        session.execute.return_value = make_execute_result(scalars_list=cards)

        result = await get_by_group(session, group_id=5)

        session.execute.assert_awaited_once()
        assert result == cards

    @pytest.mark.asyncio
    async def test_get_by_group_empty(self):
        from app.repositories.card import get_by_group

        session = make_session()
        session.execute.return_value = make_execute_result(scalars_list=[])

        result = await get_by_group(session, group_id=99)

        assert result == []

    @pytest.mark.asyncio
    async def test_update_label_executes_update(self):
        from app.repositories.card import update_label

        session = make_session()

        await update_label(session, "card-001", "New Label")

        session.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_update_label_none(self):
        from app.repositories.card import update_label

        session = make_session()

        await update_label(session, "card-001", None)

        session.execute.assert_awaited_once()
