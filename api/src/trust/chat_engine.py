from __future__ import annotations

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
from src.llm.llm_client import agent_generate_with_sources, generate_from_retrieved_sources
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


def classify_mode(query: str, has_documents: bool) -> str:
    normalized = " ".join(query.casefold().split())
    # Current-law questions always use the reviewed official catalog first.
    # Mentioning an uploaded PDF never promotes private evidence to law.
    if any(term in normalized for term in TAX_TERMS | LEGAL_TERMS):
        return "reviewed_compliance"
    if has_documents:
        return "user_document_analysis"
    return "general_business_guidance"


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
    language: str = "en",
) -> tuple[list[VerifiedClaim], list[SourceCitation], list[str]]:
    context = _profile_context(business, profile)
    rows = await client.request(
        "GET",
        "reviewed_claims",
        params={
            "select": "id,claim_key,claim_type,statement_en,statement_hi,support_excerpt,claim_value,search_terms,risk_level,required_reviewer_role,required_approvals,source_passage_id,applicability_version,applicability_rule,effective_from,effective_to,revalidate_by,jurisdiction,lifecycle,reviewer_roles,approval_count,published_at",
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
        explanation_hi = None
        language_status = "reviewed"
        if language == "hi":
            if row.get("statement_hi") and "bilingual_reviewer" in (row.get("reviewer_roles") or []):
                explanation_hi = row["statement_hi"]
            else:
                language_status = "english_only"
        verified_claim = VerifiedClaim(
            claim_id=row["id"], statement=statement, evidence_ids=[evidence_id],
            applicability=reasons, risk_level=row["risk_level"], claim_type=row.get("claim_type"), language_status=language_status,
            statutory_text_en=row["statement_en"], explanation_hi=explanation_hi,
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
    if req.business_id:
        business = await _load_business(client, req.business_id)
        profile = await _load_profile(client, req.business_id)
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

    explicit_document_request = any(term in req.query.casefold() for term in DOCUMENT_TERMS)
    preliminary_mode = classify_mode(req.query, has_documents=explicit_document_request)
    # Official legal/tax retrieval never needs the private vector index. This
    # avoids sending legal questions to third-party document retrieval before
    # the trust mode and business scope are established.
    sources = [] if preliminary_mode == "reviewed_compliance" else retrieve_sources(req.query, user_id, req.business_id)
    mode = preliminary_mode if preliminary_mode == "reviewed_compliance" else classify_mode(req.query, bool(sources))
    normalized = req.query.casefold()
    agent_type = "Tax Agent" if any(term in normalized for term in TAX_TERMS) else "Legal Agent" if mode == "reviewed_compliance" else "General Agent"

    if mode == "reviewed_compliance":
        if not business:
            return ChatResponse(
                answer="Select a business before asking for personalised legal or tax guidance. No legal conclusion has been generated.",
                answer_mode="professional_escalation", evidence_status="cannot_verify", language=req.language,
                missing_inputs=["business_id"], coverage=coverage, effective_date=as_of,
                escalation=_escalation(agent_type, ["business profile"]), agent_type=agent_type,
                grounding="insufficient", request_id=request_id,
            )
        try:
            claims, citations, missing = await _load_reviewed_evidence(client, req.query, business, profile, as_of, req.language)
        except SupabaseRestError:
            claims, citations, missing = [], [], ["reviewed source catalog availability"]
        private_sources = retrieve_sources(req.query, user_id, req.business_id) if explicit_document_request else []
        private_citations = _document_citations(private_sources)
        if not claims:
            return ChatResponse(
                answer=(
                    "I cannot verify a personalised answer from the active reviewed catalog. "
                    "No legal or tax requirement has been inferred from model memory or an uploaded document. "
                    "Complete the missing business facts, inspect the coverage limits, or use the professional briefing below."
                ),
                answer_mode="professional_escalation", evidence_status="cannot_verify", language=req.language,
                citations=private_citations, assumptions=["Uploaded documents are private evidence and do not establish current law."] if private_citations else [],
                missing_inputs=missing, coverage=coverage, effective_date=as_of,
                profile_version=(profile or {}).get("profile_version", PROFILE_VERSION),
                escalation=_escalation(agent_type, missing), agent_type=agent_type,
                grounding="insufficient", request_id=request_id,
            )
        answer_lines = ["Based only on active reviewed evidence for this business:"]
        for index, claim in enumerate(claims, 1):
            answer_lines.append(f"{index}. {claim.statement} [{index}]")
            if req.language == "hi" and claim.explanation_hi:
                answer_lines.append(f"   समीक्षित Hindi explanation: {claim.explanation_hi}")
        if req.language == "hi":
            answer_lines.insert(0, "नीचे दिए गए वैधानिक कथन समीक्षित English स्रोत-पाठ में रखे गए हैं; Hindi व्याख्या उपलब्ध न होने पर अर्थ का अनुमान नहीं लगाया गया है।")
        conflicts = _document_official_conflicts(private_sources, claims)
        return ChatResponse(
            answer="\n\n".join(answer_lines), answer_mode="reviewed_compliance", evidence_status="verified",
            language=req.language, claims=claims, citations=[*citations, *private_citations],
            assumptions=["Uploaded documents are private evidence; reviewed official claims take precedence."] if private_citations else [],
            conflicts=conflicts, coverage=coverage, effective_date=as_of,
            profile_version=(profile or {}).get("profile_version", PROFILE_VERSION), agent_type=agent_type,
            grounding="document", request_id=request_id,
        )

    if mode == "user_document_analysis":
        if not sources:
            return ChatResponse(
                answer="I could not find relevant text in your uploaded documents.",
                answer_mode="user_document_analysis", evidence_status="cannot_verify", language=req.language,
                missing_inputs=["relevant uploaded document"], coverage=coverage, effective_date=as_of,
                profile_version=(profile or {}).get("profile_version"), agent_type="General Agent",
                grounding="insufficient", request_id=request_id,
            )
        # Reuse the already owner/business-scoped retrieval result so a legal
        # phrase inside a private-document question cannot change evidence.
        answer = generate_from_retrieved_sources(req.query, "General Agent", sources, req.history)
        if _looks_like_legal_output(answer):
            return ChatResponse(
                answer="The document-analysis draft contained legal or tax conclusions that were not verified against active official claims, so that prose was suppressed.",
                answer_mode="professional_escalation", evidence_status="cannot_verify", language=req.language,
                citations=_document_citations(sources), assumptions=["Uploaded documents are private evidence and do not establish current law."],
                missing_inputs=["active reviewed official claim evidence"], coverage=coverage, effective_date=as_of,
                profile_version=(profile or {}).get("profile_version"), escalation=_escalation("lawyer", ["the exact document statement to verify"]),
                agent_type="General Agent", grounding="insufficient", request_id=request_id,
            )
        return ChatResponse(
            answer=answer, answer_mode="user_document_analysis", evidence_status="partially_supported",
            language=req.language, citations=_document_citations(sources),
            assumptions=["Uploaded documents are private evidence and do not establish current law."],
            coverage=coverage, effective_date=as_of, profile_version=(profile or {}).get("profile_version"),
            agent_type="General Agent", grounding="document", request_id=request_id,
        )

    result = agent_generate_with_sources(req.query, "General Agent", user_id=user_id, business_id=req.business_id, history=req.history)
    if _looks_like_legal_output(result.answer):
        return ChatResponse(
            answer="The generated draft contained legal, tax, filing, threshold, or deadline language that is not backed by reviewed evidence, so it was suppressed.",
            answer_mode="professional_escalation", evidence_status="cannot_verify", language=req.language,
            missing_inputs=["active reviewed claim evidence"], coverage=coverage, effective_date=as_of,
            profile_version=(profile or {}).get("profile_version"),
            escalation=_escalation("lawyer", ["the exact decision or requirement to verify"]),
            agent_type="General Agent", grounding="insufficient", request_id=request_id,
        )
    return ChatResponse(
        answer=result.answer, answer_mode="general_business_guidance", evidence_status="general_guidance",
        language=req.language, assumptions=["This is general business guidance, not a legal or tax conclusion."],
        coverage=coverage, effective_date=as_of, profile_version=(profile or {}).get("profile_version"),
        agent_type="General Agent", grounding="general", request_id=request_id,
    )
