import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.services.arqen_client import (
    ArqenAPIError,
    ArqenAuthError,
    ArqenClient,
    ArqenNotFoundError,
)

BASE_URL = "https://sandbox.arqen.finance"
TOKEN = "test-access-token"


def make_response(status_code: int, body) -> httpx.Response:
    if isinstance(body, str):
        content = body.encode()
        headers = {"content-type": "text/plain"}
    else:
        content = json.dumps(body).encode()
        headers = {"content-type": "application/json"}
    return httpx.Response(status_code, content=content, headers=headers)


@pytest.fixture
def client():
    return ArqenClient(base_url=BASE_URL)


# --- _get_headers ---

def test_get_headers(client):
    headers = client._get_headers("mytoken")
    assert headers == {"Authorization": "Bearer mytoken"}


# --- _raise_for_status ---

def test_raise_for_status_ok(client):
    response = make_response(200, {})
    client._raise_for_status(response)  # no exception


def test_raise_for_status_401(client):
    response = make_response(401, "Unauthorized")
    with pytest.raises(ArqenAuthError) as exc_info:
        client._raise_for_status(response)
    assert exc_info.value.status_code == 401


def test_raise_for_status_404(client):
    response = make_response(404, "Not found")
    with pytest.raises(ArqenNotFoundError) as exc_info:
        client._raise_for_status(response)
    assert exc_info.value.status_code == 404


def test_raise_for_status_500(client):
    response = make_response(500, "Internal Server Error")
    with pytest.raises(ArqenAPIError) as exc_info:
        client._raise_for_status(response)
    assert exc_info.value.status_code == 500


def test_raise_for_status_400(client):
    response = make_response(400, "Bad Request")
    with pytest.raises(ArqenAPIError):
        client._raise_for_status(response)


# --- get_balance ---

@pytest.mark.asyncio
async def test_get_balance_success(client):
    payload = {"balance": 100.0, "currency": "USD"}
    mock_response = make_response(200, payload)

    with patch("httpx.AsyncClient") as mock_cls:
        mock_instance = AsyncMock()
        mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
        mock_instance.__aexit__ = AsyncMock(return_value=False)
        mock_instance.get = AsyncMock(return_value=mock_response)
        mock_cls.return_value = mock_instance

        result = await client.get_balance("acc-123", TOKEN)

    assert result == payload
    mock_instance.get.assert_awaited_once_with(
        "/api/v1/accounts/acc-123/balance",
        headers={"Authorization": f"Bearer {TOKEN}"},
    )


@pytest.mark.asyncio
async def test_get_balance_auth_error(client):
    mock_response = make_response(401, "Unauthorized")

    with patch("httpx.AsyncClient") as mock_cls:
        mock_instance = AsyncMock()
        mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
        mock_instance.__aexit__ = AsyncMock(return_value=False)
        mock_instance.get = AsyncMock(return_value=mock_response)
        mock_cls.return_value = mock_instance

        with pytest.raises(ArqenAuthError):
            await client.get_balance("acc-123", TOKEN)


# --- issue_card ---

@pytest.mark.asyncio
async def test_issue_card_success(client):
    params = {"group_id": "grp-1", "label": "Test Card"}
    payload = {"card_id": "card-456", "status": "active"}
    mock_response = make_response(201, payload)

    with patch("httpx.AsyncClient") as mock_cls:
        mock_instance = AsyncMock()
        mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
        mock_instance.__aexit__ = AsyncMock(return_value=False)
        mock_instance.post = AsyncMock(return_value=mock_response)
        mock_cls.return_value = mock_instance

        result = await client.issue_card(params, TOKEN)

    assert result == payload
    mock_instance.post.assert_awaited_once_with(
        "/api/v1/cards",
        json=params,
        headers={"Authorization": f"Bearer {TOKEN}"},
    )


# --- list_cards ---

@pytest.mark.asyncio
async def test_list_cards_success(client):
    payload = {"cards": [], "total": 0}
    mock_response = make_response(200, payload)

    with patch("httpx.AsyncClient") as mock_cls:
        mock_instance = AsyncMock()
        mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
        mock_instance.__aexit__ = AsyncMock(return_value=False)
        mock_instance.get = AsyncMock(return_value=mock_response)
        mock_cls.return_value = mock_instance

        result = await client.list_cards("grp-1", TOKEN, page=2, limit=10)

    assert result == payload
    mock_instance.get.assert_awaited_once_with(
        "/api/v1/cards",
        params={"group_id": "grp-1", "page": 2, "limit": 10},
        headers={"Authorization": f"Bearer {TOKEN}"},
    )


# --- get_card ---

@pytest.mark.asyncio
async def test_get_card_success(client):
    payload = {"card_id": "card-1", "status": "active"}
    mock_response = make_response(200, payload)

    with patch("httpx.AsyncClient") as mock_cls:
        mock_instance = AsyncMock()
        mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
        mock_instance.__aexit__ = AsyncMock(return_value=False)
        mock_instance.get = AsyncMock(return_value=mock_response)
        mock_cls.return_value = mock_instance

        result = await client.get_card("card-1", TOKEN)

    assert result == payload


@pytest.mark.asyncio
async def test_get_card_not_found(client):
    mock_response = make_response(404, "Not Found")

    with patch("httpx.AsyncClient") as mock_cls:
        mock_instance = AsyncMock()
        mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
        mock_instance.__aexit__ = AsyncMock(return_value=False)
        mock_instance.get = AsyncMock(return_value=mock_response)
        mock_cls.return_value = mock_instance

        with pytest.raises(ArqenNotFoundError):
            await client.get_card("nonexistent", TOKEN)


# --- get_card_details ---

@pytest.mark.asyncio
async def test_get_card_details_returns_jwe(client):
    jwe_string = "eyJhbGciOiJSU0EtT0FFUC0yNTYifQ.fake.jwe.token"
    mock_response = make_response(200, jwe_string)

    with patch("httpx.AsyncClient") as mock_cls:
        mock_instance = AsyncMock()
        mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
        mock_instance.__aexit__ = AsyncMock(return_value=False)
        mock_instance.get = AsyncMock(return_value=mock_response)
        mock_cls.return_value = mock_instance

        result = await client.get_card_details("card-1", TOKEN)

    assert result == jwe_string


# --- update_card ---

@pytest.mark.asyncio
async def test_update_card_success(client):
    params = {"limit": 500}
    payload = {"card_id": "card-1", "limit": 500}
    mock_response = make_response(200, payload)

    with patch("httpx.AsyncClient") as mock_cls:
        mock_instance = AsyncMock()
        mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
        mock_instance.__aexit__ = AsyncMock(return_value=False)
        mock_instance.patch = AsyncMock(return_value=mock_response)
        mock_cls.return_value = mock_instance

        result = await client.update_card("card-1", params, TOKEN)

    assert result == payload
    mock_instance.patch.assert_awaited_once_with(
        "/api/v1/cards/card-1",
        json=params,
        headers={"Authorization": f"Bearer {TOKEN}"},
    )


# --- close_card ---

@pytest.mark.asyncio
async def test_close_card_success(client):
    mock_response = make_response(204, "")

    with patch("httpx.AsyncClient") as mock_cls:
        mock_instance = AsyncMock()
        mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
        mock_instance.__aexit__ = AsyncMock(return_value=False)
        mock_instance.delete = AsyncMock(return_value=mock_response)
        mock_cls.return_value = mock_instance

        await client.close_card("card-1", TOKEN)  # should not raise

    mock_instance.delete.assert_awaited_once_with(
        "/api/v1/cards/card-1",
        headers={"Authorization": f"Bearer {TOKEN}"},
    )


@pytest.mark.asyncio
async def test_close_card_api_error(client):
    mock_response = make_response(422, "Unprocessable")

    with patch("httpx.AsyncClient") as mock_cls:
        mock_instance = AsyncMock()
        mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
        mock_instance.__aexit__ = AsyncMock(return_value=False)
        mock_instance.delete = AsyncMock(return_value=mock_response)
        mock_cls.return_value = mock_instance

        with pytest.raises(ArqenAPIError) as exc_info:
            await client.close_card("card-1", TOKEN)
        assert exc_info.value.status_code == 422


# --- list_account_transactions ---

@pytest.mark.asyncio
async def test_list_account_transactions_success(client):
    payload = {"transactions": [], "total": 0}
    mock_response = make_response(200, payload)

    with patch("httpx.AsyncClient") as mock_cls:
        mock_instance = AsyncMock()
        mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
        mock_instance.__aexit__ = AsyncMock(return_value=False)
        mock_instance.get = AsyncMock(return_value=mock_response)
        mock_cls.return_value = mock_instance

        result = await client.list_account_transactions(
            "acc-1", TOKEN, filters={"page": 1, "limit": 10}
        )

    assert result == payload
    mock_instance.get.assert_awaited_once_with(
        "/api/v1/transactions",
        params={"account_id": "acc-1", "page": 1, "limit": 10},
        headers={"Authorization": f"Bearer {TOKEN}"},
    )


@pytest.mark.asyncio
async def test_list_account_transactions_no_filters(client):
    payload = {"transactions": [], "total": 0}
    mock_response = make_response(200, payload)

    with patch("httpx.AsyncClient") as mock_cls:
        mock_instance = AsyncMock()
        mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
        mock_instance.__aexit__ = AsyncMock(return_value=False)
        mock_instance.get = AsyncMock(return_value=mock_response)
        mock_cls.return_value = mock_instance

        result = await client.list_account_transactions("acc-1", TOKEN)

    assert result == payload
    mock_instance.get.assert_awaited_once_with(
        "/api/v1/transactions",
        params={"account_id": "acc-1"},
        headers={"Authorization": f"Bearer {TOKEN}"},
    )


# --- list_card_transactions ---

@pytest.mark.asyncio
async def test_list_card_transactions_success(client):
    payload = {"transactions": [{"id": "tx-1"}], "total": 1}
    mock_response = make_response(200, payload)

    with patch("httpx.AsyncClient") as mock_cls:
        mock_instance = AsyncMock()
        mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
        mock_instance.__aexit__ = AsyncMock(return_value=False)
        mock_instance.get = AsyncMock(return_value=mock_response)
        mock_cls.return_value = mock_instance

        result = await client.list_card_transactions(
            "card-1", TOKEN, filters={"page": 1}
        )

    assert result == payload
    mock_instance.get.assert_awaited_once_with(
        "/api/v1/cards/card-1/transactions",
        params={"page": 1},
        headers={"Authorization": f"Bearer {TOKEN}"},
    )


@pytest.mark.asyncio
async def test_list_card_transactions_no_filters(client):
    payload = {"transactions": [], "total": 0}
    mock_response = make_response(200, payload)

    with patch("httpx.AsyncClient") as mock_cls:
        mock_instance = AsyncMock()
        mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
        mock_instance.__aexit__ = AsyncMock(return_value=False)
        mock_instance.get = AsyncMock(return_value=mock_response)
        mock_cls.return_value = mock_instance

        result = await client.list_card_transactions("card-1", TOKEN)

    assert result == payload
    mock_instance.get.assert_awaited_once_with(
        "/api/v1/cards/card-1/transactions",
        params={},
        headers={"Authorization": f"Bearer {TOKEN}"},
    )
