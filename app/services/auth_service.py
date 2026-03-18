import json
import uuid
from datetime import datetime, timedelta, timezone

import httpx
from jose import jwt as jose_jwt
from joserfc import jwe
from joserfc.jwe import JWERegistry
from joserfc.jwk import RSAKey

_JWE_REGISTRY = JWERegistry(algorithms=["RSA-OAEP-256", "A256GCM"])
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models.b2b_account import B2BAccount
from app.services.crypto_service import decrypt, encrypt
import app.repositories.b2b_account as b2b_account_repo


def generate_assertion_jwt(client_id: str, key_id: str, private_key: str) -> str:
    """Generate RS256-signed JWT assertion for OAuth2 client_credentials flow."""
    now = datetime.now(tz=timezone.utc)
    payload = {
        "iss": client_id,
        "sub": client_id,
        "aud": settings.arqen_base_url,
        "iat": now,
        "exp": now + timedelta(minutes=5),
    }
    return jose_jwt.encode(
        payload,
        private_key,
        algorithm="RS256",
        headers={"kid": key_id},
    )


async def fetch_access_token(
    client_id: str,
    key_id: str,
    private_key: str,
) -> tuple[str, datetime]:
    """Call POST /api/v1/token and return (access_token, expires_at)."""
    assertion = generate_assertion_jwt(client_id, key_id, private_key)
    async with httpx.AsyncClient(base_url=settings.arqen_base_url) as client:
        response = await client.post(
            "/api/v1/token",
            json={
                "grant_type": "client_credentials",
                "client_assertion_type": (
                    "urn:ietf:params:oauth:client-assertion-type:jwt-bearer"
                ),
                "client_assertion": assertion,
            },
        )
    response.raise_for_status()
    data = response.json()
    token = data["access_token"]
    expires_in = data.get("expires_in", 3600)
    expires_at = datetime.now(tz=timezone.utc) + timedelta(seconds=expires_in)
    return token, expires_at


async def get_valid_access_token(
    b2b_account_id: uuid.UUID,
    session: AsyncSession,
    master_key: str,
) -> str:
    """Return a valid access token for the given B2B account.

    Decrypts from DB if still valid (>5 min remaining); otherwise re-fetches
    from Arqen, stores encrypted, and returns the new token.
    """
    result = await session.execute(
        select(B2BAccount).where(B2BAccount.id == b2b_account_id)
    )
    account = result.scalar_one()

    now = datetime.now(tz=timezone.utc)
    buffer = timedelta(minutes=5)

    if (
        account.access_token
        and account.access_token_expires_at
        and account.access_token_expires_at > now + buffer
    ):
        return decrypt(account.access_token, master_key)

    private_key_pem = decrypt(account.private_key, master_key)
    token, expires_at = await fetch_access_token(
        account.client_id, account.key_id, private_key_pem
    )

    await b2b_account_repo.update_access_token(
        session, account.id, token, expires_at, master_key
    )
    await session.commit()

    return token


def decrypt_jwe(jwe_string: str, private_key_pem: str) -> dict:
    """Decrypt a JWE compact token (RSA-OAEP-256 + A256GCM) and return parsed JSON."""
    key = RSAKey.import_key(private_key_pem)
    token = jwe.decrypt_compact(jwe_string.encode(), key, registry=_JWE_REGISTRY)
    return json.loads(token.plaintext)
