#!/usr/bin/env python3
"""Monitor active official sources and quarantine changed high-risk claims.

Run from a private worker with SUPABASE_SERVICE_ROLE_KEY configured. This job
never publishes content. It records changes for human review and immediately
removes changed high-risk claims from the active answer set.
"""

from __future__ import annotations

import asyncio
import difflib
import hashlib
import re
from datetime import UTC, datetime

import httpx

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "api"))

from src.integrations.supabase_rest import SupabaseRestClient, SupabaseRestError  # noqa: E402
from src.integrations.supabase_storage import SupabaseStorageClient  # noqa: E402
from config import get_settings  # noqa: E402


def normalize_content(content: bytes, content_type: str) -> bytes:
    if "html" not in content_type.casefold():
        return content
    text = content.decode("utf-8", errors="ignore")
    text = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", text)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    return " ".join(text.split()).encode("utf-8")


def diff_preview(previous: str | None, observed: str | None) -> str | None:
    if not previous or not observed:
        return None
    lines = list(difflib.unified_diff(
        previous.splitlines(), observed.splitlines(), fromfile="reviewed", tofile="observed", lineterm="",
    ))
    return "\n".join(lines)[:6000] or None


async def quarantine_claims(client: SupabaseRestClient, version_id: str) -> int:
    passages = await client.request("GET", "source_passages", params={"select": "id", "source_version_id": f"eq.{version_id}"})
    if not passages:
        return 0
    passage_ids = ",".join(row["id"] for row in passages)
    claims = await client.request(
        "GET", "reviewed_claims",
        params={"select": "id", "source_passage_id": f"in.({passage_ids})", "lifecycle": "eq.published", "risk_level": "in.(high,critical)"},
    )
    for claim in claims:
        await client.request("PATCH", "reviewed_claims", params={"id": f"eq.{claim['id']}"}, payload={"lifecycle": "quarantined", "current": False})
    return len(claims)


async def monitor() -> dict[str, int]:
    client = SupabaseRestClient.admin()
    settings = get_settings()
    storage = SupabaseStorageClient.admin(bucket=settings.source_snapshot_storage_bucket)
    sources = await client.request(
        "GET", "source_documents",
        params={"select": "id,canonical_url,monitoring_frequency", "active": "eq.true", "monitoring_frequency": "in.(daily,weekly,monthly)"},
    )
    counts = {"checked": 0, "changed": 0, "unavailable": 0, "quarantined_claims": 0}
    async with httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=8.0), follow_redirects=True, headers={"User-Agent": "BizGuideSourceMonitor/1.0"}) as http:
        for source in sources:
            versions = await client.request(
                "GET", "source_versions",
                params={"select": "id,content_hash,fetch_status,extracted_text", "source_document_id": f"eq.{source['id']}", "order": "retrieved_at.desc", "limit": 1},
            )
            latest = versions[0] if versions else None
            counts["checked"] += 1
            try:
                response = await http.get(source["canonical_url"])
                response.raise_for_status()
                content_type = response.headers.get("content-type", "application/octet-stream")
                normalized = normalize_content(response.content, content_type)
                observed = hashlib.sha256(normalized).hexdigest()
                snapshot_path = f"{source['id']}/{observed}.bin"
                if latest and observed != latest["content_hash"]:
                    counts["changed"] += 1
                    await client.request("PATCH", "source_versions", params={"id": f"eq.{latest['id']}"}, payload={"fetch_status": "changed", "last_checked_at": datetime.now(UTC).isoformat()})
                    quarantined = await quarantine_claims(client, latest["id"])
                    counts["quarantined_claims"] += quarantined
                    await storage.upload(snapshot_path, response.content, content_type)
                    observed_versions = await client.request("POST", "source_versions", payload={
                        "source_document_id": source["id"], "version_label": f"Observed {datetime.now(UTC).date().isoformat()}",
                        "retrieved_at": datetime.now(UTC).isoformat(), "last_checked_at": datetime.now(UTC).isoformat(),
                        "content_hash": observed, "snapshot_path": snapshot_path,
                        "extracted_text": normalized.decode("utf-8", errors="ignore")[:1000000] if "html" in content_type.casefold() else None,
                        "fetch_status": "healthy", "review_status": "draft",
                    })
                    observed_text = normalized.decode("utf-8", errors="ignore") if "html" in content_type.casefold() else None
                    await client.request("POST", "source_change_events", payload={
                        "source_document_id": source["id"], "previous_version_id": latest["id"],
                        "observed_hash": observed, "event_type": "content_changed",
                        "severity": "critical" if quarantined else "high",
                        "details": {
                            "quarantined_claims": quarantined,
                            "observed_version_id": observed_versions[0]["id"] if observed_versions else None,
                            "diff_preview": diff_preview(latest.get("extracted_text"), observed_text),
                        },
                    })
                elif latest:
                    if latest.get("fetch_status") in {"unavailable", "error"}:
                        await client.request("POST", "source_change_events", payload={
                            "source_document_id": source["id"], "previous_version_id": latest["id"],
                            "observed_hash": observed, "event_type": "restored", "severity": "medium",
                            "details": {"restored_at": datetime.now(UTC).isoformat()},
                        })
                    await client.request("PATCH", "source_versions", params={"id": f"eq.{latest['id']}"}, payload={"last_checked_at": datetime.now(UTC).isoformat(), "fetch_status": "healthy"})
                else:
                    await storage.upload(snapshot_path, response.content, content_type)
                    await client.request("POST", "source_versions", payload={
                        "source_document_id": source["id"], "version_label": f"Observed {datetime.now(UTC).date().isoformat()}",
                        "retrieved_at": datetime.now(UTC).isoformat(), "last_checked_at": datetime.now(UTC).isoformat(),
                        "content_hash": observed, "snapshot_path": snapshot_path,
                        "extracted_text": normalized.decode("utf-8", errors="ignore")[:1000000] if "html" in content_type.casefold() else None,
                        "fetch_status": "healthy", "review_status": "draft",
                    })
            except (httpx.HTTPError, SupabaseRestError) as exc:
                counts["unavailable"] += 1
                if latest:
                    await client.request("PATCH", "source_versions", params={"id": f"eq.{latest['id']}"}, payload={"fetch_status": "unavailable", "last_checked_at": datetime.now(UTC).isoformat()})
                    quarantined = await quarantine_claims(client, latest["id"])
                    counts["quarantined_claims"] += quarantined
                await client.request("POST", "source_change_events", payload={"source_document_id": source["id"], "previous_version_id": latest["id"] if latest else None, "event_type": "unavailable", "severity": "critical" if latest else "high", "details": {"error_type": type(exc).__name__}})
    return counts


if __name__ == "__main__":
    print(asyncio.run(monitor()))
