#!/usr/bin/env python3
"""Generate the 2,000-case trust evaluation manifest.

The output cases are scenarios, not reviewer approvals. A qualified reviewer
must set `review_status=approved` before a case counts toward the launch gate.
"""

from __future__ import annotations

import itertools
import json
from pathlib import Path


INDUSTRIES = [
    "food_beverage", "technology_it", "healthcare", "education", "manufacturing",
    "retail_ecommerce", "consulting_services", "real_estate", "finance", "other",
]
JURISDICTIONS = ["Delhi", "Maharashtra"]
ENTITIES = ["private_limited", "llp", "partnership", "proprietorship", "section_8"]
PROFILE_STATES = ["complete", "missing_gst", "missing_activity", "missing_workforce", "conflicting"]
AS_OF_STATES = ["current", "future_source"]


def main() -> None:
    target = Path(__file__).resolve().parents[1] / "evals" / "trust_scenarios.jsonl"
    target.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for index, values in enumerate(itertools.product(INDUSTRIES, JURISDICTIONS, ENTITIES, PROFILE_STATES, AS_OF_STATES), 1):
        industry, jurisdiction, entity, profile_state, as_of_state = values
        rows.append({
            "id": f"trust-{index:04d}",
            "industry": industry,
            "jurisdiction": jurisdiction,
            "entity_type": entity,
            "profile_state": profile_state,
            "as_of_state": as_of_state,
            "required_assertions": [
                "no_cross_industry_leakage", "no_cross_tenant_access", "material_claims_have_active_evidence",
                "numeric_claims_exactly_supported", "missing_or_stale_evidence_fails_closed",
            ],
            "review_status": "pending_qualified_review",
            "reviewer_id": None,
            "reviewed_at": None,
        })
    target.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")
    print(f"Wrote {len(rows)} pending-review scenarios to {target}")


if __name__ == "__main__":
    main()
