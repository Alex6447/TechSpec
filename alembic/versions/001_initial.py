"""Initial schema

Revision ID: 001
Revises:
Create Date: 2026-03-18 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # B2B_Accounts
    op.create_table(
        "b2b_accounts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("client_id", sa.String(), nullable=False),
        sa.Column("key_id", sa.String(), nullable=False),
        sa.Column("public_key", sa.Text(), nullable=False),
        sa.Column("private_key", sa.Text(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("is_assigned", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("access_token", sa.Text(), nullable=True),
        sa.Column("access_token_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("client_id"),
    )
    op.create_index("ix_b2b_accounts_is_assigned", "b2b_accounts", ["is_assigned"])

    # Groups
    op.create_table(
        "groups",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("b2b_account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("invite_hash", sa.String(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["b2b_account_id"], ["b2b_accounts.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("invite_hash"),
    )

    # Users
    op.create_table(
        "users",
        sa.Column("telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("group_id", sa.Integer(), nullable=False),
        sa.Column("terms_accepted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["group_id"], ["groups.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("telegram_id"),
    )
    op.create_index("ix_users_group_id", "users", ["group_id"])

    # Cards
    op.create_table(
        "cards",
        sa.Column("card_id", sa.String(), nullable=False),
        sa.Column("group_id", sa.Integer(), nullable=False),
        sa.Column("label", sa.String(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["group_id"], ["groups.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("card_id"),
    )
    op.create_index("ix_cards_group_id", "cards", ["group_id"])

    # Codes_3ds
    op.create_table(
        "codes_3ds",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("card_id", sa.String(), nullable=False),
        sa.Column("group_id", sa.Integer(), nullable=False),
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("merchant_name", sa.String(), nullable=True),
        sa.Column("amount", sa.Numeric(), nullable=True),
        sa.Column("currency", sa.String(3), nullable=True),
        sa.Column("purchase_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "received_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["card_id"], ["cards.card_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["group_id"], ["groups.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_codes_3ds_card_id_expires_at", "codes_3ds", ["card_id", "expires_at"])


def downgrade() -> None:
    op.drop_index("ix_codes_3ds_card_id_expires_at", table_name="codes_3ds")
    op.drop_table("codes_3ds")
    op.drop_index("ix_cards_group_id", table_name="cards")
    op.drop_table("cards")
    op.drop_index("ix_users_group_id", table_name="users")
    op.drop_table("users")
    op.drop_table("groups")
    op.drop_index("ix_b2b_accounts_is_assigned", table_name="b2b_accounts")
    op.drop_table("b2b_accounts")
