"""
Tests for auth_service.py (task 6.1–6.3).

- generate_assertion_jwt  — unit (no network, no DB)
- fetch_access_token      — unit (mocked httpx)
- get_valid_access_token  — unit (mocked DB session + fetch_access_token)
- decrypt_jwe             — unit (real crypto, no network)
"""

import json
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from joserfc import jwe as josejwe
from joserfc.jwe import JWERegistry
from joserfc.jwk import RSAKey
from jose import jwt as jose_jwt

_TEST_JWE_REGISTRY = JWERegistry(algorithms=["RSA-OAEP-256", "A256GCM"])

from app.services.auth_service import (
    decrypt_jwe,
    fetch_access_token,
    generate_assertion_jwt,
    get_valid_access_token,
)
from app.services.crypto_service import encrypt


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_rsa_keypair() -> tuple[str, str]:
    """Generate RSA-2048 keypair; return (private_pem, public_pem) as strings."""
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()
    return private_pem, public_pem


# ---------------------------------------------------------------------------
# generate_assertion_jwt
# ---------------------------------------------------------------------------

class TestGenerateAssertionJwt:
    def setup_method(self):
        self.private_pem, self.public_pem = make_rsa_keypair()
        self.client_id = "test-client-id"
        self.key_id = "test-key-id"

    def test_returns_string(self):
        token = generate_assertion_jwt(self.client_id, self.key_id, self.private_pem)
        assert isinstance(token, str)
        assert len(token) > 0

    def test_jwt_has_three_parts(self):
        token = generate_assertion_jwt(self.client_id, self.key_id, self.private_pem)
        assert token.count(".") == 2

    def test_claims_correct(self):
        token = generate_assertion_jwt(self.client_id, self.key_id, self.private_pem)
        claims = jose_jwt.decode(
            token, self.public_pem, algorithms=["RS256"],
            options={"verify_aud": False},
        )
        assert claims["iss"] == self.client_id
        assert claims["sub"] == self.client_id
        assert "aud" in claims
        assert "exp" in claims
        assert "iat" in claims

    def test_kid_in_header(self):
        import base64
        token = generate_assertion_jwt(self.client_id, self.key_id, self.private_pem)
        header_b64 = token.split(".")[0]
        # Fix padding
        padding = 4 - len(header_b64) % 4
        if padding != 4:
            header_b64 += "=" * padding
        header = json.loads(base64.urlsafe_b64decode(header_b64))
        assert header["kid"] == self.key_id
        assert header["alg"] == "RS256"

    def test_exp_in_future(self):
        token = generate_assertion_jwt(self.client_id, self.key_id, self.private_pem)
        claims = jose_jwt.decode(
            token, self.public_pem, algorithms=["RS256"],
            options={"verify_aud": False},
        )
        now = datetime.now(tz=timezone.utc).timestamp()
        assert claims["exp"] > now

    def test_exp_within_5_minutes(self):
        token = generate_assertion_jwt(self.client_id, self.key_id, self.private_pem)
        claims = jose_jwt.decode(
            token, self.public_pem, algorithms=["RS256"],
            options={"verify_aud": False},
        )
        now = datetime.now(tz=timezone.utc).timestamp()
        assert claims["exp"] <= now + 5 * 60 + 2  # +2s tolerance

    def test_signature_invalid_with_wrong_key(self):
        from jose.exceptions import JWTError
        _, other_public_pem = make_rsa_keypair()
        token = generate_assertion_jwt(self.client_id, self.key_id, self.private_pem)
        with pytest.raises(JWTError):
            jose_jwt.decode(token, other_public_pem, algorithms=["RS256"])


# ---------------------------------------------------------------------------
# fetch_access_token
# ---------------------------------------------------------------------------

class TestFetchAccessToken:
    def setup_method(self):
        self.private_pem, _ = make_rsa_keypair()
        self.client_id = "client-123"
        self.key_id = "key-abc"

    @pytest.mark.asyncio
    async def test_success_returns_token_and_expires_at(self):
        response_data = {"access_token": "arqen-token-xyz", "expires_in": 3600}
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json = MagicMock(return_value=response_data)

        with patch("app.services.auth_service.httpx.AsyncClient") as mock_cls:
            mock_instance = AsyncMock()
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            mock_instance.post = AsyncMock(return_value=mock_response)
            mock_cls.return_value = mock_instance

            token, expires_at = await fetch_access_token(
                self.client_id, self.key_id, self.private_pem
            )

        assert token == "arqen-token-xyz"
        assert isinstance(expires_at, datetime)
        assert expires_at.tzinfo is not None

    @pytest.mark.asyncio
    async def test_expires_at_is_approximately_one_hour(self):
        response_data = {"access_token": "tok", "expires_in": 3600}
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json = MagicMock(return_value=response_data)

        with patch("app.services.auth_service.httpx.AsyncClient") as mock_cls:
            mock_instance = AsyncMock()
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            mock_instance.post = AsyncMock(return_value=mock_response)
            mock_cls.return_value = mock_instance

            _, expires_at = await fetch_access_token(
                self.client_id, self.key_id, self.private_pem
            )

        now = datetime.now(tz=timezone.utc)
        diff = (expires_at - now).total_seconds()
        assert 3595 < diff < 3605

    @pytest.mark.asyncio
    async def test_uses_default_expires_in_when_missing(self):
        response_data = {"access_token": "tok"}  # no expires_in
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json = MagicMock(return_value=response_data)

        with patch("app.services.auth_service.httpx.AsyncClient") as mock_cls:
            mock_instance = AsyncMock()
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            mock_instance.post = AsyncMock(return_value=mock_response)
            mock_cls.return_value = mock_instance

            _, expires_at = await fetch_access_token(
                self.client_id, self.key_id, self.private_pem
            )

        now = datetime.now(tz=timezone.utc)
        diff = (expires_at - now).total_seconds()
        assert diff > 3500

    @pytest.mark.asyncio
    async def test_correct_endpoint_and_payload(self):
        response_data = {"access_token": "tok", "expires_in": 3600}
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json = MagicMock(return_value=response_data)

        with patch("app.services.auth_service.httpx.AsyncClient") as mock_cls:
            mock_instance = AsyncMock()
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            mock_instance.post = AsyncMock(return_value=mock_response)
            mock_cls.return_value = mock_instance

            await fetch_access_token(self.client_id, self.key_id, self.private_pem)

        call_kwargs = mock_instance.post.call_args
        assert call_kwargs[0][0] == "/api/v1/token"
        body = call_kwargs[1]["json"]
        assert body["grant_type"] == "client_credentials"
        assert body["client_assertion_type"] == (
            "urn:ietf:params:oauth:client-assertion-type:jwt-bearer"
        )
        assert "client_assertion" in body

    @pytest.mark.asyncio
    async def test_http_error_propagates(self):
        import httpx as httpx_lib

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock(
            side_effect=httpx_lib.HTTPStatusError(
                "401", request=MagicMock(), response=MagicMock()
            )
        )

        with patch("app.services.auth_service.httpx.AsyncClient") as mock_cls:
            mock_instance = AsyncMock()
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            mock_instance.post = AsyncMock(return_value=mock_response)
            mock_cls.return_value = mock_instance

            with pytest.raises(httpx_lib.HTTPStatusError):
                await fetch_access_token(self.client_id, self.key_id, self.private_pem)


# ---------------------------------------------------------------------------
# get_valid_access_token
# ---------------------------------------------------------------------------

import base64
import secrets


def make_master_key() -> str:
    return base64.b64encode(secrets.token_bytes(32)).decode()


def make_account(
    *,
    access_token_str: str | None = None,
    expires_at: datetime | None = None,
    master_key: str,
    private_pem: str,
) -> MagicMock:
    account = MagicMock()
    account.id = uuid.uuid4()
    account.client_id = "client-abc"
    account.key_id = "key-abc"
    account.private_key = encrypt(private_pem, master_key)
    if access_token_str:
        account.access_token = encrypt(access_token_str, master_key)
    else:
        account.access_token = None
    account.access_token_expires_at = expires_at
    return account


class TestGetValidAccessToken:
    def setup_method(self):
        self.private_pem, _ = make_rsa_keypair()
        self.master_key = make_master_key()

    def _make_session(self, account: MagicMock) -> AsyncMock:
        session = AsyncMock()
        result = MagicMock()
        result.scalar_one.return_value = account
        session.execute = AsyncMock(return_value=result)
        session.commit = AsyncMock()
        return session

    @pytest.mark.asyncio
    async def test_returns_cached_token_when_still_valid(self):
        future = datetime.now(tz=timezone.utc) + timedelta(hours=1)
        account = make_account(
            access_token_str="cached-token",
            expires_at=future,
            master_key=self.master_key,
            private_pem=self.private_pem,
        )
        session = self._make_session(account)

        with patch("app.services.auth_service.fetch_access_token") as mock_fetch:
            token = await get_valid_access_token(
                account.id, session, self.master_key
            )

        assert token == "cached-token"
        mock_fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_refreshes_when_token_missing(self):
        account = make_account(
            access_token_str=None,
            expires_at=None,
            master_key=self.master_key,
            private_pem=self.private_pem,
        )
        session = self._make_session(account)
        new_expires = datetime.now(tz=timezone.utc) + timedelta(hours=1)

        with patch("app.services.auth_service.fetch_access_token") as mock_fetch:
            mock_fetch.return_value = ("new-token", new_expires)
            with patch("app.services.auth_service.b2b_account_repo.update_access_token") as mock_update:
                mock_update.return_value = None
                token = await get_valid_access_token(
                    account.id, session, self.master_key
                )

        assert token == "new-token"
        mock_fetch.assert_awaited_once()
        session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_refreshes_when_token_almost_expired(self):
        # Expires in 3 minutes — within the 5-minute buffer
        almost_expired = datetime.now(tz=timezone.utc) + timedelta(minutes=3)
        account = make_account(
            access_token_str="expiring-soon",
            expires_at=almost_expired,
            master_key=self.master_key,
            private_pem=self.private_pem,
        )
        session = self._make_session(account)
        new_expires = datetime.now(tz=timezone.utc) + timedelta(hours=1)

        with patch("app.services.auth_service.fetch_access_token") as mock_fetch:
            mock_fetch.return_value = ("refreshed-token", new_expires)
            with patch("app.services.auth_service.b2b_account_repo.update_access_token") as mock_update:
                mock_update.return_value = None
                token = await get_valid_access_token(
                    account.id, session, self.master_key
                )

        assert token == "refreshed-token"
        mock_fetch.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_does_not_refresh_token_with_plenty_of_time(self):
        far_future = datetime.now(tz=timezone.utc) + timedelta(hours=2)
        account = make_account(
            access_token_str="valid-long-token",
            expires_at=far_future,
            master_key=self.master_key,
            private_pem=self.private_pem,
        )
        session = self._make_session(account)

        with patch("app.services.auth_service.fetch_access_token") as mock_fetch:
            token = await get_valid_access_token(
                account.id, session, self.master_key
            )

        assert token == "valid-long-token"
        mock_fetch.assert_not_called()
        session.commit.assert_not_called()


# ---------------------------------------------------------------------------
# decrypt_jwe
# ---------------------------------------------------------------------------

class TestDecryptJwe:
    def setup_method(self):
        self.private_pem, self.public_pem = make_rsa_keypair()

    def _encrypt_jwe(self, payload: dict) -> str:
        key = RSAKey.import_key(self.public_pem)
        protected = {"alg": "RSA-OAEP-256", "enc": "A256GCM"}
        token = josejwe.encrypt_compact(
            protected, json.dumps(payload).encode(), key,
            registry=_TEST_JWE_REGISTRY,
        )
        return token.decode() if isinstance(token, bytes) else token

    def test_decrypt_returns_dict(self):
        payload = {"pan": "4111111111111111", "cvv": "123"}
        jwe_string = self._encrypt_jwe(payload)
        result = decrypt_jwe(jwe_string, self.private_pem)
        assert result == payload

    def test_decrypt_nested_payload(self):
        payload = {"card": {"number": "5500000000000004", "exp": "12/27"}, "currency": "USD"}
        jwe_string = self._encrypt_jwe(payload)
        result = decrypt_jwe(jwe_string, self.private_pem)
        assert result == payload

    def test_wrong_key_raises(self):
        payload = {"secret": "data"}
        jwe_string = self._encrypt_jwe(payload)
        other_private_pem, _ = make_rsa_keypair()
        with pytest.raises(Exception):
            decrypt_jwe(jwe_string, other_private_pem)

    def test_malformed_jwe_raises(self):
        with pytest.raises(Exception):
            decrypt_jwe("not.a.valid.jwe.token", self.private_pem)
