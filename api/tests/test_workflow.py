from datetime import datetime, timedelta, timezone

import jwt
import pytest
from config import get_settings
from fastapi.testclient import TestClient
from main import app
from src.integrations import supabase_rest
from src.routes import workflow

client = TestClient(app)
settings = get_settings()
BUSINESS_ID = "22222222-2222-4222-8222-222222222222"


def auth_headers(*, audience=None, expires_in_minutes=5):
    now = datetime.now(timezone.utc)
    token = jwt.encode(
        {
            "sub": "test-user-id",
            "aud": audience or settings.supabase_jwt_audience,
            "iss": settings.jwt_issuer,
            "iat": now,
            "exp": now + timedelta(minutes=expires_in_minutes),
        },
        settings.supabase_jwt_secret,
        algorithm="HS256",
    )
    return {"Authorization": f"Bearer {token}"}


def obligation(
    obligation_id: str,
    *,
    jurisdiction="India",
    rule=None,
    effective_from="2026-01-01",
    effective_to=None,
    review_status="published",
    published=True,
    source_url="https://example.gov.in/source",
):
    return {
        "id": obligation_id,
        "jurisdiction": jurisdiction,
        "title": obligation_id,
        "description": "Use the current official source.",
        "source_url": source_url,
        "source_version": "2026-01",
        "effective_from": effective_from,
        "effective_to": effective_to,
        "published": published,
        "review_status": review_status,
        "source_citation": "Official notice, section 1.",
        "review_owner": "domain-review",
        "reviewed_at": "2026-01-01T00:00:00Z",
        "applicability_version": 2,
        "applicability_rule": rule or {"field": "industry_code", "op": "eq", "value": "other"},
        "revalidate_by": "2026-11-01",
        "kill_switch": False,
        "primary_claim_id": f"claim-{obligation_id}",
        "due_date_rule": None,
        "evidence_requirements": [],
        "risk_level": "medium",
        "metadata": {},
    }


def plan_store(*, industry_code="technology_it", state_code="DL", profile=None, rows=None, owns_business=True):
    profile_row = {
        "business_id": BUSINESS_ID,
        "owner_id": "test-user-id",
        "profile_version": 2,
        "regulated_activities": [],
        "gst_registration_status": "not_registered",
        "turnover_band": None,
        "employee_count_band": None,
        "has_physical_establishment": False,
        "operates_multiple_states": None,
        "imports_goods_services": None,
        "exports_goods_services": None,
        "answers": {},
        **(profile or {}),
    }
    obligations = rows or []

    async def fake_request(self, method, table, *, params=None, payload=None):
        if table == "businesses":
            if method == "PATCH":
                return [{
                    "id": BUSINESS_ID,
                    "owner_id": "test-user-id",
                    "legal_name": "Test Business",
                    "entity_type": "Private Limited (Pvt Ltd)",
                    "industry": payload["industry"],
                    "industry_code": payload["industry_code"],
                    "state_code": state_code,
                    "status": "operating",
                }]
            return [{
                "id": BUSINESS_ID,
                "owner_id": "test-user-id",
                "legal_name": "Test Business",
                "entity_type": "Private Limited (Pvt Ltd)",
                "industry": None,
                "industry_code": industry_code,
                "state_code": state_code,
                "status": "operating",
            }] if owns_business else []
        if table == "business_compliance_profiles":
            if method == "PATCH":
                return [{**profile_row, **payload}]
            return [profile_row]
        if table == "obligations":
            assert params["published"] == "eq.true"
            assert params["review_status"] == "eq.published"
            return obligations
        if table == "reviewed_claims":
            return [{
                "id": row["primary_claim_id"], "obligation_id": row["id"],
                "statement_en": row["description"], "support_excerpt": "Authoritative supporting passage.",
                "source_passage_id": f"passage-{row['id']}", "lifecycle": "published", "current": True,
                "kill_switch": False, "revalidate_by": "2026-11-01", "reviewer_roles": ["lawyer"], "approval_count": 1,
                "required_reviewer_role": "lawyer", "required_approvals": 1, "claim_type": "procedure", "claim_value": True,
                "applicability_version": row["applicability_version"], "applicability_rule": row["applicability_rule"],
            } for row in obligations if row.get("published") and row.get("review_status") == "published"]
        if table == "source_passages":
            return [{
                "id": f"passage-{row['id']}", "source_version_id": f"version-{row['id']}",
                "anchor": "section 1", "page_number": 1, "passage_text": "Authoritative supporting passage.",
            } for row in obligations if row.get("published") and row.get("review_status") == "published"]
        if table == "source_versions":
            return [{
                "id": f"version-{row['id']}", "source_document_id": f"source-{row['id']}",
                "version_label": row["source_version"], "last_checked_at": "2026-08-12T00:00:00Z",
                "content_hash": "a" * 64, "fetch_status": "healthy", "review_status": "approved",
                "effective_from": row["effective_from"], "effective_to": row["effective_to"],
            } for row in obligations if row.get("published") and row.get("review_status") == "published"]
        if table == "source_documents":
            return [{
                "id": f"source-{row['id']}", "canonical_url": row["source_url"], "source_tier": 1,
                "authority_name": "Official authority", "title": "Official source", "active": True,
            } for row in obligations if row.get("published") and row.get("review_status") == "published"]
        if table in {"obligation_due_date_rules", "obligation_evidence_items"}:
            return []
        if table == "compliance_catalog_coverage":
            return [{"industry_code": industry_code, "jurisdiction": "India", "status": "partial", "notes": "Reviewed central coverage is partial."}]
        if table == "compliance_coverage_cells":
            return []
        raise AssertionError(f"unexpected table: {table}")

    return fake_request


def test_workflow_tasks_require_authentication():
    response = client.get("/api/workflow/tasks", params={"business_id": "biz-1"})
    assert response.status_code == 401


def test_jurisdiction_only_obligation_request_is_rejected():
    response = client.get(
        "/api/workflow/obligations",
        params={"jurisdiction": "Delhi"},
        headers=auth_headers(),
    )
    assert response.status_code == 422


@pytest.mark.parametrize(
    "industry_code",
    [
        "food_beverage",
        "technology_it",
        "healthcare",
        "education",
        "manufacturing",
        "retail_ecommerce",
        "consulting_services",
        "real_estate",
        "finance",
        "other",
    ],
)
def test_plan_has_no_cross_industry_food_leakage(monkeypatch, industry_code):
    food_rule = {"field": "regulated_activities", "op": "contains_any", "value": ["food_handling", "food_delivery"]}
    activities = ["food_handling"] if industry_code == "food_beverage" else []
    monkeypatch.setattr(
        supabase_rest.SupabaseRestClient,
        "request",
        plan_store(industry_code=industry_code, profile={"regulated_activities": activities}, rows=[obligation("fssai", rule=food_rule)]),
    )
    response = client.get(
        "/api/workflow/plan",
        params={"business_id": BUSINESS_ID, "as_of": "2026-08-12"},
        headers=auth_headers(),
    )
    assert response.status_code == 200
    ids = [row["id"] for row in response.json()["obligations"]]
    assert ("fssai" in ids) is (industry_code == "food_beverage")


def test_technology_marketplace_with_food_delivery_receives_food_rule(monkeypatch):
    rule = {"field": "regulated_activities", "op": "contains_any", "value": ["food_handling", "food_delivery"]}
    monkeypatch.setattr(
        supabase_rest.SupabaseRestClient,
        "request",
        plan_store(profile={"regulated_activities": ["ecommerce_marketplace", "food_delivery"]}, rows=[obligation("fssai", rule=rule)]),
    )
    response = client.get("/api/workflow/plan", params={"business_id": BUSINESS_ID}, headers=auth_headers())
    assert [row["id"] for row in response.json()["obligations"]] == ["fssai"]


def test_unknown_gst_returns_question_not_obligation(monkeypatch):
    gst_rule = {"field": "gst_registration_status", "op": "eq", "value": "registered"}
    monkeypatch.setattr(
        supabase_rest.SupabaseRestClient,
        "request",
        plan_store(profile={"gst_registration_status": None}, rows=[obligation("gstr-3b", rule=gst_rule)]),
    )
    response = client.get("/api/workflow/plan", params={"business_id": BUSINESS_ID}, headers=auth_headers())
    body = response.json()
    assert body["obligations"] == []
    assert [question["key"] for question in body["questions"]] == ["gst_registration_status"]


def test_confirmed_gst_returns_gstr_3b(monkeypatch):
    rule = {"field": "gst_registration_status", "op": "eq", "value": "registered"}
    monkeypatch.setattr(
        supabase_rest.SupabaseRestClient,
        "request",
        plan_store(profile={"gst_registration_status": "registered"}, rows=[obligation("gstr-3b", rule=rule)]),
    )
    response = client.get("/api/workflow/plan", params={"business_id": BUSINESS_ID}, headers=auth_headers())
    assert [row["id"] for row in response.json()["obligations"]] == ["gstr-3b"]


def test_plan_fails_closed_for_invalid_future_expired_and_unpublished_rules(monkeypatch):
    rows = [
        obligation("good", jurisdiction="Delhi", rule={"field": "has_physical_establishment", "op": "eq", "value": True}),
        obligation("future", effective_from="2027-01-01"),
        obligation("expired", effective_to="2026-01-01"),
        obligation("unpublished", review_status="reviewed", published=False),
        obligation("malformed", rule={"field": "industry_code", "op": "execute", "value": "technology_it"}),
        obligation("wrong-state", jurisdiction="Karnataka", rule={"field": "industry_code", "op": "eq", "value": "technology_it"}),
    ]
    monkeypatch.setattr(
        supabase_rest.SupabaseRestClient,
        "request",
        plan_store(profile={"has_physical_establishment": True}, rows=rows),
    )
    response = client.get(
        "/api/workflow/plan",
        params={"business_id": BUSINESS_ID, "as_of": "2026-08-12"},
        headers=auth_headers(),
    )
    assert [row["id"] for row in response.json()["obligations"]] == ["good"]


def test_another_users_business_cannot_be_read_or_updated(monkeypatch):
    monkeypatch.setattr(supabase_rest.SupabaseRestClient, "request", plan_store(owns_business=False))
    read = client.get("/api/workflow/plan", params={"business_id": BUSINESS_ID}, headers=auth_headers())
    update = client.patch(
        f"/api/workflow/businesses/{BUSINESS_ID}/compliance-profile",
        json={"gst_registration_status": "registered"},
        headers=auth_headers(),
    )
    assert read.status_code == 404
    assert update.status_code == 404


def test_compliance_profile_rejects_unknown_activity(monkeypatch):
    monkeypatch.setattr(supabase_rest.SupabaseRestClient, "request", plan_store())
    response = client.patch(
        f"/api/workflow/businesses/{BUSINESS_ID}/compliance-profile",
        json={"regulated_activities": ["made_up_activity"]},
        headers=auth_headers(),
    )
    assert response.status_code == 422


def test_business_applicability_update_validates_and_persists_codes(monkeypatch):
    monkeypatch.setattr(supabase_rest.SupabaseRestClient, "request", plan_store())
    response = client.patch(
        f"/api/workflow/businesses/{BUSINESS_ID}/applicability",
        json={"industry_code": "retail_ecommerce", "regulated_activities": ["physical_retail"]},
        headers=auth_headers(),
    )
    assert response.status_code == 200
    assert response.json()["business"]["industry_code"] == "retail_ecommerce"
    assert response.json()["compliance_profile"]["regulated_activities"] == ["physical_retail"]


def test_create_task_is_owner_scoped_and_returns_created_task(monkeypatch):
    captured = {}

    async def fake_request(self, method, table, *, params=None, payload=None):
        captured.update({"method": method, "table": table, "payload": payload})
        return [{
            "id": "task-1",
            "business_id": "biz-1",
            "obligation_id": None,
            "title": "Collect records",
            "status": "todo",
            "due_date": "2026-09-01",
            "completed_at": None,
            "created_at": None,
            "updated_at": None,
        }]

    monkeypatch.setattr(supabase_rest.SupabaseRestClient, "request", fake_request)
    response = client.post(
        "/api/workflow/tasks",
        headers=auth_headers(),
        json={"business_id": "biz-1", "title": "Collect records", "due_date": "2026-09-01"},
    )
    assert response.status_code == 201
    assert captured["payload"]["owner_id"] == "test-user-id"
    assert response.json()["status"] == "todo"


def test_workflow_storage_failure_is_fail_closed(monkeypatch):
    async def unavailable(*args, **kwargs):
        raise supabase_rest.SupabaseRestError(404)

    monkeypatch.setattr(supabase_rest.SupabaseRestClient, "request", unavailable)
    response = client.get("/api/workflow/plan", params={"business_id": BUSINESS_ID}, headers=auth_headers())
    assert response.status_code == 503
    assert "not available yet" in response.json()["detail"]


def test_workflow_schema_read_failure_keeps_cors_header(monkeypatch):
    async def unavailable(*args, **kwargs):
        raise supabase_rest.SupabaseRestError(400)

    monkeypatch.setattr(supabase_rest.SupabaseRestClient, "request", unavailable)
    response = client.get(
        "/api/workflow/plan",
        params={"business_id": BUSINESS_ID},
        headers={**auth_headers(), "Origin": "https://businessrag.vercel.app"},
    )
    assert response.status_code == 503
    assert response.headers.get("access-control-allow-origin")


def test_unhandled_workflow_failure_keeps_cors_header(monkeypatch):
    async def explode(*args, **kwargs):
        raise RuntimeError("simulated backend failure")

    monkeypatch.setattr(workflow, "_build_plan", explode)
    no_raise_client = TestClient(app, raise_server_exceptions=False)
    response = no_raise_client.get(
        "/api/workflow/plan",
        params={"business_id": BUSINESS_ID},
        headers={**auth_headers(), "Origin": "https://businessrag.vercel.app"},
    )
    assert response.status_code == 500
    assert response.headers.get("access-control-allow-origin")
    assert response.json()["code"] == "internal_error"
