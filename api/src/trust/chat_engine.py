from __future__ import annotations

import json
import re
from datetime import UTC, date, datetime, timedelta
from typing import Any
from urllib.parse import urlparse

from fastapi import HTTPException

from src.compliance.applicability import Outcome, evaluate_rule
from src.contracts.chat import (
    ChatRequest,
    ChatResponse,
    EscalationGuidance,
    SourceCitation,
    VerifiedClaim,
)
from src.integrations.supabase_rest import SupabaseRestClient, SupabaseRestError
from src.llm.llm_client import agent_generate_with_sources
from src.retrieval.retriever import retrieve_sources
from src.routes.workflow import (
    PROFILE_VERSION,
    STATE_NAMES,
    _coverage_for,
    _load_business,
    _load_profile,
    _profile_context,
)


LEGAL_TERMS = {
    "act", "law", "legal", "licence", "license", "registration", "compliance",
    "penalty", "notice", "statute", "rule", "regulation", "filing", "mca",
    "fssai", "labour", "employee", "contract", "incorporate", "company registration",
    "procedure", "permission", "approval", "eligibility", "exemption", "statutory",
    "rera", "rbi", "sebi", "epfo", "esic",
}
TAX_TERMS = {
    "tax", "gst", "gstr", "income tax", "tds", "return", "deduction", "rate",
    "threshold", "turnover", "invoice", "cbic", "itr",
}
DOCUMENT_TERMS = {"uploaded", "my document", "this document", "pdf", "notice says", "agreement says"}
STOPWORDS = {
    "what", "when", "where", "which", "with", "from", "that", "this", "have", "does",
    "your", "about", "into", "their", "will", "shall", "must", "india", "business",
}
NUMBER_TOKEN = re.compile(r"(?:₹|rs\.?\s*)?\d[\d,]*(?:\.\d+)?%?", re.IGNORECASE)


def classify_mode(query: str, has_documents: bool = False, use_business_context: bool = False) -> str:
    normalized = " ".join(query.casefold().split())
    if use_business_context and any(term in normalized for term in TAX_TERMS | LEGAL_TERMS):
        return "reviewed_compliance"
    if has_documents:
        return "user_document_analysis"
    return "general_business_guidance"


def _context_value(value: Any) -> str:
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value)


def _business_context_text(business: dict[str, Any] | None, profile: dict[str, Any] | None) -> str:
    """Create a bounded, user-visible business profile context for Gemini."""
    if not business:
        return ""
    metadata = business.get("metadata") or {}
    fields = [
        ("Business name", business.get("legal_name")),
        ("Entity type", business.get("entity_type")),
        ("Industry", business.get("industry")),
        ("Industry code", business.get("industry_code")),
        ("Primary state or jurisdiction", business.get("state_code")),
        ("Operating status", business.get("status")),
        ("Description", metadata.get("description")),
    ]
    if profile:
        fields.extend([
            ("Confirmed regulated activities", profile.get("regulated_activities")),
            ("GST registration status", profile.get("gst_registration_status")),
            ("GST scheme", profile.get("gst_scheme")),
            ("Incorporation stage", profile.get("incorporation_stage")),
            ("Turnover band", profile.get("turnover_band")),
            ("Employee count band", profile.get("employee_count_band")),
            ("Physical establishment", profile.get("has_physical_establishment")),
            ("Operating states", profile.get("operating_state_codes")),
            ("Additional profile answers", profile.get("answers")),
        ])
    lines = [f"{label}: {_context_value(value)}" for label, value in fields if value not in (None, "", [], {})]
    return "\n".join(lines)[:6000]


def _looks_like_legal_output(answer: str) -> bool:
    normalized = " ".join(answer.casefold().split())
    risky_terms = TAX_TERMS | LEGAL_TERMS | {"section", "notification", "circular", "mandatory", "required to"}
    has_risky_term = any(re.search(rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])", normalized) for term in risky_terms)
    has_numeric_rule = bool(NUMBER_TOKEN.search(answer) and any(re.search(rf"\b{term}\b", normalized) for term in {"day", "month", "crore", "lakh", "fine", "fee"}))
    return has_risky_term or has_numeric_rule


def _query_terms(value: str) -> set[str]:
    return {
        token for token in re.findall(r"[a-z0-9][a-z0-9-]{2,}", value.casefold())
        if token not in STOPWORDS
    }


def _authoritative_https(url: str | None) -> bool:
    if not url:
        return False
    parsed = urlparse(url)
    host = (parsed.hostname or "").casefold()
    return parsed.scheme == "https" and any(
        host == suffix or host.endswith(f".{suffix}")
        for suffix in ("gov.in", "nic.in", "org.in")
    )


def _numeric_claim_is_supported(statement: str, passage: str) -> bool:
    claimed = {token.casefold().replace(" ", "") for token in NUMBER_TOKEN.findall(statement)}
    supported = {token.casefold().replace(" ", "") for token in NUMBER_TOKEN.findall(passage)}
    return claimed.issubset(supported)


def _source_is_fresh(value: str | datetime | None, now: datetime | None = None, max_age_days: int = 90) -> bool:
    if not value:
        return False
    try:
        checked = value if isinstance(value, datetime) else datetime.fromisoformat(value.replace("Z", "+00:00"))
        if checked.tzinfo is None:
            checked = checked.replace(tzinfo=UTC)
    except (TypeError, ValueError):
        return False
    current = now or datetime.now(UTC)
    return checked <= current and checked >= current - timedelta(days=max_age_days)


def _date_window_active(starts: str | None, ends: str | None, as_of: date) -> bool:
    try:
        start_date = date.fromisoformat(starts) if starts else None
        end_date = date.fromisoformat(ends) if ends else None
    except (TypeError, ValueError):
        return False
    return bool(start_date and start_date <= as_of and (end_date is None or end_date >= as_of))


def _normalize_excerpt(value: str) -> str:
    return " ".join(value.casefold().split())


def _claim_matches_query(row: dict[str, Any], terms: set[str]) -> int:
    """Return deterministic lexical relevance; zero means do not retrieve."""
    searchable = " ".join([
        row.get("claim_key", ""), row.get("statement_en", ""),
        " ".join(row.get("search_terms") or []),
    ])
    searchable_terms = _query_terms(searchable)
    overlap = terms & searchable_terms
    exact_phrases = sum(1 for phrase in (row.get("search_terms") or []) if _query_terms(phrase).issubset(terms))
    return len(overlap) * 3 + exact_phrases


def _conflicting_claim_ids(rows: list[dict[str, Any]]) -> set[str]:
    """Fail closed when simultaneously applicable active claims disagree."""
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        scope = (
            row.get("claim_key", ""), row.get("jurisdiction", "").casefold(),
            repr(row.get("applicability_rule")),
        )
        grouped.setdefault(repr(scope), []).append(row)
    conflicts: set[str] = set()
    for group in grouped.values():
        values = {repr(row.get("claim_value")) for row in group}
        if len(values) > 1:
            conflicts.update(row["id"] for row in group)
    return conflicts


def _applicability_reason(context: dict[str, Any], rule: dict[str, Any]) -> list[str]:
    reasons: list[str] = []

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
        value = context.get(field)
        if field.startswith("answers."):
            value = context.get("answers", {}).get(field.removeprefix("answers."))
        labels = {
            "industry_code": "Primary industry",
            "entity_type": "Entity type",
            "regulated_activities": "Confirmed activities",
            "gst_registration_status": "GST status",
            "has_physical_establishment": "Physical establishment",
            "employee_count_band": "Workforce band",
            "turnover_band": "Turnover band",
        }
        rendered = ", ".join(value) if isinstance(value, list) else str(value)
        reasons.append(f"{labels.get(field, field.replace('_', ' ').title())}: {rendered}")

    visit(rule)
    return reasons[:12]


async def _load_reviewed_evidence(
    client: SupabaseRestClient,
    query: str,
    business: dict[str, Any],
    profile: dict[str, Any] | None,
    as_of: date,
) -> tuple[list[VerifiedClaim], list[SourceCitation], list[str]]:
    context = _profile_context(business, profile)
    rows = await client.request(
        "GET",
        "reviewed_claims",
        params={
            "select": "id,claim_key,claim_type,statement_en,support_excerpt,claim_value,search_terms,risk_level,required_reviewer_role,required_approvals,source_passage_id,applicability_version,applicability_rule,effective_from,effective_to,revalidate_by,jurisdiction,lifecycle,reviewer_roles,approval_count,published_at",
            "lifecycle": "eq.published",
            "current": "eq.true",
            "effective_from": f"lte.{as_of.isoformat()}",
            "revalidate_by": f"gte.{as_of.isoformat()}",
            "limit": 250,
        },
    )
    state_name = STATE_NAMES.get((business.get("state_code") or "").upper(), business.get("state_code") or "")
    allowed_jurisdictions = {"india", "central", "all-india", state_name.casefold()}
    terms = _query_terms(query)
    candidates: list[tuple[int, dict[str, Any], list[str]]] = []
    unknown: set[str] = set()
    for row in rows:
        if (row.get("jurisdiction") or "").casefold() not in allowed_jurisdictions:
            continue
        effective_to = row.get("effective_to")
        if effective_to and date.fromisoformat(effective_to) < as_of:
            continue
        if row.get("applicability_version") != PROFILE_VERSION or not row.get("applicability_rule"):
            continue
        try:
            outcome = evaluate_rule(row["applicability_rule"], context)
        except ValueError:
            continue
        if outcome.outcome == Outcome.UNKNOWN:
            unknown.update(outcome.unknown_fields)
            continue
        if outcome.outcome != Outcome.APPLICABLE:
            continue
        score = _claim_matches_query(row, terms)
        if score:
            candidates.append((score, row, _applicability_reason(context, row["applicability_rule"])))
    candidates.sort(key=lambda item: (-item[0], item[1]["id"]))
    candidates = candidates[:8]
    if not candidates:
        return [], [], sorted(unknown)

    passage_ids = [row["source_passage_id"] for _, row, _ in candidates]
    passages = await client.request(
        "GET", "source_passages",
        params={"select": "id,source_version_id,anchor,page_number,passage_text", "id": f"in.({','.join(passage_ids)})"},
    )
    passage_by_id = {row["id"]: row for row in passages}
    version_ids = sorted({row["source_version_id"] for row in passages})
    versions = await client.request(
        "GET", "source_versions",
        params={"select": "id,source_document_id,publication_date,effective_from,effective_to,last_checked_at,content_hash,fetch_status,review_status", "id": f"in.({','.join(version_ids)})"},
    )
    version_by_id = {row["id"]: row for row in versions}
    document_ids = sorted({row["source_document_id"] for row in versions})
    documents = await client.request(
        "GET", "source_documents",
        params={"select": "id,title,authority_name,canonical_url,source_tier,active", "id": f"in.({','.join(document_ids)})"},
    )
    document_by_id = {row["id"]: row for row in documents}

    try:
        open_conflicts = await client.request(
            "GET", "claim_conflicts",
            params={"select": "claim_id,conflicting_claim_id", "resolution_status": "eq.open", "limit": 500},
        )
    except SupabaseRestError:
        # A partially deployed contradiction registry cannot support a verified
        # answer. Returning no claims is safer than silently bypassing it.
        return [], [], sorted(unknown | {"active contradiction registry"})
    conflicted_ids = {value for conflict in open_conflicts for value in (conflict["claim_id"], conflict["conflicting_claim_id"])}
    conflicted_ids.update(_conflicting_claim_ids([row for _, row, _ in candidates]))

    verified_pairs: list[tuple[int, str, VerifiedClaim, SourceCitation]] = []
    for _, row, reasons in candidates:
        passage = passage_by_id.get(row["source_passage_id"])
        version = version_by_id.get(passage.get("source_version_id")) if passage else None
        document = document_by_id.get(version.get("source_document_id")) if version else None
        if row["id"] in conflicted_ids or not passage or not version or not document:
            continue
        if (
            version.get("fetch_status") != "healthy"
            or version.get("review_status") != "approved"
            or not _source_is_fresh(
                version.get("last_checked_at"),
                max_age_days=2 if row.get("risk_level") == "critical" or row.get("claim_type") in {"deadline", "rate", "threshold", "penalty", "eligibility"} else 90,
            )
            or not _date_window_active(version.get("effective_from"), version.get("effective_to"), as_of)
            or not document.get("active")
        ):
            continue
        required_approvals = max(
            row.get("required_approvals") or 1,
            2 if row.get("risk_level") in {"high", "critical"} or row.get("claim_type") in {"deadline", "rate", "threshold", "penalty", "eligibility"} else 1,
        )
        if (row.get("approval_count") or 0) < required_approvals or row.get("required_reviewer_role") not in (row.get("reviewer_roles") or []):
            continue
        if not _authoritative_https(document.get("canonical_url")):
            continue
        if not _numeric_claim_is_supported(row["statement_en"], passage["passage_text"]):
            continue
        support_excerpt = _normalize_excerpt(row.get("support_excerpt") or "")
        if not support_excerpt or support_excerpt not in _normalize_excerpt(passage["passage_text"]):
            continue
        evidence_id = passage["id"]
        statement = row["statement_en"]
        verified_claim = VerifiedClaim(
            claim_id=row["id"], statement=statement, evidence_ids=[evidence_id],
            applicability=reasons, risk_level=row["risk_level"], claim_type=row.get("claim_type"),
        )
        citation = SourceCitation(
            evidence_id=evidence_id, source_kind="official", source_id=document["id"],
            source_version_id=version["id"], title=document["title"], authority=document["authority_name"],
            url=document["canonical_url"], anchor=passage.get("anchor"), page_number=passage.get("page_number"),
            snippet=" ".join(row["support_excerpt"].split())[:1200], source_tier=document["source_tier"],
            publication_date=version.get("publication_date"),
            effective_from=version.get("effective_from"), effective_to=version.get("effective_to"),
            last_checked_at=version.get("last_checked_at"), content_hash=version.get("content_hash"),
            reviewed_at=row.get("published_at"), approval_count=row.get("approval_count"),
            reviewer_roles=row.get("reviewer_roles") or [],
        )
        verified_pairs.append((document["source_tier"], row["claim_key"], verified_claim, citation))

    # When multiple sources support the same canonical claim, display only the
    # highest-priority source family (lowest tier number). A conflicting value
    # has already caused every member of the group to fail closed above.
    selected: dict[str, tuple[int, VerifiedClaim, SourceCitation]] = {}
    for tier, claim_key, claim, citation in verified_pairs:
        current = selected.get(claim_key)
        if current is None or tier < current[0]:
            selected[claim_key] = (tier, claim, citation)
    claims = [item[1] for item in selected.values()]
    citations = [item[2] for item in selected.values()]
    return claims, citations, sorted(unknown)


def _document_citations(sources) -> list[SourceCitation]:
    return [
        SourceCitation(
            source_kind="user_document", document_id=source.document_id,
            file_name=(source.file_name or "Uploaded document")[:255], page_number=source.page_number,
            snippet=" ".join(source.content.split())[:1200], score=source.score,
        )
        for source in sources if source.document_id
    ]


def _reviewed_context_text(claims: list[VerifiedClaim], citations: list[SourceCitation]) -> str:
    """Format reviewed claims for Gemini without turning them into instructions."""
    citations_by_evidence = {citation.evidence_id: citation for citation in citations}
    sections: list[str] = []
    for index, claim in enumerate(claims, start=1):
        citation = citations_by_evidence.get(claim.evidence_ids[0])
        source_line = ""
        if citation:
            source_line = f"\nSource: {citation.title or citation.authority or 'Reviewed official source'}"
            if citation.anchor:
                source_line += f" ({citation.anchor})"
            source_line += f"\nSupport excerpt: {citation.snippet}"
        sections.append(
            f"[reviewed_claim_{index}]\n"
            f"Statement: {claim.statement}\n"
            f"Applicability: {', '.join(claim.applicability) or 'Confirmed for the selected profile'}"
            f"{source_line}"
        )
    return "\n\n".join(sections)[:10000]


def _document_official_conflicts(sources, claims: list[VerifiedClaim]) -> list[str]:
    """Identify explicit numeric disagreement without treating private text as law."""
    official_numbers = {
        token.casefold().replace(" ", "")
        for claim in claims for token in NUMBER_TOKEN.findall(claim.statement)
    }
    if not official_numbers:
        return []
    document_numbers = {
        token.casefold().replace(" ", "")
        for source in sources for token in NUMBER_TOKEN.findall(source.content)
    }
    if document_numbers and document_numbers != official_numbers:
        return [
            "An uploaded document contains a date, amount, rate, or threshold that differs from the active reviewed official claim. The official claim takes precedence; inspect both sources before acting."
        ]
    return []


def _escalation(agent_type: str, missing: list[str]) -> EscalationGuidance:
    role = "CA" if agent_type == "Tax Agent" else "lawyer"
    return EscalationGuidance(
        recommended_role=role,
        reason="The active reviewed catalog does not contain enough evidence to support a personalised answer.",
        briefing=["Confirm the exact business activity and entity type.", *[f"Confirm: {item}" for item in missing[:6]]],
    )


async def build_chat_response(
    req: ChatRequest,
    user_id: str,
    access_token: str,
    request_id: str | None = None,
) -> ChatResponse:
    as_of = req.as_of or date.today()
    client = SupabaseRestClient(access_token)
    business = None
    profile = None
    coverage: dict[str, Any] = {}
    selected_business_id = req.business_id if req.use_business_context else None
    if req.use_business_context and selected_business_id:
        business = await _load_business(client, selected_business_id)
        profile = await _load_profile(client, selected_business_id)
        industry_code = _profile_context(business, profile)["industry_code"]
        coverage_rows = await client.request(
            "GET", "compliance_catalog_coverage",
            params={"select": "industry_code,jurisdiction,status,notes", "industry_code": f"eq.{industry_code}", "jurisdiction": "eq.India", "limit": 1},
        )
        coverage_cells = await client.request(
            "GET", "compliance_coverage_cells",
            params={"select": "jurisdiction,industry_code,module_code,activity_code,status,notes,reviewed_at", "industry_code": f"eq.{industry_code}", "limit": 250},
        )
        coverage = _coverage_for(business, coverage_rows[0] if coverage_rows else None, coverage_cells)

    business_context_text = _business_context_text(business, profile) if business else ""
    sources = (
        retrieve_sources(req.query, user_id, selected_business_id)
        if req.use_document_context
        else []
    )
    mode = classify_mode(
        req.query,
        has_documents=bool(sources),
        use_business_context=bool(business),
    )
    normalized = req.query.casefold()
    agent_type = "Tax Agent" if any(term in normalized for term in TAX_TERMS) else "Legal Agent" if any(term in normalized for term in LEGAL_TERMS) else "General Agent"

    claims: list[VerifiedClaim] = []
    official_citations: list[SourceCitation] = []
    missing: list[str] = []
    official_context_text = ""
    if mode == "reviewed_compliance" and business:
        try:
            claims, citations, missing = await _load_reviewed_evidence(client, req.query, business, profile, as_of)
        except SupabaseRestError:
            claims, citations, missing = [], [], ["reviewed source catalog availability"]
        official_citations = citations
        official_context_text = _reviewed_context_text(claims, official_citations)
        if not claims:
            # A missing reviewed claim should reduce verification status, not
            # prevent Gemini from answering the user's broader question.
            mode = "user_document_analysis" if sources else "general_business_guidance"

    result = agent_generate_with_sources(
        req.query,
        agent_type,
        user_id=user_id,
        business_id=selected_business_id,
        history=req.history,
        sources=sources,
        business_context_text=business_context_text,
        official_context_text=official_context_text,
    )

    document_citations = _document_citations(sources)
    all_citations = [*official_citations, *document_citations]
    context_used: list[str] = []
    assumptions: list[str] = []
    if business:
        context_used.append("business")
        assumptions.append("The selected business profile was used as user-provided context, not as official legal authority.")
    if sources:
        context_used.append("documents")
        assumptions.append("Selected uploaded documents are private reference material and do not establish current law.")
    elif req.use_document_context:
        assumptions.append("No relevant uploaded document was found, so this answer was generated independently.")
    if not context_used:
        assumptions.append("Answered independently without business or uploaded-document context.")
    if not claims and missing:
        assumptions.append("The reviewed catalog did not provide a verified claim for this question; current specifics should be checked against an official source.")

    if claims:
        return ChatResponse(
            answer=result.answer,
            answer_mode="reviewed_compliance",
            evidence_status="verified",
            claims=claims,
            citations=all_citations,
            context_used=context_used,
            assumptions=assumptions,
            missing_inputs=missing,
            conflicts=_document_official_conflicts(sources, claims),
            coverage=coverage,
            effective_date=as_of,
            profile_version=(profile or {}).get("profile_version", PROFILE_VERSION),
            agent_type=agent_type,
            grounding=result.grounding,
            request_id=request_id,
        )

    if sources:
        return ChatResponse(
            answer=result.answer,
            answer_mode="user_document_analysis",
            evidence_status="partially_supported",
            citations=all_citations,
            context_used=context_used,
            assumptions=assumptions,
            missing_inputs=missing,
            coverage=coverage,
            effective_date=as_of,
            profile_version=(profile or {}).get("profile_version"),
            agent_type=agent_type,
            grounding=result.grounding,
            request_id=request_id,
        )

    return ChatResponse(
        answer=result.answer,
        answer_mode="general_business_guidance",
        evidence_status="general_guidance",
        citations=all_citations,
        context_used=context_used,
        assumptions=assumptions,
        missing_inputs=missing,
        coverage=coverage,
        effective_date=as_of,
        profile_version=(profile or {}).get("profile_version"),
        agent_type=agent_type,
        grounding=result.grounding,
        request_id=request_id,
    )
