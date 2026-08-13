from datetime import date, datetime, timezone
from typing import Any
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import ValidationError

from src.auth.dependencies import get_current_user
from src.contracts.workflow import (
    ObligationRead,
    TaskCreate,
    TaskRead,
    TaskUpdate,
    WorkflowSummary,
)
from src.integrations.supabase_rest import SupabaseRestClient, SupabaseRestError
from src.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/api/workflow", tags=["workflow"])


def _safe_identifier(value: str) -> str:
    if not value or len(value) > 120 or any(char not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-" for char in value):
        raise HTTPException(status_code=422, detail="The supplied identifier is invalid.")
    return value


def _client(request: Request) -> SupabaseRestClient:
    token = getattr(request.state, "access_token", None)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication is required.")
    return SupabaseRestClient(token)


def _storage_error(exc: SupabaseRestError, operation: str) -> HTTPException:
    logger.warning(
        "workflow_storage_failed",
        extra={"event": "workflow_storage_failed", "operation": operation, "status_code": exc.status_code},
    )
    # Read failures are commonly caused by an unapplied or stale schema
    # (PostgREST reports that as 400/404). Keep the response fail-closed and
    # actionable instead of presenting a schema mismatch as a user input
    # error. Mutation validation errors retain their 400 response.
    if operation in {"list_obligations", "list_tasks", "summary"}:
        return HTTPException(
            status_code=503,
            detail="Compliance Plan data is not available yet. Apply the workflow schema before using this view.",
        )
    if exc.status_code in {400, 409, 422}:
        return HTTPException(status_code=400, detail="The workflow change is invalid. Check the business and obligation IDs.")
    return HTTPException(
        status_code=503,
        detail="Compliance Plan data is not available yet. Apply the workflow schema before using this view.",
    )


def _active_on(obligation: ObligationRead, as_of: date) -> bool:
    if not obligation.effective_from:
        return False
    if obligation.effective_from and obligation.effective_from > as_of:
        return False
    if obligation.effective_to and obligation.effective_to < as_of:
        return False
    return True


def _has_review_evidence(obligation: ObligationRead, as_of: date) -> bool:
    if not obligation.published or obligation.review_status != "published":
        return False
    if not obligation.source_citation or not obligation.source_citation.strip():
        return False
    if not obligation.review_owner or not obligation.review_owner.strip():
        return False
    parsed_source = urlparse(obligation.source_url)
    source_host = (parsed_source.hostname or "").casefold()
    if parsed_source.scheme.casefold() != "https" or not parsed_source.netloc:
        return False
    if not (source_host.endswith(".gov.in") or source_host.endswith(".nic.in") or source_host.endswith(".org.in")):
        return False
    if not obligation.reviewed_at or obligation.reviewed_at.date() > as_of:
        return False
    return True


def _eligible_on(obligation: ObligationRead, as_of: date) -> bool:
    return _has_review_evidence(obligation, as_of) and _active_on(obligation, as_of)


def _matches_jurisdiction(obligation: ObligationRead, normalized_jurisdiction: str | None) -> bool:
    if not normalized_jurisdiction:
        return True
    normalized_obligation = obligation.jurisdiction.casefold()
    if normalized_obligation == normalized_jurisdiction:
        return True
    return normalized_jurisdiction != "india" and normalized_obligation in {"india", "central", "all-india"}


async def _list_obligation_rows(client: SupabaseRestClient) -> list[ObligationRead]:
    rows = await client.request(
        "GET",
        "obligations",
        params={
            "select": "id,jurisdiction,title,description,source_url,source_version,effective_from,effective_to,published,review_status,source_citation,review_owner,reviewed_at,metadata",
            "published": "eq.true",
            "review_status": "eq.published",
            "source_citation": "not.is.null",
            "review_owner": "not.is.null",
            "reviewed_at": "not.is.null",
            "order": "effective_from.asc",
        },
    )
    obligations = []
    for row in rows:
        try:
            obligations.append(ObligationRead.model_validate(row))
        except ValidationError:
            # A malformed catalog row is not a reason to show an unverified
            # claim. The next controlled import can repair it safely.
            logger.warning(
                "workflow_obligation_row_rejected",
                extra={"event": "workflow_obligation_row_rejected"},
            )
    return obligations


async def _list_task_rows(client: SupabaseRestClient, business_id: str) -> list[TaskRead]:
    rows = await client.request(
        "GET",
        "tasks",
        params={
            "select": "id,business_id,obligation_id,title,status,due_date,completed_at,created_at,updated_at",
            "business_id": f"eq.{business_id}",
            "order": "created_at.desc",
        },
    )
    return [TaskRead.model_validate(row) for row in rows]


@router.get("/obligations", response_model=list[ObligationRead])
async def list_obligations(
    request: Request,
    jurisdiction: str | None = Query(default=None, min_length=2, max_length=120),
    as_of: date | None = None,
    _user_id: str = Depends(get_current_user),
):
    """Return only reviewed, published obligations active on the requested date."""
    try:
        obligations = await _list_obligation_rows(_client(request))
    except SupabaseRestError as exc:
        raise _storage_error(exc, "list_obligations") from exc

    effective_date = as_of or date.today()
    normalized_jurisdiction = jurisdiction.strip().casefold() if jurisdiction else None
    return [
        obligation
        for obligation in obligations
        if _eligible_on(obligation, effective_date)
        and _matches_jurisdiction(obligation, normalized_jurisdiction)
    ]


@router.get("/tasks", response_model=list[TaskRead])
async def list_tasks(
    request: Request,
    business_id: str = Query(..., min_length=1, max_length=120),
    _user_id: str = Depends(get_current_user),
):
    business_id = _safe_identifier(business_id)
    try:
        return await _list_task_rows(_client(request), business_id)
    except SupabaseRestError as exc:
        raise _storage_error(exc, "list_tasks") from exc


@router.post("/tasks", response_model=TaskRead, status_code=status.HTTP_201_CREATED)
async def create_task(
    request: Request,
    body: TaskCreate,
    user_id: str = Depends(get_current_user),
):
    payload: dict[str, Any] = body.model_dump(mode="json", exclude_none=True)
    payload["owner_id"] = user_id
    if body.status == "done":
        payload["completed_at"] = datetime.now(timezone.utc).isoformat()
    try:
        rows = await _client(request).request("POST", "tasks", payload=payload)
    except SupabaseRestError as exc:
        raise _storage_error(exc, "create_task") from exc
    if not rows:
        raise HTTPException(status_code=502, detail="The workflow store did not return the created task.")
    return TaskRead.model_validate(rows[0])


@router.patch("/tasks/{task_id}", response_model=TaskRead)
async def update_task(
    request: Request,
    task_id: str,
    body: TaskUpdate,
    _user_id: str = Depends(get_current_user),
):
    task_id = _safe_identifier(task_id)
    payload = body.model_dump(mode="json", exclude_unset=True)
    if body.status == "done":
        payload["completed_at"] = datetime.now(timezone.utc).isoformat()
    elif body.status:
        payload["completed_at"] = None
    if not payload:
        raise HTTPException(status_code=422, detail="Provide at least one task field to update.")
    try:
        rows = await _client(request).request(
            "PATCH",
            "tasks",
            params={"id": f"eq.{task_id}"},
            payload=payload,
        )
    except SupabaseRestError as exc:
        raise _storage_error(exc, "update_task") from exc
    if not rows:
        raise HTTPException(status_code=404, detail="Task not found.")
    return TaskRead.model_validate(rows[0])


@router.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(
    request: Request,
    task_id: str,
    _user_id: str = Depends(get_current_user),
):
    task_id = _safe_identifier(task_id)
    try:
        await _client(request).request("DELETE", "tasks", params={"id": f"eq.{task_id}"})
    except SupabaseRestError as exc:
        raise _storage_error(exc, "delete_task") from exc
    return None


@router.get("/summary", response_model=WorkflowSummary)
async def workflow_summary(
    request: Request,
    business_id: str = Query(..., min_length=1, max_length=120),
    _user_id: str = Depends(get_current_user),
):
    business_id = _safe_identifier(business_id)
    try:
        client = _client(request)
        obligations = await _list_obligation_rows(client)
        tasks = await _list_task_rows(client, business_id)
    except SupabaseRestError as exc:
        raise _storage_error(exc, "summary") from exc
    active_obligations = sum(_eligible_on(obligation, date.today()) for obligation in obligations)
    return WorkflowSummary(
        business_id=business_id,
        obligations_count=active_obligations,
        tasks_count=len(tasks),
        tasks_done=sum(task.status == "done" for task in tasks),
        source_status="ready" if active_obligations else "empty",
    )
