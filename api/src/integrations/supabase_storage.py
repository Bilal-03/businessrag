from __future__ import annotations

from urllib.parse import quote

import httpx

from config import get_settings
from src.integrations.supabase_rest import SupabaseRestError


class SupabaseStorageClient:
    """Small Supabase Storage adapter for private document objects."""

    def __init__(self, token: str | None = None, *, service_role: bool = False):
        settings = get_settings()
        if service_role:
            if not settings.supabase_service_role_key:
                raise SupabaseRestError(503, "Server-side Supabase storage is not configured.")
            self.api_key = settings.supabase_service_role_key
            self.token = settings.supabase_service_role_key
        else:
            self.api_key = settings.supabase_anon_key
            self.token = token or ""
        self.base_url = f"{settings.supabase_url.rstrip('/')}/storage/v1/object"
        self.bucket = settings.document_storage_bucket

    @classmethod
    def admin(cls) -> "SupabaseStorageClient":
        return cls(service_role=True)

    def _url(self, path: str) -> str:
        safe_path = quote(path.strip('/'), safe='/')
        return f"{self.base_url}/{quote(self.bucket, safe='')}/{safe_path}"

    def _headers(self, content_type: str | None = None) -> dict[str, str]:
        headers = {
            "apikey": self.api_key,
            "Authorization": f"Bearer {self.token}",
        }
        if content_type:
            headers["Content-Type"] = content_type
        return headers

    async def upload(self, path: str, content: bytes, content_type: str = "application/pdf") -> None:
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(90.0, connect=10.0)) as client:
                response = await client.post(
                    self._url(path),
                    headers={**self._headers(content_type), "x-upsert": "false"},
                    content=content,
                )
        except httpx.HTTPError as exc:
            raise SupabaseRestError(503, "Document storage is temporarily unavailable.") from exc
        if response.status_code >= 400:
            raise SupabaseRestError(response.status_code, "Document storage rejected the upload.")

    async def download(self, path: str) -> bytes:
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(90.0, connect=10.0)) as client:
                response = await client.get(self._url(path), headers=self._headers())
        except httpx.HTTPError as exc:
            raise SupabaseRestError(503, "Document storage is temporarily unavailable.") from exc
        if response.status_code >= 400:
            raise SupabaseRestError(response.status_code, "The stored document could not be read.")
        return response.content

    async def delete(self, path: str) -> None:
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=5.0)) as client:
                response = await client.delete(self._url(path), headers=self._headers())
        except httpx.HTTPError as exc:
            raise SupabaseRestError(503, "Document storage is temporarily unavailable.") from exc
        if response.status_code >= 400 and response.status_code != 404:
            raise SupabaseRestError(response.status_code, "The stored document could not be removed.")
