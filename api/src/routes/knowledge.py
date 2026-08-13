from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from src.auth.dependencies import get_current_user
from src.compliance.applicability import validate_rule
from src.contracts.knowledge import (
    AnswerFeedbackCreate,
    ClaimCreate,
    LifecycleTransition,
    ReviewDecisionCreate,
    SourceDocumentCreate,
    SourcePassageCreate,
    SourceVersionCreate,
    SourceVersionTransition,
)
from src.integrations.supabase_rest import SupabaseRestClient, SupabaseRestError

router = APIRouter(prefix="/api", tags=["knowledge"])


def _client(request: Request) -> SupabaseRestClient:
    token = getattr(request.state, "access_token", None)
    if not token:
        raise HTTPException(status_code=401, detail="Authentication is required.")
    return SupabaseRestClient(token)


def _uuid(value: str) -> str:
    try:
        return str(UUID(value))
    except (ValueError, TypeError, AttributeError) as exc:
        raise HTTPException(status_code=422, detail="A valid UUID is required.") from exc


async def _roles(client: SupabaseRestClient, user_id: str) -> set[str]:
    rows = await client.request(
        "GET", "reviewer_assignments",
        params={"select": "reviewer_role", "reviewer_user_id": f"eq.{user_id}", "active": "eq.true"},
    )
    return {row["reviewer_role"] for row in rows}


async def _require_reviewer(client: SupabaseRestClient, user_id: str, role: str | None = None) -> set[str]:
    roles = await _roles(client, user_id)
    if not roles or (role and role not in roles and "catalog_admin" not in roles):
        raise HTTPException(status_code=403, detail="An active qualified reviewer assignment is required.")
    return roles


async def _audit(client: SupabaseRestClient, user_id: str, entity_type: str, entity_id: str, action: str, from_state: str | None, to_state: str | None, reason: str) -> None:
    await client.request("POST", "review_events", payload={
        "actor_id": user_id, "entity_type": entity_type, "entity_id": entity_id,
        "action": action, "from_state": from_state, "to_state": to_state, "reason": reason,
    })


@router.post("/answers/feedback", status_code=status.HTTP_201_CREATED)
async def create_answer_feedback(request: Request, body: AnswerFeedbackCreate, user_id: str = Depends(get_current_user)):
    payload = body.model_dump(mode="json", exclude_none=True)
    payload["owner_id"] = user_id
    try:
        rows = await _client(request).request("POST", "answer_feedback", payload=payload)
    except SupabaseRestError as exc:
        raise HTTPException(status_code=503, detail="Feedback could not be saved.") from exc
    return rows[0]


@router.get("/knowledge/sources/{source_id}")
async def source_detail(request: Request, source_id: str, _user_id: str = Depends(get_current_user)):
    source_id = _uuid(source_id)
    client = _client(request)
    try:
        sources = await client.request("GET", "source_documents", params={"select": "*", "id": f"eq.{source_id}", "limit": 1})
        if not sources:
            raise HTTPException(status_code=404, detail="Source not found.")
        versions = await client.request("GET", "source_versions", params={"select": "id,version_label,publication_date,effective_from,effective_to,retrieved_at,last_checked_at,content_hash,fetch_status,review_status", "source_document_id": f"eq.{source_id}", "order": "retrieved_at.desc"})
        return {"source": sources[0], "versions": versions}
    except SupabaseRestError as exc:
        raise HTTPException(status_code=503, detail="Source details are unavailable.") from exc


@router.get("/review/me")
async def reviewer_identity(request: Request, user_id: str = Depends(get_current_user)):
    roles = await _roles(_client(request), user_id)
    return {"is_reviewer": bool(roles), "roles": sorted(roles)}


@router.get("/review/queue")
async def review_queue(request: Request, lifecycle: str = Query("in_review"), user_id: str = Depends(get_current_user)):
    client = _client(request)
    await _require_reviewer(client, user_id)
    if lifecycle not in {"draft", "in_review", "published", "rejected", "quarantined", "superseded"}:
        raise HTTPException(status_code=422, detail="Unknown lifecycle state.")
    return await client.request("GET", "reviewed_claims", params={"select": "*", "lifecycle": f"eq.{lifecycle}", "order": "updated_at.asc", "limit": 200})


@router.get("/review/change-events")
async def source_change_queue(request: Request, user_id: str = Depends(get_current_user)):
    client = _client(request)
    await _require_reviewer(client, user_id)
    return await client.request("GET", "source_change_events", params={"select": "*", "resolution_status": "eq.open", "order": "detected_at.asc", "limit": 200})


@router.get("/review/audit")
async def review_audit(request: Request, user_id: str = Depends(get_current_user)):
    client = _client(request)
    await _require_reviewer(client, user_id)
    return await client.request("GET", "review_events", params={"select": "*", "order": "created_at.desc", "limit": 200})


@router.post("/review/sources", status_code=status.HTTP_201_CREATED)
async def create_source(request: Request, body: SourceDocumentCreate, user_id: str = Depends(get_current_user)):
    client = _client(request)
    await _require_reviewer(client, user_id)
    rows = await client.request("POST", "source_documents", payload=body.model_dump(mode="json"))
    return rows[0]


@router.post("/review/passages", status_code=status.HTTP_201_CREATED)
async def create_passage(request: Request, body: SourcePassageCreate, user_id: str = Depends(get_current_user)):
    client = _client(request)
    await _require_reviewer(client, user_id)
    rows = await client.request("POST", "source_passages", payload=body.model_dump(mode="json"))
    return rows[0]


@router.post("/review/source-versions", status_code=status.HTTP_201_CREATED)
async def create_source_version(request: Request, body: SourceVersionCreate, user_id: str = Depends(get_current_user)):
    client = _client(request)
    await _require_reviewer(client, user_id)
    rows = await client.request("POST", "source_versions", payload=body.model_dump(mode="json", exclude_none=True) | {"review_status": "draft"})
    await _audit(client, user_id, "source_version", rows[0]["id"], "created", None, "draft", "Immutable source snapshot registered.")
    return rows[0]


@router.post("/review/claims", status_code=status.HTTP_201_CREATED)
async def create_claim(request: Request, body: ClaimCreate, user_id: str = Depends(get_current_user)):
    client = _client(request)
    await _require_reviewer(client, user_id)
    try:
        validate_rule(body.applicability_rule)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    payload = body.model_dump(mode="json", exclude_none=True)
    payload.update({"created_by": user_id, "lifecycle": "draft", "current": True})
    rows = await client.request("POST", "reviewed_claims", payload=payload)
    await _audit(client, user_id, "claim", rows[0]["id"], "created", None, "draft", "Claim drafted for qualified review.")
    return rows[0]


@router.post("/review/claims/{claim_id}/reviews", status_code=status.HTTP_201_CREATED)
async def review_claim(request: Request, claim_id: str, body: ReviewDecisionCreate, user_id: str = Depends(get_current_user)):
    claim_id = _uuid(claim_id)
    client = _client(request)
    await _require_reviewer(client, user_id, body.reviewer_role)
    payload = body.model_dump(mode="json") | {"claim_id": claim_id, "reviewer_user_id": user_id}
    rows = await client.request("POST", "claim_reviews", payload=payload)
    action = "approved" if body.decision == "approve" else "rejected" if body.decision == "reject" else "changes_requested"
    await _audit(client, user_id, "claim", claim_id, action, "in_review", "in_review", body.comments)
    return rows[0]


@router.post("/review/claims/{claim_id}/transition")
async def transition_claim(request: Request, claim_id: str, body: LifecycleTransition, user_id: str = Depends(get_current_user)):
    claim_id = _uuid(claim_id)
    client = _client(request)
    roles = await _require_reviewer(client, user_id)
    rows = await client.request("GET", "reviewed_claims", params={"select": "id,lifecycle", "id": f"eq.{claim_id}", "limit": 1})
    if not rows:
        raise HTTPException(status_code=404, detail="Claim not found.")
    previous = rows[0]["lifecycle"]
    if body.lifecycle in {"published", "superseded", "quarantined"} and "catalog_admin" not in roles:
        raise HTTPException(status_code=403, detail="Catalog-admin approval is required for this transition.")
    payload = {"lifecycle": body.lifecycle}
    if body.lifecycle in {"superseded", "quarantined", "rejected"}:
        payload["current"] = False
    updated = await client.request("PATCH", "reviewed_claims", params={"id": f"eq.{claim_id}"}, payload=payload)
    action = (
        "rolled_back" if previous == "published" and body.lifecycle == "quarantined"
        else "submitted" if body.lifecycle == "in_review"
        else "rejected" if body.lifecycle == "rejected"
        else "superseded" if body.lifecycle == "superseded"
        else "quarantined" if body.lifecycle == "quarantined"
        else "published" if body.lifecycle == "published"
        else "created"
    )
    await _audit(client, user_id, "claim", claim_id, action, previous, body.lifecycle, body.reason)
    return updated[0]


@router.post("/review/source-versions/{version_id}/transition")
async def transition_source_version(request: Request, version_id: str, body: SourceVersionTransition, user_id: str = Depends(get_current_user)):
    version_id = _uuid(version_id)
    client = _client(request)
    await _require_reviewer(client, user_id, "catalog_admin")
    rows = await client.request("GET", "source_versions", params={"select": "id,review_status", "id": f"eq.{version_id}", "limit": 1})
    if not rows:
        raise HTTPException(status_code=404, detail="Source version not found.")
    previous = rows[0]["review_status"]
    updated = await client.request("PATCH", "source_versions", params={"id": f"eq.{version_id}"}, payload={"review_status": body.review_status, "last_checked_at": datetime.now(timezone.utc).isoformat()})
    action = "approved" if body.review_status == "approved" else "quarantined" if body.review_status == "quarantined" else "submitted"
    await _audit(client, user_id, "source_version", version_id, action, previous, body.review_status, body.reason)
    return updated[0]
