from datetime import date, datetime, timezone
from typing import Any
from urllib.parse import urlparse
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import ValidationError

from src.auth.dependencies import get_current_user
from src.compliance.applicability import (
    ACTIVITY_LABELS,
    APPROVED_ANSWER_KEYS,
    APPROVED_DATE_KEYS,
    INDUSTRY_LABELS,
    PROFILE_VERSION,
    Outcome,
    evaluate_rule,
    normalize_industry_code,
    question_for,
)
from src.compliance.due_dates import DueDateRuleError, evaluate_due_date
from src.contracts.workflow import (
    BusinessApplicabilityUpdate,
    CompliancePlanResponse,
    ComplianceProfileUpdate,
    ObligationRead,
    ReminderCreate,
    ReminderRead,
    ReminderUpdate,
    TaskEvidenceCreate,
    TaskEvidenceRead,
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


def _uuid_identifier(value: str) -> str:
    try:
        return str(UUID(value))
    except (ValueError, TypeError, AttributeError) as exc:
        raise HTTPException(status_code=422, detail="A valid business UUID is required.") from exc


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
    if operation in {"list_obligations", "get_plan", "get_profile", "list_tasks", "summary"}:
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
    if obligation.kill_switch or not obligation.revalidate_by or obligation.revalidate_by < as_of:
        return False
    return True


def _applicability_reasons(rule: dict[str, Any], context: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    labels = {
        "industry_code": "Primary industry",
        "entity_type": "Entity type",
        "business_status": "Business status",
        "regulated_activities": "Confirmed regulated activities",
        "gst_registration_status": "GST registration status",
        "turnover_band": "Turnover band",
        "employee_count_band": "Employee-count band",
        "has_physical_establishment": "Physical establishment",
        "operates_multiple_states": "Multi-state operation",
        "imports_goods_services": "Imports",
        "exports_goods_services": "Exports",
    }

    def visit(node: dict[str, Any]) -> None:
        if "all" in node or "any" in node:
            for child in node.get("all") or node.get("any") or []:
                visit(child)
            return
        if "not" in node:
            return
        field = node.get("field")
        if not field:
            return
        actual = context.get(field)
        if field.startswith("answers."):
            actual = context.get("answers", {}).get(field.removeprefix("answers."))
        rendered = ", ".join(actual) if isinstance(actual, list) else "Yes" if actual is True else "No" if actual is False else str(actual)
        reasons.append(f"{labels.get(field, field.replace('_', ' ').title())}: {rendered}")

    visit(rule)
    return reasons[:12]


def _eligible_on(obligation: ObligationRead, as_of: date) -> bool:
    return _has_review_evidence(obligation, as_of) and _active_on(obligation, as_of)


def _matches_jurisdiction(obligation: ObligationRead, normalized_jurisdiction: str | None) -> bool:
    normalized_obligation = obligation.jurisdiction.casefold()
    if not normalized_jurisdiction:
        return normalized_obligation in {"india", "central", "all-india"}
    if normalized_obligation == normalized_jurisdiction:
        return True
    return normalized_jurisdiction != "india" and normalized_obligation in {"india", "central", "all-india"}


async def _list_obligation_rows(client: SupabaseRestClient) -> list[ObligationRead]:
    base_params = {
        "published": "eq.true", "review_status": "eq.published",
        "source_citation": "not.is.null", "review_owner": "not.is.null",
        "reviewed_at": "not.is.null", "order": "effective_from.asc",
    }
    try:
        rows = await client.request(
            "GET", "obligations",
            params={**base_params, "select": "id,jurisdiction,title,description,source_url,source_version,effective_from,effective_to,published,review_status,source_citation,review_owner,reviewed_at,applicability_version,applicability_rule,due_date_rule,evidence_requirements,risk_level,revalidate_by,kill_switch,metadata"},
        )
    except SupabaseRestError as exc:
        if exc.status_code not in {400, 404}:
            raise
        # Safe rolling-deploy adapter. Legacy rows lack qualified-review
        # freshness fields and therefore remain hidden by _has_review_evidence.
        rows = await client.request(
            "GET", "obligations",
            params={**base_params, "select": "id,jurisdiction,title,description,source_url,source_version,effective_from,effective_to,published,review_status,source_citation,review_owner,reviewed_at,applicability_version,applicability_rule,metadata"},
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


STATE_NAMES = {
    "AP": "Andhra Pradesh",
    "DL": "Delhi",
    "GJ": "Gujarat",
    "KA": "Karnataka",
    "KL": "Kerala",
    "MH": "Maharashtra",
    "TN": "Tamil Nadu",
    "TG": "Telangana",
    "UP": "Uttar Pradesh",
    "WB": "West Bengal",
    "MULTI": "Other / Multi-state",
}


async def _load_business(client: SupabaseRestClient, business_id: str) -> dict[str, Any]:
    rows = await client.request(
        "GET",
        "businesses",
        params={
            "select": "id,owner_id,legal_name,entity_type,industry,industry_code,state_code,status",
            "id": f"eq.{business_id}",
            "limit": 1,
        },
    )
    if not rows:
        # RLS intentionally makes a different user's business indistinguishable
        # from a missing record.
        raise HTTPException(status_code=404, detail="Business not found.")
    return rows[0]


async def _load_profile(client: SupabaseRestClient, business_id: str) -> dict[str, Any] | None:
    rows = await client.request(
        "GET",
        "business_compliance_profiles",
        params={"select": "*", "business_id": f"eq.{business_id}", "limit": 1},
    )
    return rows[0] if rows else None


def _profile_context(business: dict[str, Any], profile: dict[str, Any] | None) -> dict[str, Any]:
    profile = profile or {}
    return {
        "industry_code": normalize_industry_code(business.get("industry_code"), business.get("industry")),
        "entity_type": business.get("entity_type"),
        "business_status": business.get("status"),
        "regulated_activities": profile.get("regulated_activities"),
        "gst_registration_status": profile.get("gst_registration_status"),
        "gst_scheme": profile.get("gst_scheme"),
        "incorporation_stage": profile.get("incorporation_stage"),
        "turnover_band": profile.get("turnover_band"),
        "employee_count_band": profile.get("employee_count_band"),
        "has_physical_establishment": profile.get("has_physical_establishment"),
        "premises_status": profile.get("premises_status"),
        "uses_contractors": profile.get("uses_contractors"),
        "handles_personal_data": profile.get("handles_personal_data"),
        "operating_state_codes": profile.get("operating_state_codes"),
        "operates_multiple_states": profile.get("operates_multiple_states"),
        "imports_goods_services": profile.get("imports_goods_services"),
        "exports_goods_services": profile.get("exports_goods_services"),
        "answers": profile.get("answers") if isinstance(profile.get("answers"), dict) else {},
        "date_answers": profile.get("date_answers") if isinstance(profile.get("date_answers"), dict) else {},
    }


def _coverage_for(
    business: dict[str, Any],
    central_coverage: dict[str, Any] | None = None,
    coverage_cells: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    industry_code = normalize_industry_code(business.get("industry_code"), business.get("industry"))
    industry_label = INDUSTRY_LABELS[industry_code]
    state_code = (business.get("state_code") or "").upper()
    state_name = STATE_NAMES.get(state_code, state_code or "Not provided")
    cells = coverage_cells or []

    def summarize(jurisdiction: str, fallback_status: str, fallback_message: str) -> tuple[str, str, list[str]]:
        matching = [cell for cell in cells if cell.get("jurisdiction") == jurisdiction]
        if not matching:
            return fallback_status, fallback_message, []
        blocked = sorted({cell["module_code"] for cell in matching if cell.get("status") in {"blocked", "in_review"}})
        approved = [cell for cell in matching if cell.get("status") in {"covered", "not_applicable"}]
        if matching and len(approved) == len(matching):
            return "available", "Every declared launch module has a qualified reviewer-approved coverage status.", []
        if approved:
            return "partial", "Some launch modules are reviewed; blocked modules are explicitly excluded from completeness.", blocked
        return "in_review", "No launch module is reviewer-approved yet; no requirement is inferred for blocked modules.", blocked

    central_status, central_message, central_blocked = summarize(
        "India",
        central_coverage.get("status", "partial") if central_coverage else "partial",
        central_coverage.get("notes") if central_coverage else f"Reviewed central records are routed for {industry_label}, but catalog coverage is not yet exhaustive.",
    )
    if state_code == "DL":
        state_status, state_message, state_blocked = summarize("Delhi", "partial", "A reviewed Delhi slice is available, but it is not a complete state-law catalog.")
    elif state_code == "MH":
        state_status, state_message, state_blocked = summarize("Maharashtra", "in_review", "Maharashtra catalog entries are still under review and remain unpublished.")
    else:
        state_status = "unsupported"
        state_message = "No complete reviewed state catalog is available for this jurisdiction; no state requirement is guessed."
        state_blocked = []
    return {
        "central": {
            "status": central_status,
            "message": central_message,
            "blocked_modules": central_blocked,
        },
        "state": {"status": state_status, "jurisdiction": state_name, "message": state_message, "blocked_modules": state_blocked},
    }


async def _build_plan(client: SupabaseRestClient, business_id: str, effective_date: date) -> CompliancePlanResponse:
    business = await _load_business(client, business_id)
    profile = await _load_profile(client, business_id)
    obligations = await _list_obligation_rows(client)
    context = _profile_context(business, profile)
    coverage_rows = await client.request(
        "GET",
        "compliance_catalog_coverage",
        params={
            "select": "industry_code,jurisdiction,status,notes",
            "industry_code": f"eq.{context['industry_code']}",
            "jurisdiction": "eq.India",
            "limit": 1,
        },
    )
    try:
        coverage_cells = await client.request(
            "GET", "compliance_coverage_cells",
            params={
                "select": "jurisdiction,industry_code,module_code,activity_code,status,notes,reviewed_at",
                "industry_code": f"eq.{context['industry_code']}", "limit": 250,
            },
        )
    except SupabaseRestError as exc:
        if exc.status_code not in {400, 404}:
            raise
        coverage_cells = []
    jurisdiction = STATE_NAMES.get((business.get("state_code") or "").upper(), business.get("state_code") or "")
    normalized_jurisdiction = jurisdiction.casefold() if jurisdiction else None
    applicable: list[ObligationRead] = []
    unknown_fields: set[str] = set()
    for obligation in obligations:
        if not _eligible_on(obligation, effective_date):
            continue
        if not _matches_jurisdiction(obligation, normalized_jurisdiction):
            continue
        if obligation.applicability_version != PROFILE_VERSION or not obligation.applicability_rule:
            logger.warning("workflow_obligation_rule_rejected", extra={"event": "workflow_obligation_rule_rejected"})
            continue
        try:
            result = evaluate_rule(obligation.applicability_rule, context)
        except ValueError:
            logger.warning("workflow_obligation_rule_rejected", extra={"event": "workflow_obligation_rule_rejected"})
            continue
        if result.outcome == Outcome.APPLICABLE:
            try:
                due_date, due_basis = evaluate_due_date(obligation.due_date_rule, context["date_answers"], effective_date)
            except DueDateRuleError:
                # Malformed or unsupported formulas fail closed exactly like an
                # invalid applicability rule.
                due_date, due_basis = None, "Published due-date formula failed validation; deadline not determined."
            applicable.append(obligation.model_copy(update={
                "applicability_reason": _applicability_reasons(obligation.applicability_rule, context),
                "due_date": due_date,
                "deadline_status": "determined" if due_date else "not_determined",
                "due_date_basis": due_basis,
            }))
        elif result.outcome == Outcome.UNKNOWN:
            unknown_fields.update(result.unknown_fields)

    questions = []
    for field in sorted(unknown_fields):
        current_value = context.get(field) if not field.startswith("answers.") else context["answers"].get(field.removeprefix("answers."))
        question = question_for(field, current_value)
        if question:
            questions.append(question)
    return CompliancePlanResponse(
        business_id=business_id,
        obligations=applicable,
        questions=questions,
        coverage=_coverage_for(business, coverage_rows[0] if coverage_rows else None, coverage_cells),
        profile_version=PROFILE_VERSION,
    )


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


async def _list_reminder_rows(client: SupabaseRestClient, business_id: str) -> list[ReminderRead]:
    rows = await client.request(
        "GET", "reminders",
        params={
            "select": "id,business_id,task_id,title,remind_at,timezone,status,alert_offsets_days,recurrence_rule,snoozed_until,created_at,updated_at",
            "business_id": f"eq.{business_id}", "order": "remind_at.asc",
        },
    )
    return [ReminderRead.model_validate(row) for row in rows]


@router.get("/plan", response_model=CompliancePlanResponse)
async def get_plan(
    request: Request,
    business_id: str = Query(...),
    as_of: date | None = None,
    _user_id: str = Depends(get_current_user),
):
    """Build a fail-closed plan from the authenticated user's stored business."""
    business_id = _uuid_identifier(business_id)
    try:
        return await _build_plan(_client(request), business_id, as_of or date.today())
    except SupabaseRestError as exc:
        raise _storage_error(exc, "get_plan") from exc


@router.get("/obligations", response_model=list[ObligationRead])
async def list_obligations(
    request: Request,
    business_id: str = Query(...),
    as_of: date | None = None,
    _user_id: str = Depends(get_current_user),
):
    """Compatibility route; unscoped jurisdiction-only requests are rejected."""
    business_id = _uuid_identifier(business_id)
    try:
        plan = await _build_plan(_client(request), business_id, as_of or date.today())
    except SupabaseRestError as exc:
        raise _storage_error(exc, "list_obligations") from exc
    return plan.obligations


@router.patch("/businesses/{business_id}/compliance-profile")
async def update_compliance_profile(
    request: Request,
    business_id: str,
    body: ComplianceProfileUpdate,
    user_id: str = Depends(get_current_user),
):
    business_id = _uuid_identifier(business_id)
    payload = body.model_dump(mode="json", exclude_unset=True)
    if not payload:
        raise HTTPException(status_code=422, detail="Provide at least one compliance profile answer.")
    activities = payload.get("regulated_activities")
    if activities is not None:
        unknown_activities = sorted(set(activities) - set(ACTIVITY_LABELS))
        if unknown_activities:
            raise HTTPException(status_code=422, detail="The compliance profile contains an unknown regulated activity.")
        payload["regulated_activities"] = sorted(set(activities))
    answers = payload.get("answers")
    if answers is not None and set(answers) - APPROVED_ANSWER_KEYS:
        raise HTTPException(status_code=422, detail="The compliance profile contains an unknown answer key.")
    if answers is not None and any(value is not None and not isinstance(value, bool) for value in answers.values()):
        raise HTTPException(status_code=422, detail="Industry-specific compliance answers must be yes or no.")
    date_answers = payload.get("date_answers")
    if date_answers is not None and set(date_answers) - APPROVED_DATE_KEYS:
        raise HTTPException(status_code=422, detail="The compliance profile contains an unknown date answer key.")
    payload["profile_version"] = PROFILE_VERSION
    try:
        client = _client(request)
        await _load_business(client, business_id)
        existing = await _load_profile(client, business_id)
        if existing and answers is not None:
            payload["answers"] = {**(existing.get("answers") or {}), **answers}
        if existing and date_answers is not None:
            payload["date_answers"] = {**(existing.get("date_answers") or {}), **date_answers}
        if existing:
            rows = await client.request(
                "PATCH",
                "business_compliance_profiles",
                params={"business_id": f"eq.{business_id}"},
                payload=payload,
            )
        else:
            rows = await client.request(
                "POST",
                "business_compliance_profiles",
                payload={"business_id": business_id, "owner_id": user_id, **payload},
            )
    except SupabaseRestError as exc:
        raise _storage_error(exc, "update_profile") from exc
    if not rows:
        raise HTTPException(status_code=404, detail="Business compliance profile not found.")
    return rows[0]


@router.patch("/businesses/{business_id}/applicability")
async def update_business_applicability(
    request: Request,
    business_id: str,
    body: BusinessApplicabilityUpdate,
    user_id: str = Depends(get_current_user),
):
    """Atomically validate the primary industry and regulated activities."""
    business_id = _uuid_identifier(business_id)
    payload = body.model_dump(mode="json", exclude_unset=True)
    if not payload:
        raise HTTPException(status_code=422, detail="Provide an industry or regulated activities.")
    activities = payload.pop("regulated_activities", None)
    if activities is not None and set(activities) - set(ACTIVITY_LABELS):
        raise HTTPException(status_code=422, detail="The business contains an unknown regulated activity.")
    try:
        client = _client(request)
        business = await _load_business(client, business_id)
        industry_code = payload.get("industry_code")
        if industry_code:
            business_rows = await client.request(
                "PATCH",
                "businesses",
                params={"id": f"eq.{business_id}"},
                payload={"industry_code": industry_code, "industry": INDUSTRY_LABELS[industry_code]},
            )
            business = business_rows[0] if business_rows else business
        profile = await _load_profile(client, business_id)
        if activities is not None:
            profile_payload = {"profile_version": PROFILE_VERSION, "regulated_activities": sorted(set(activities))}
            if profile:
                profile_rows = await client.request(
                    "PATCH",
                    "business_compliance_profiles",
                    params={"business_id": f"eq.{business_id}"},
                    payload=profile_payload,
                )
            else:
                profile_rows = await client.request(
                    "POST",
                    "business_compliance_profiles",
                    payload={"business_id": business_id, "owner_id": user_id, **profile_payload},
                )
            profile = profile_rows[0] if profile_rows else profile
    except SupabaseRestError as exc:
        raise _storage_error(exc, "update_profile") from exc
    return {"business": business, "compliance_profile": profile}


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


@router.get("/reminders", response_model=list[ReminderRead])
async def list_reminders(
    request: Request,
    business_id: str = Query(...),
    _user_id: str = Depends(get_current_user),
):
    business_id = _uuid_identifier(business_id)
    try:
        client = _client(request)
        await _load_business(client, business_id)
        return await _list_reminder_rows(client, business_id)
    except SupabaseRestError as exc:
        raise _storage_error(exc, "list_reminders") from exc


@router.post("/reminders", response_model=ReminderRead, status_code=status.HTTP_201_CREATED)
async def create_reminder(
    request: Request,
    body: ReminderCreate,
    user_id: str = Depends(get_current_user),
):
    business_id = _uuid_identifier(body.business_id)
    offsets = sorted(set(body.alert_offsets_days), reverse=True)
    if any(offset < 0 or offset > 365 for offset in offsets):
        raise HTTPException(status_code=422, detail="Reminder offsets must be between 0 and 365 days.")
    try:
        client = _client(request)
        await _load_business(client, business_id)
        payload = body.model_dump(mode="json", exclude_none=True)
        payload.update({"owner_id": user_id, "business_id": business_id, "alert_offsets_days": offsets})
        rows = await client.request("POST", "reminders", payload=payload)
        if rows:
            await client.request("POST", "reminder_events", payload={
                "reminder_id": rows[0]["id"], "owner_id": user_id, "event_type": "created",
                "metadata": {"timezone": body.timezone, "alert_offsets_days": offsets},
            })
    except SupabaseRestError as exc:
        raise _storage_error(exc, "create_reminder") from exc
    return ReminderRead.model_validate(rows[0])


@router.patch("/reminders/{reminder_id}", response_model=ReminderRead)
async def update_reminder(
    request: Request,
    reminder_id: str,
    body: ReminderUpdate,
    user_id: str = Depends(get_current_user),
):
    reminder_id = _uuid_identifier(reminder_id)
    payload = body.model_dump(mode="json", exclude_unset=True)
    if not payload:
        raise HTTPException(status_code=422, detail="Provide at least one reminder field to update.")
    if body.status == "snoozed" and not body.snoozed_until:
        raise HTTPException(status_code=422, detail="A snoozed reminder requires snoozed_until.")
    try:
        client = _client(request)
        rows = await client.request("PATCH", "reminders", params={"id": f"eq.{reminder_id}"}, payload=payload)
        if not rows:
            raise HTTPException(status_code=404, detail="Reminder not found.")
        event = "snoozed" if body.status == "snoozed" else "dismissed" if body.status == "dismissed" else "rescheduled"
        await client.request("POST", "reminder_events", payload={
            "reminder_id": reminder_id, "owner_id": user_id, "event_type": event,
            "metadata": {"status": body.status} if body.status else {},
        })
    except SupabaseRestError as exc:
        raise _storage_error(exc, "update_reminder") from exc
    return ReminderRead.model_validate(rows[0])


@router.delete("/reminders/{reminder_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_reminder(request: Request, reminder_id: str, _user_id: str = Depends(get_current_user)):
    reminder_id = _uuid_identifier(reminder_id)
    try:
        await _client(request).request("DELETE", "reminders", params={"id": f"eq.{reminder_id}"})
    except SupabaseRestError as exc:
        raise _storage_error(exc, "delete_reminder") from exc
    return None


@router.get("/tasks/{task_id}/evidence", response_model=list[TaskEvidenceRead])
async def list_task_evidence(request: Request, task_id: str, _user_id: str = Depends(get_current_user)):
    task_id = _uuid_identifier(task_id)
    try:
        rows = await _client(request).request(
            "GET", "task_evidence",
            params={"select": "id,business_id,task_id,evidence_type,title,document_id,reference_url,note,created_at", "task_id": f"eq.{task_id}", "order": "created_at.desc"},
        )
    except SupabaseRestError as exc:
        raise _storage_error(exc, "list_task_evidence") from exc
    return [TaskEvidenceRead.model_validate(row) for row in rows]


@router.post("/tasks/{task_id}/evidence", response_model=TaskEvidenceRead, status_code=status.HTTP_201_CREATED)
async def add_task_evidence(
    request: Request,
    task_id: str,
    body: TaskEvidenceCreate,
    user_id: str = Depends(get_current_user),
):
    task_id = _uuid_identifier(task_id)
    business_id = _uuid_identifier(body.business_id)
    if body.evidence_type == "document" and not body.document_id:
        raise HTTPException(status_code=422, detail="Document evidence requires document_id.")
    if body.evidence_type == "reference" and not body.reference_url:
        raise HTTPException(status_code=422, detail="Reference evidence requires an HTTPS URL.")
    if body.evidence_type == "note" and not body.note:
        raise HTTPException(status_code=422, detail="Note evidence requires note text.")
    try:
        client = _client(request)
        await _load_business(client, business_id)
        payload = body.model_dump(mode="json", exclude_none=True) | {
            "owner_id": user_id, "business_id": business_id, "task_id": task_id,
        }
        rows = await client.request("POST", "task_evidence", payload=payload)
    except SupabaseRestError as exc:
        raise _storage_error(exc, "add_task_evidence") from exc
    return TaskEvidenceRead.model_validate(rows[0])


@router.get("/summary", response_model=WorkflowSummary)
async def workflow_summary(
    request: Request,
    business_id: str = Query(..., min_length=1, max_length=120),
    _user_id: str = Depends(get_current_user),
):
    business_id = _uuid_identifier(business_id)
    try:
        client = _client(request)
        plan = await _build_plan(client, business_id, date.today())
        tasks = await _list_task_rows(client, business_id)
    except SupabaseRestError as exc:
        raise _storage_error(exc, "summary") from exc
    active_obligations = len(plan.obligations)
    return WorkflowSummary(
        business_id=business_id,
        obligations_count=active_obligations,
        tasks_count=len(tasks),
        tasks_done=sum(task.status == "done" for task in tasks),
        source_status="ready" if active_obligations else "empty",
    )
