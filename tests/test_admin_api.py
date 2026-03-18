"""
Integration tests for Admin API (task 7).

Uses FastAPI TestClient with dependency overrides — no live database required.
Tests cover:
  - 7.1  verify_admin_token middleware
  - 7.2  POST /api/v1/admin/accounts
  - 7.3  GET /api/v1/admin/accounts
"""
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.db.models.b2b_account import B2BAccount
from app.main import create_app

ADMIN_TOKEN = "test_admin_token"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_account(client_id: str, is_assigned: bool = False) -> B2BAccount:
    account = B2BAccount(
        client_id=client_id,
        key_id="key-001",
        public_key="PUBLIC",
        private_key="ENCRYPTED",
        name=f"Account {client_id}",
        is_assigned=is_assigned,
    )
    account.id = uuid.uuid4()
    account.created_at = datetime(2026, 3, 18, tzinfo=timezone.utc)
    return account


def make_profile(client_id: str = "cli-001") -> dict:
    return {
        "client_id": client_id,
        "key_id": "key-001",
        "public_key": "PUBLIC_KEY",
        "private_key": "PRIVATE_KEY",
        "name": f"Test Account {client_id}",
    }


@pytest.fixture
def client():
    app = create_app()

    session = AsyncMock()
    session.commit = AsyncMock()
    session.flush = AsyncMock()
    session.add = MagicMock()

    async def mock_get_session():
        yield session

    from app.routers.admin import accounts as accounts_module
    app.dependency_overrides[accounts_module.get_session] = mock_get_session

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 7.1  verify_admin_token
# ---------------------------------------------------------------------------

class TestVerifyAdminToken:
    def test_missing_token_returns_403(self, client):
        response = client.post("/api/v1/admin/accounts", json=[])
        assert response.status_code == 403

    def test_wrong_token_returns_403(self, client):
        response = client.post(
            "/api/v1/admin/accounts",
            json=[],
            headers={"X-Admin-Token": "wrong-token"},
        )
        assert response.status_code == 403

    def test_correct_token_on_post_passes_auth(self, client):
        with patch("app.routers.admin.accounts.fetch_access_token") as mock_fetch, \
             patch("app.routers.admin.accounts.b2b_account_repo.create") as mock_create:
            mock_fetch.return_value = ("tok", datetime.now(tz=timezone.utc))
            mock_create.return_value = make_account("cli-001")
            response = client.post(
                "/api/v1/admin/accounts",
                json=[make_profile()],
                headers={"X-Admin-Token": ADMIN_TOKEN},
            )
        assert response.status_code == 200

    def test_correct_token_on_get_passes_auth(self, client):
        with patch("app.routers.admin.accounts.b2b_account_repo.get_all") as mock_get_all:
            mock_get_all.return_value = []
            response = client.get(
                "/api/v1/admin/accounts",
                headers={"X-Admin-Token": ADMIN_TOKEN},
            )
        assert response.status_code == 200

    def test_get_missing_token_returns_403(self, client):
        response = client.get("/api/v1/admin/accounts")
        assert response.status_code == 403


# ---------------------------------------------------------------------------
# 7.2  POST /api/v1/admin/accounts
# ---------------------------------------------------------------------------

class TestPostAccounts:
    def test_add_single_account_success(self, client):
        with patch("app.routers.admin.accounts.fetch_access_token") as mock_fetch, \
             patch("app.routers.admin.accounts.b2b_account_repo.create") as mock_create:
            mock_fetch.return_value = ("token-xyz", datetime.now(tz=timezone.utc))
            mock_create.return_value = make_account("cli-001")

            response = client.post(
                "/api/v1/admin/accounts",
                json=[make_profile("cli-001")],
                headers={"X-Admin-Token": ADMIN_TOKEN},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["added"] == 1
        assert data["errors"] == []

    def test_failed_auth_goes_to_errors(self, client):
        with patch("app.routers.admin.accounts.fetch_access_token") as mock_fetch:
            mock_fetch.side_effect = Exception("Auth failed: invalid key")

            response = client.post(
                "/api/v1/admin/accounts",
                json=[make_profile("cli-bad")],
                headers={"X-Admin-Token": ADMIN_TOKEN},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["added"] == 0
        assert len(data["errors"]) == 1
        assert data["errors"][0]["client_id"] == "cli-bad"
        assert "Auth failed" in data["errors"][0]["reason"]

    def test_mixed_success_and_errors(self, client):
        async def fetch_side_effect(client_id, key_id, private_key):
            if client_id == "bad-client":
                raise Exception("Invalid credentials")
            return ("token-ok", datetime.now(tz=timezone.utc))

        with patch("app.routers.admin.accounts.fetch_access_token") as mock_fetch, \
             patch("app.routers.admin.accounts.b2b_account_repo.create") as mock_create:
            mock_fetch.side_effect = fetch_side_effect
            mock_create.return_value = make_account("good-client")

            response = client.post(
                "/api/v1/admin/accounts",
                json=[make_profile("good-client"), make_profile("bad-client")],
                headers={"X-Admin-Token": ADMIN_TOKEN},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["added"] == 1
        assert len(data["errors"]) == 1
        assert data["errors"][0]["client_id"] == "bad-client"

    def test_empty_list_returns_zero(self, client):
        response = client.post(
            "/api/v1/admin/accounts",
            json=[],
            headers={"X-Admin-Token": ADMIN_TOKEN},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["added"] == 0
        assert data["errors"] == []

    def test_multiple_accounts_all_success(self, client):
        with patch("app.routers.admin.accounts.fetch_access_token") as mock_fetch, \
             patch("app.routers.admin.accounts.b2b_account_repo.create") as mock_create:
            mock_fetch.return_value = ("tok", datetime.now(tz=timezone.utc))
            mock_create.side_effect = [make_account(f"cli-{i}") for i in range(3)]

            response = client.post(
                "/api/v1/admin/accounts",
                json=[make_profile(f"cli-{i}") for i in range(3)],
                headers={"X-Admin-Token": ADMIN_TOKEN},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["added"] == 3
        assert data["errors"] == []

    def test_response_schema_has_required_fields(self, client):
        with patch("app.routers.admin.accounts.fetch_access_token") as mock_fetch, \
             patch("app.routers.admin.accounts.b2b_account_repo.create") as mock_create:
            mock_fetch.return_value = ("tok", datetime.now(tz=timezone.utc))
            mock_create.return_value = make_account("cli-001")

            response = client.post(
                "/api/v1/admin/accounts",
                json=[make_profile()],
                headers={"X-Admin-Token": ADMIN_TOKEN},
            )

        data = response.json()
        assert "added" in data
        assert "errors" in data
        assert isinstance(data["added"], int)
        assert isinstance(data["errors"], list)


# ---------------------------------------------------------------------------
# 7.3  GET /api/v1/admin/accounts
# ---------------------------------------------------------------------------

class TestGetAccounts:
    def test_returns_correct_counts(self, client):
        accounts = [
            make_account("cli-1", is_assigned=True),
            make_account("cli-2", is_assigned=False),
            make_account("cli-3", is_assigned=False),
        ]
        with patch("app.routers.admin.accounts.b2b_account_repo.get_all") as mock_get_all:
            mock_get_all.return_value = accounts

            response = client.get(
                "/api/v1/admin/accounts",
                headers={"X-Admin-Token": ADMIN_TOKEN},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 3
        assert data["used"] == 1
        assert data["free"] == 2
        assert len(data["accounts"]) == 3

    def test_filter_is_assigned_true(self, client):
        accounts = [
            make_account("cli-1", is_assigned=True),
            make_account("cli-2", is_assigned=False),
        ]
        with patch("app.routers.admin.accounts.b2b_account_repo.get_all") as mock_get_all:
            mock_get_all.return_value = accounts

            response = client.get(
                "/api/v1/admin/accounts?is_assigned=true",
                headers={"X-Admin-Token": ADMIN_TOKEN},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert data["used"] == 1
        assert data["free"] == 1
        assert len(data["accounts"]) == 1
        assert data["accounts"][0]["client_id"] == "cli-1"

    def test_filter_is_assigned_false(self, client):
        accounts = [
            make_account("cli-1", is_assigned=True),
            make_account("cli-2", is_assigned=False),
        ]
        with patch("app.routers.admin.accounts.b2b_account_repo.get_all") as mock_get_all:
            mock_get_all.return_value = accounts

            response = client.get(
                "/api/v1/admin/accounts?is_assigned=false",
                headers={"X-Admin-Token": ADMIN_TOKEN},
            )

        assert response.status_code == 200
        data = response.json()
        assert len(data["accounts"]) == 1
        assert data["accounts"][0]["client_id"] == "cli-2"

    def test_no_filter_returns_all(self, client):
        accounts = [
            make_account("cli-1", is_assigned=True),
            make_account("cli-2", is_assigned=False),
        ]
        with patch("app.routers.admin.accounts.b2b_account_repo.get_all") as mock_get_all:
            mock_get_all.return_value = accounts

            response = client.get(
                "/api/v1/admin/accounts",
                headers={"X-Admin-Token": ADMIN_TOKEN},
            )

        data = response.json()
        assert len(data["accounts"]) == 2

    def test_empty_accounts(self, client):
        with patch("app.routers.admin.accounts.b2b_account_repo.get_all") as mock_get_all:
            mock_get_all.return_value = []

            response = client.get(
                "/api/v1/admin/accounts",
                headers={"X-Admin-Token": ADMIN_TOKEN},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["used"] == 0
        assert data["free"] == 0
        assert data["accounts"] == []

    def test_account_fields_in_response(self, client):
        account = make_account("cli-1", is_assigned=True)
        with patch("app.routers.admin.accounts.b2b_account_repo.get_all") as mock_get_all:
            mock_get_all.return_value = [account]

            response = client.get(
                "/api/v1/admin/accounts",
                headers={"X-Admin-Token": ADMIN_TOKEN},
            )

        data = response.json()
        a = data["accounts"][0]
        assert "id" in a
        assert "client_id" in a
        assert "key_id" in a
        assert "name" in a
        assert "is_assigned" in a
        assert "created_at" in a
        assert a["is_assigned"] is True

    def test_response_schema_has_required_fields(self, client):
        with patch("app.routers.admin.accounts.b2b_account_repo.get_all") as mock_get_all:
            mock_get_all.return_value = []

            response = client.get(
                "/api/v1/admin/accounts",
                headers={"X-Admin-Token": ADMIN_TOKEN},
            )

        data = response.json()
        assert "total" in data
        assert "used" in data
        assert "free" in data
        assert "accounts" in data
