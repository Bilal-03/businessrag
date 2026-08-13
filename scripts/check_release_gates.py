#!/usr/bin/env python3
"""Fail CI/rollout until evidence, coverage, and reviewer gates are complete."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "api"))

from src.integrations.supabase_rest import SupabaseRestClient  # noqa: E402


async def main() -> int:
    root = Path(__file__).resolve().parents[1]
    scenarios_path = root / "evals" / "trust_scenarios.jsonl"
    scenarios = [json.loads(line) for line in scenarios_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    approved_scenarios = sum(row["review_status"] == "approved" for row in scenarios)
    client = SupabaseRestClient.admin()
    coverage = await client.request("GET", "compliance_coverage_cells", params={"select": "status,reviewer_user_id,reviewed_at"})
    open_changes = await client.request("GET", "source_change_events", params={"select": "id", "resolution_status": "eq.open", "severity": "in.(high,critical)"})
    stale_claims = await client.request("GET", "reviewed_claims", params={"select": "id", "lifecycle": "eq.published", "revalidate_by": f"lt.{datetime.now(UTC).date().isoformat()}"})
    gates = {
        "approved_evaluation_scenarios": {"required": 2000, "actual": approved_scenarios},
        "coverage_cells_reviewed": {"required": len(coverage), "actual": sum(row["status"] in {"covered", "not_applicable"} and row["reviewer_user_id"] and row["reviewed_at"] for row in coverage)},
        "open_high_or_critical_source_changes": {"required": 0, "actual": len(open_changes)},
        "stale_published_claims": {"required": 0, "actual": len(stale_claims)},
    }
    print(json.dumps(gates, indent=2))
    return 0 if all(item["actual"] == item["required"] for item in gates.values()) else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
