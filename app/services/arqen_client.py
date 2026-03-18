import httpx

from app.config import settings


class ArqenAPIError(Exception):
    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = message
        super().__init__(f"Arqen API error {status_code}: {message}")


class ArqenAuthError(ArqenAPIError):
    pass


class ArqenNotFoundError(ArqenAPIError):
    pass


class ArqenClient:
    def __init__(self, base_url: str | None = None):
        self._base_url = base_url or settings.arqen_base_url

    def _get_headers(self, access_token: str) -> dict:
        return {"Authorization": f"Bearer {access_token}"}

    def _raise_for_status(self, response: httpx.Response) -> None:
        if response.status_code == 401:
            raise ArqenAuthError(response.status_code, response.text)
        if response.status_code == 404:
            raise ArqenNotFoundError(response.status_code, response.text)
        if response.status_code >= 400:
            raise ArqenAPIError(response.status_code, response.text)

    async def get_balance(self, account_id: str, access_token: str) -> dict:
        async with httpx.AsyncClient(base_url=self._base_url) as client:
            response = await client.get(
                f"/api/v1/accounts/{account_id}/balance",
                headers=self._get_headers(access_token),
            )
        self._raise_for_status(response)
        return response.json()

    async def issue_card(self, params: dict, access_token: str) -> dict:
        async with httpx.AsyncClient(base_url=self._base_url) as client:
            response = await client.post(
                "/api/v1/cards",
                json=params,
                headers=self._get_headers(access_token),
            )
        self._raise_for_status(response)
        return response.json()

    async def list_cards(
        self,
        group_id: str,
        access_token: str,
        page: int = 1,
        limit: int = 20,
    ) -> dict:
        async with httpx.AsyncClient(base_url=self._base_url) as client:
            response = await client.get(
                "/api/v1/cards",
                params={"group_id": group_id, "page": page, "limit": limit},
                headers=self._get_headers(access_token),
            )
        self._raise_for_status(response)
        return response.json()

    async def get_card(self, card_id: str, access_token: str) -> dict:
        async with httpx.AsyncClient(base_url=self._base_url) as client:
            response = await client.get(
                f"/api/v1/cards/{card_id}",
                headers=self._get_headers(access_token),
            )
        self._raise_for_status(response)
        return response.json()

    async def get_card_details(self, card_id: str, access_token: str) -> str:
        async with httpx.AsyncClient(base_url=self._base_url) as client:
            response = await client.get(
                f"/api/v1/cards/{card_id}/details",
                headers=self._get_headers(access_token),
            )
        self._raise_for_status(response)
        return response.text

    async def update_card(self, card_id: str, params: dict, access_token: str) -> dict:
        async with httpx.AsyncClient(base_url=self._base_url) as client:
            response = await client.patch(
                f"/api/v1/cards/{card_id}",
                json=params,
                headers=self._get_headers(access_token),
            )
        self._raise_for_status(response)
        return response.json()

    async def close_card(self, card_id: str, access_token: str) -> None:
        async with httpx.AsyncClient(base_url=self._base_url) as client:
            response = await client.delete(
                f"/api/v1/cards/{card_id}",
                headers=self._get_headers(access_token),
            )
        self._raise_for_status(response)

    async def list_account_transactions(
        self,
        account_id: str,
        access_token: str,
        filters: dict | None = None,
    ) -> dict:
        params = {"account_id": account_id, **(filters or {})}
        async with httpx.AsyncClient(base_url=self._base_url) as client:
            response = await client.get(
                "/api/v1/transactions",
                params=params,
                headers=self._get_headers(access_token),
            )
        self._raise_for_status(response)
        return response.json()

    async def list_card_transactions(
        self,
        card_id: str,
        access_token: str,
        filters: dict | None = None,
    ) -> dict:
        async with httpx.AsyncClient(base_url=self._base_url) as client:
            response = await client.get(
                f"/api/v1/cards/{card_id}/transactions",
                params=filters or {},
                headers=self._get_headers(access_token),
            )
        self._raise_for_status(response)
        return response.json()
