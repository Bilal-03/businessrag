from datetime import date, datetime, timedelta, timezone
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
    ReminderDeliveryRead,
    ReminderDeliveryRequest,
    ReminderRead,
    ReminderUpdate,
    TaskEvidenceCreate,
    TaskEvidenceRead,
    TaskCompletionEventRead,
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


def _source_version_fresh(last_checked_at: str | datetime | None, as_of: date, max_age_days: int = 90) -> bool:
    if not last_checked_at:
        return False
    try:
        checked = last_checked_at if isinstance(last_checked_at, datetime) else datetime.fromisoformat(last_checked_at.replace("Z", "+00:00"))
        checked_date = checked.date()
    except (TypeError, ValueError):
        return False
    return checked_date <= as_of and checked_date >= as_of - timedelta(days=max_age_days)


def _authoritative_https(url: str | None) -> bool:
    if not url:
        return False
    parsed = urlparse(url)
    host = (parsed.hostname or "").casefold()
    return parsed.scheme.casefold() == "https" and any(
        host == suffix or host.endswith(f".{suffix}")
        for suffix in ("gov.in", "nic.in", "org.in")
    )


def _version_active(version: dict[str, Any], as_of: date) -> bool:
    try:
        starts = date.fromisoformat(version["effective_from"])
        ends = date.fromisoformat(version["effective_to"]) if version.get("effective_to") else None
    except (KeyError, TypeError, ValueError):
        return False
    return starts <= as_of and (ends is None or ends >= as_of)


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
            params={**base_params, "select": "id,jurisdiction,title,description,source_url,source_version,effective_from,effective_to,published,review_status,source_citation,review_owner,reviewed_at,applicability_version,applicability_rule,due_date_rule,evidence_requirements,risk_level,revalidate_by,kill_switch,primary_claim_id,metadata"},
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
    obligation_ids = [item.id for item in obligations]
    due_rows: list[dict[str, Any]] = []
    evidence_rows: list[dict[str, Any]] = []
    if obligation_ids:
        id_filter = f"in.({','.join(obligation_ids)})"
        due_rows = await client.request(
            "GET", "obligation_due_date_rules",
            params={
                "select": "id,obligation_id,formula,required_input_keys,lifecycle,revalidate_by,current,supporting_claim_id",
                "obligation_id": id_filter, "lifecycle": "eq.published", "current": "eq.true",
            },
        )
        evidence_rows = await client.request(
            "GET", "obligation_evidence_items",
            params={
                "select": "id,obligation_id,label,description,required,lifecycle,revalidate_by,current,supporting_claim_id",
                "obligation_id": id_filter, "lifecycle": "eq.published", "current": "eq.true",
            },
        )
    primary_claim_ids = [item.primary_claim_id for item in obligations if item.primary_claim_id]
    supporting_claim_ids = [row.get("supporting_claim_id") for row in due_rows + evidence_rows if row.get("supporting_claim_id")]
    claim_ids = list(dict.fromkeys(primary_claim_ids + supporting_claim_ids))
    verified_claims: dict[str, dict[str, Any]] = {}
    verified_passages: dict[str, dict[str, Any]] = {}
    verified_versions: dict[str, dict[str, Any]] = {}
    verified_documents: dict[str, dict[str, Any]] = {}
    if claim_ids:
        claim_rows = await client.request(
            "GET", "reviewed_claims",
            params={
                "select": "id,obligation_id,claim_type,claim_value,statement_en,support_excerpt,source_passage_id,lifecycle,current,kill_switch,revalidate_by,required_reviewer_role,required_approvals,reviewer_roles,approval_count,applicability_version,applicability_rule",
                "id": f"in.({','.join(claim_ids)})", "lifecycle": "eq.published", "current": "eq.true", "kill_switch": "eq.false",
            },
        )
        verified_claims = {row["id"]: row for row in claim_rows}
        passage_ids = [row["source_passage_id"] for row in claim_rows]
        if passage_ids:
            passage_rows = await client.request("GET", "source_passages", params={"select": "id,source_version_id,anchor,page_number,passage_text", "id": f"in.({','.join(passage_ids)})"})
            verified_passages = {row["id"]: row for row in passage_rows}
            version_ids = [row["source_version_id"] for row in passage_rows]
            version_rows = await client.request("GET", "source_versions", params={"select": "id,source_document_id,version_label,last_checked_at,content_hash,fetch_status,review_status,effective_from,effective_to", "id": f"in.({','.join(version_ids)})"})
            verified_versions = {row["id"]: row for row in version_rows}
            document_ids = [row["source_document_id"] for row in version_rows]
            if document_ids:
                document_rows = await client.request("GET", "source_documents", params={"select": "id,canonical_url,source_tier,authority_name,title,active", "id": f"in.({','.join(document_ids)})"})
                verified_documents = {row["id"]: row for row in document_rows}
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

    def verified_supporting_claim(claim_id: str | None, obligation_id: str, rule: dict[str, Any]) -> dict[str, Any] | None:
        claim = verified_claims.get(claim_id or "")
        passage = verified_passages.get(claim.get("source_passage_id")) if claim else None
        version = verified_versions.get(passage.get("source_version_id")) if passage else None
        document = verified_documents.get(version.get("source_document_id")) if version else None
        if not claim or claim.get("obligation_id") != obligation_id or not passage or not version or not document:
            return None
        if claim.get("applicability_version") != PROFILE_VERSION or claim.get("applicability_rule") != rule:
            return None
        required_approvals = max(
            claim.get("required_approvals") or 1,
            2 if claim.get("claim_type") in {"deadline", "rate", "threshold", "penalty", "eligibility"} else 1,
        )
        if (claim.get("approval_count") or 0) < required_approvals or claim.get("required_reviewer_role") not in (claim.get("reviewer_roles") or []):
            return None
        if claim.get("revalidate_by", "") < effective_date.isoformat() or version.get("fetch_status") != "healthy" or version.get("review_status") != "approved":
            return None
        if not document.get("active") or not _authoritative_https(document.get("canonical_url")):
            return None
        if not _source_version_fresh(version.get("last_checked_at"), effective_date) or not _version_active(version, effective_date):
            return None
        excerpt = " ".join((claim.get("support_excerpt") or "").casefold().split())
        if not excerpt or excerpt not in " ".join(passage["passage_text"].casefold().split()):
            return None
        return claim

    for obligation in obligations:
        if not _eligible_on(obligation, effective_date):
            continue
        if not _matches_jurisdiction(obligation, normalized_jurisdiction):
            continue
        primary_claim = verified_claims.get(obligation.primary_claim_id or "")
        passage = verified_passages.get(primary_claim.get("source_passage_id")) if primary_claim else None
        version = verified_versions.get(passage.get("source_version_id")) if passage else None
        document = verified_documents.get(version.get("source_document_id")) if version else None
        if not primary_claim or primary_claim.get("obligation_id") != obligation.id or not passage or not version or not document:
            continue
        if primary_claim.get("revalidate_by", "") < effective_date.isoformat() or version.get("fetch_status") != "healthy" or version.get("review_status") != "approved" or not document.get("active"):
            continue
        freshness_days = 2 if obligation.risk_level == "critical" or primary_claim.get("claim_type") in {"deadline", "rate", "threshold", "penalty", "eligibility"} else 90
        if not _authoritative_https(document.get("canonical_url")) or not _source_version_fresh(version.get("last_checked_at"), effective_date, freshness_days) or not _version_active(version, effective_date):
            continue
        excerpt = " ".join((primary_claim.get("support_excerpt") or "").casefold().split())
        if not excerpt or excerpt not in " ".join(passage["passage_text"].casefold().split()):
            continue
        required_approvals = max(
            primary_claim.get("required_approvals") or 1,
            2 if obligation.risk_level in {"high", "critical"} or primary_claim.get("claim_type") in {"deadline", "rate", "threshold", "penalty", "eligibility"} else 1,
        )
        if (primary_claim.get("approval_count") or 0) < required_approvals or primary_claim.get("required_reviewer_role") not in (primary_claim.get("reviewer_roles") or []):
            continue
        claim_rule = primary_claim.get("applicability_rule")
        if (
            obligation.applicability_version != PROFILE_VERSION
            or primary_claim.get("applicability_version") != PROFILE_VERSION
            or not obligation.applicability_rule
            or claim_rule != obligation.applicability_rule
        ):
            logger.warning("workflow_obligation_rule_rejected", extra={"event": "workflow_obligation_rule_rejected"})
            continue
        try:
            result = evaluate_rule(claim_rule, context)
        except ValueError:
            logger.warning("workflow_obligation_rule_rejected", extra={"event": "workflow_obligation_rule_rejected"})
            continue
        if result.outcome == Outcome.APPLICABLE:
            due_rule = next((row for row in due_rows if row["obligation_id"] == obligation.id), None)
            verified_due_rule = None
            if due_rule and due_rule.get("revalidate_by", "") >= effective_date.isoformat():
                supporting_claim = verified_supporting_claim(due_rule.get("supporting_claim_id"), obligation.id, claim_rule)
                if supporting_claim and supporting_claim.get("claim_type") == "deadline" and supporting_claim.get("claim_value") == due_rule.get("formula"):
                    verified_due_rule = due_rule.get("formula")
            try:
                due_date, due_basis = evaluate_due_date(verified_due_rule, context["date_answers"], effective_date)
            except DueDateRuleError:
                # Malformed or unsupported formulas fail closed exactly like an
                # invalid applicability rule.
                due_date, due_basis = None, "Published due-date formula failed validation; deadline not determined."
            verified_evidence = []
            for item in evidence_rows:
                if item["obligation_id"] != obligation.id or item.get("revalidate_by", "") < effective_date.isoformat():
                    continue
                supporting_claim = verified_supporting_claim(item.get("supporting_claim_id"), obligation.id, claim_rule)
                if (
                    not supporting_claim
                    or supporting_claim.get("claim_type") not in {"duty", "procedure"}
                    or not isinstance(supporting_claim.get("claim_value"), dict)
                    or supporting_claim["claim_value"].get("evidence_label") != item["label"]
                ):
                    continue
                verified_evidence.append({
                    "id": item["id"], "label": item["label"], "description": item.get("description"),
                    "required": item.get("required", True), "supporting_claim_id": item["supporting_claim_id"],
                })
            applicable.append(obligation.model_copy(update={
                "description": primary_claim["statement_en"],
                "source_url": document["canonical_url"],
                "source_version": version["version_label"],
                "source_citation": f"{document['title']}, {passage['anchor']}",
                "applicability_reason": _applicability_reasons(claim_rule, context),
                "due_date": due_date,
                "deadline_status": "determined" if due_date else "not_determined",
                "due_date_basis": due_basis,
                "due_date_rule": verified_due_rule,
                "evidence_requirements": verified_evidence,
                "source_version_id": version["id"], "source_tier": document["source_tier"],
                "source_last_checked_at": version["last_checked_at"], "source_content_hash": version["content_hash"],
                "reviewer_roles": primary_claim.get("reviewer_roles") or [], "approval_count": primary_claim.get("approval_count"),
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
            "select": "id,business_id,obligation_id,title,status,due_date,completed_at,created_at,updated_at,recurrence_rule,series_id,occurrence_number",
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


@router.get("/reminders/due", response_model=list[ReminderDeliveryRead])
async def due_reminders(request: Request, _user_id: str = Depends(get_current_user)):
    """Return due owner-scoped reminders without changing delivery state."""
    now = datetime.now(timezone.utc)
    try:
        client = _client(request)
        rows = await client.request(
            "GET", "reminders",
            params={
                "select": "id,title,business_id,task_id,remind_at,timezone,status,alert_offsets_days,snoozed_until",
                "status": "in.(scheduled,snoozed)",
                "remind_at": f"lte.{(now + timedelta(days=365)).isoformat()}",
                "order": "remind_at.asc", "limit": 100,
            },
        )
        reminder_ids = [row["id"] for row in rows]
        events = await client.request(
            "GET", "reminder_events",
            params={
                "select": "reminder_id,metadata", "event_type": "eq.delivered",
                "reminder_id": f"in.({','.join(reminder_ids)})" if reminder_ids else "eq.00000000-0000-0000-0000-000000000000",
                "limit": 1000,
            },
        )
    except SupabaseRestError as exc:
        raise _storage_error(exc, "due_reminders") from exc
    delivered_offsets: dict[str, set[int]] = {}
    for event in events:
        offset = (event.get("metadata") or {}).get("alert_offset_days")
        if isinstance(offset, int):
            delivered_offsets.setdefault(event["reminder_id"], set()).add(offset)
    due: list[ReminderDeliveryRead] = []
    for row in rows:
        if row["status"] == "snoozed":
            scheduled_for = datetime.fromisoformat((row.get("snoozed_until") or "").replace("Z", "+00:00")) if row.get("snoozed_until") else None
            if scheduled_for and scheduled_for <= now:
                due.append(ReminderDeliveryRead(
                    id=row["id"], title=row["title"], business_id=row["business_id"], task_id=row.get("task_id"),
                    scheduled_for=scheduled_for, timezone=row["timezone"], alert_offset_days=0,
                ))
            continue
        target = datetime.fromisoformat(row["remind_at"].replace("Z", "+00:00"))
        offsets = sorted({int(value) for value in row.get("alert_offsets_days") or []}, reverse=True)
        already_delivered = delivered_offsets.get(row["id"], set())
        candidates = [offset for offset in offsets if target - timedelta(days=offset) <= now and offset not in already_delivered]
        if not candidates:
            continue
        # If the reminder was created after an earlier alert window, skip that
        # obsolete window and deliver only the most recent elapsed alert.
        offset = min(candidates)
        due.append(ReminderDeliveryRead(
            id=row["id"], title=row["title"], business_id=row["business_id"], task_id=row.get("task_id"),
            scheduled_for=target - timedelta(days=offset), timezone=row["timezone"], alert_offset_days=offset,
        ))
    return due


@router.post("/reminders/{reminder_id}/delivered", response_model=ReminderRead)
async def mark_reminder_delivered(
    request: Request,
    reminder_id: str,
    body: ReminderDeliveryRequest,
    user_id: str = Depends(get_current_user),
):
    reminder_id = _uuid_identifier(reminder_id)
    delivered_at = body.delivered_at or datetime.now(timezone.utc)
    try:
        client = _client(request)
        reminder_rows = await client.request(
            "GET", "reminders",
            params={"select": "id,status,remind_at,alert_offsets_days", "id": f"eq.{reminder_id}", "limit": 1},
        )
        if not reminder_rows:
            raise HTTPException(status_code=404, detail="Reminder not found.")
        reminder = reminder_rows[0]
        allowed_offsets = {int(value) for value in reminder.get("alert_offsets_days") or []}
        if reminder["status"] != "snoozed" and body.alert_offset_days not in allowed_offsets:
            raise HTTPException(status_code=422, detail="The alert offset is not configured for this reminder.")
        final_alert = reminder["status"] == "snoozed" or body.alert_offset_days == min(allowed_offsets, default=0)
        rows = await client.request(
            "PATCH", "reminders", params={"id": f"eq.{reminder_id}"},
            payload={"status": "delivered" if final_alert else "scheduled", "snoozed_until": None},
        )
        if not rows:
            raise HTTPException(status_code=404, detail="Reminder not found.")
        await client.request("POST", "reminder_events", payload={
            "reminder_id": reminder_id, "owner_id": user_id, "event_type": "delivered",
            "event_at": delivered_at.isoformat(), "metadata": {"alert_offset_days": body.alert_offset_days},
        })
    except SupabaseRestError as exc:
        raise _storage_error(exc, "deliver_reminder") from exc
    return ReminderRead.model_validate(rows[0])


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


@router.get("/tasks/{task_id}/history", response_model=list[TaskCompletionEventRead])
async def task_completion_history(request: Request, task_id: str, _user_id: str = Depends(get_current_user)):
    task_id = _uuid_identifier(task_id)
    try:
        rows = await _client(request).request(
            "GET", "task_completion_events",
            params={"select": "id,task_id,from_status,to_status,changed_at", "task_id": f"eq.{task_id}", "order": "changed_at.desc"},
        )
    except SupabaseRestError as exc:
        raise _storage_error(exc, "task_history") from exc
    return [TaskCompletionEventRead.model_validate(row) for row in rows]


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
