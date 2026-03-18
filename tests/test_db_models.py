"""
Tests for DB models (task 2.2) and migration file (task 2.4).

These tests verify model structure using SQLAlchemy metadata inspection —
no live database connection required.
"""

import pytest
from sqlalchemy import inspect as sa_inspect


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _column_names(model_class) -> set[str]:
    return {c.key for c in sa_inspect(model_class).mapper.column_attrs}


def _table_column_names(model_class) -> set[str]:
    return {c.name for c in model_class.__table__.columns}


# ---------------------------------------------------------------------------
# 2.1  base.py — engine and session factory exist
# ---------------------------------------------------------------------------

def test_db_base_exports():
    from app.db.base import Base, engine, async_session_factory
    assert Base is not None
    assert engine is not None
    assert async_session_factory is not None


# ---------------------------------------------------------------------------
# 2.2  Models — import and structural checks
# ---------------------------------------------------------------------------

class TestB2BAccountModel:
    def test_import(self):
        from app.db.models.b2b_account import B2BAccount
        assert B2BAccount.__tablename__ == "b2b_accounts"

    def test_columns(self):
        from app.db.models.b2b_account import B2BAccount
        expected = {
            "id", "client_id", "key_id", "public_key", "private_key",
            "name", "is_assigned", "access_token", "access_token_expires_at",
            "created_at",
        }
        assert expected == _table_column_names(B2BAccount)

    def test_primary_key(self):
        from app.db.models.b2b_account import B2BAccount
        pk_cols = {c.name for c in B2BAccount.__table__.primary_key}
        assert pk_cols == {"id"}

    def test_unique_client_id(self):
        from app.db.models.b2b_account import B2BAccount
        from sqlalchemy import UniqueConstraint
        unique_cols = {
            col.name
            for constraint in B2BAccount.__table__.constraints
            if isinstance(constraint, UniqueConstraint)
            for col in constraint.columns
        }
        assert "client_id" in unique_cols

    def test_index_is_assigned(self):
        from app.db.models.b2b_account import B2BAccount
        index_names = {idx.name for idx in B2BAccount.__table__.indexes}
        assert "ix_b2b_accounts_is_assigned" in index_names


class TestGroupModel:
    def test_import(self):
        from app.db.models.group import Group
        assert Group.__tablename__ == "groups"

    def test_columns(self):
        from app.db.models.group import Group
        expected = {"id", "b2b_account_id", "invite_hash", "created_at"}
        assert expected == _table_column_names(Group)

    def test_primary_key(self):
        from app.db.models.group import Group
        pk_cols = {c.name for c in Group.__table__.primary_key}
        assert pk_cols == {"id"}

    def test_fk_to_b2b_accounts(self):
        from app.db.models.group import Group
        fk_targets = {fk.target_fullname for fk in Group.__table__.foreign_keys}
        assert "b2b_accounts.id" in fk_targets


class TestUserModel:
    def test_import(self):
        from app.db.models.user import User
        assert User.__tablename__ == "users"

    def test_columns(self):
        from app.db.models.user import User
        expected = {"telegram_id", "group_id", "terms_accepted", "created_at"}
        assert expected == _table_column_names(User)

    def test_primary_key(self):
        from app.db.models.user import User
        pk_cols = {c.name for c in User.__table__.primary_key}
        assert pk_cols == {"telegram_id"}

    def test_index_group_id(self):
        from app.db.models.user import User
        index_names = {idx.name for idx in User.__table__.indexes}
        assert "ix_users_group_id" in index_names


class TestCardModel:
    def test_import(self):
        from app.db.models.card import Card
        assert Card.__tablename__ == "cards"

    def test_columns(self):
        from app.db.models.card import Card
        expected = {"card_id", "group_id", "label", "created_at"}
        assert expected == _table_column_names(Card)

    def test_primary_key(self):
        from app.db.models.card import Card
        pk_cols = {c.name for c in Card.__table__.primary_key}
        assert pk_cols == {"card_id"}

    def test_index_group_id(self):
        from app.db.models.card import Card
        index_names = {idx.name for idx in Card.__table__.indexes}
        assert "ix_cards_group_id" in index_names


class TestCode3dsModel:
    def test_import(self):
        from app.db.models.code_3ds import Code3ds
        assert Code3ds.__tablename__ == "codes_3ds"

    def test_columns(self):
        from app.db.models.code_3ds import Code3ds
        expected = {
            "id", "card_id", "group_id", "code", "merchant_name",
            "amount", "currency", "purchase_date", "received_at", "expires_at",
        }
        assert expected == _table_column_names(Code3ds)

    def test_primary_key(self):
        from app.db.models.code_3ds import Code3ds
        pk_cols = {c.name for c in Code3ds.__table__.primary_key}
        assert pk_cols == {"id"}

    def test_index_card_id_expires_at(self):
        from app.db.models.code_3ds import Code3ds
        index_names = {idx.name for idx in Code3ds.__table__.indexes}
        assert "ix_codes_3ds_card_id_expires_at" in index_names

    def test_fk_to_cards(self):
        from app.db.models.code_3ds import Code3ds
        fk_targets = {fk.target_fullname for fk in Code3ds.__table__.foreign_keys}
        assert "cards.card_id" in fk_targets

    def test_fk_to_groups(self):
        from app.db.models.code_3ds import Code3ds
        fk_targets = {fk.target_fullname for fk in Code3ds.__table__.foreign_keys}
        assert "groups.id" in fk_targets


# ---------------------------------------------------------------------------
# models/__init__.py — all models registered in Base.metadata
# ---------------------------------------------------------------------------

def test_all_models_in_metadata():
    import app.db.models  # noqa: F401 — triggers all imports
    from app.db.base import Base

    expected_tables = {"b2b_accounts", "groups", "users", "cards", "codes_3ds"}
    assert expected_tables == set(Base.metadata.tables.keys())


# ---------------------------------------------------------------------------
# 2.4  Migration file — exists and has correct revision
# ---------------------------------------------------------------------------

def _load_migration():
    import importlib.util
    import pathlib
    migration_path = pathlib.Path(__file__).parent.parent / "alembic" / "versions" / "001_initial.py"
    spec = importlib.util.spec_from_file_location("migration_001", migration_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_migration_file_exists():
    module = _load_migration()
    assert module.revision == "001"
    assert module.down_revision is None


def test_migration_has_upgrade_downgrade():
    module = _load_migration()
    assert callable(module.upgrade)
    assert callable(module.downgrade)


# ---------------------------------------------------------------------------
# 2.5  Migration SQL generation — verify DDL is valid (offline mode, no DB)
# ---------------------------------------------------------------------------

def _make_pg_offline_context(buf):
    """Create an Alembic MigrationContext in offline (SQL generation) mode using PG dialect."""
    from alembic.runtime.migration import MigrationContext
    from sqlalchemy.dialects.postgresql.base import PGDialect

    return MigrationContext.configure(
        dialect=PGDialect(),
        opts={
            "as_sql": True,
            "literal_binds": True,
            "output_buffer": buf,
        },
    )


def test_migration_generates_all_tables():
    """
    Verify upgrade() generates CREATE TABLE for all expected tables.
    Uses Alembic offline mode — no DB connection required.
    """
    from io import StringIO
    from alembic.operations import Operations

    buf = StringIO()
    ctx = _make_pg_offline_context(buf)
    op = Operations(ctx)

    module = _load_migration()
    with ctx.begin_transaction():
        module.upgrade.__globals__["op"] = op
        module.upgrade()

    sql = buf.getvalue()
    for table in ("b2b_accounts", "groups", "users", "cards", "codes_3ds"):
        assert table in sql, f"Table {table!r} not found in generated DDL"


def test_migration_downgrade_drops_all_tables():
    """
    Verify downgrade() generates DROP TABLE statements.
    Uses Alembic offline mode — no DB connection required.
    """
    from io import StringIO
    from alembic.operations import Operations

    buf = StringIO()
    ctx = _make_pg_offline_context(buf)
    op = Operations(ctx)

    module = _load_migration()
    with ctx.begin_transaction():
        module.downgrade.__globals__["op"] = op
        module.downgrade()

    sql = buf.getvalue()
    assert "DROP TABLE" in sql.upper()
