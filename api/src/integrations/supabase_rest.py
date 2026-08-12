from typing import Any

import httpx

from config import get_settings


class SupabaseRestError(Exception):
    def __init__(self, status_code: int, detail: str = "Supabase request failed"):
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


class SupabaseRestClient:
    """Minimal user-token REST adapter so Supabase RLS remains authoritative."""

    def __init__(self, token: str):
        settings = get_settings()
        self.base_url = f"{settings.supabase_url.rstrip('/')}/rest/v1"
        self.anon_key = settings.supabase_anon_key
        self.token = token

    async def request(
        self,
        method: str,
        table: str,
        *,
        params: dict[str, str | int] | None = None,
        payload: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        headers = {
            "apikey": self.anon_key,
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/json",
            "Content-Profile": "public",
            "Accept-Profile": "public",
        }
        if payload is not None:
            headers["Content-Type"] = "application/json"
            headers["Prefer"] = "return=representation"

        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(8.0, connect=3.0)) as client:
                response = await client.request(
                    method,
                    f"{self.base_url}/{table}",
                    headers=headers,
                    params=params,
                    json=payload,
                )
        except httpx.HTTPError as exc:
            raise SupabaseRestError(503, "Workflow storage is temporarily unavailable.") from exc

        if response.status_code >= 400:
            # Do not expose provider response bodies, which may contain schema details.
            raise SupabaseRestError(response.status_code)
        if response.status_code == 204 or not response.content:
            return []
        try:
            data = response.json()
        except ValueError as exc:
            raise SupabaseRestError(502, "Workflow storage returned an invalid response.") from exc
        return data if isinstance(data, list) else [data]
