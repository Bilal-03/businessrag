from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


PROFILE_VERSION = 2

INDUSTRY_LABELS = {
    "food_beverage": "Food & Beverage",
    "technology_it": "Technology/IT",
    "healthcare": "Healthcare",
    "education": "Education",
    "manufacturing": "Manufacturing",
    "retail_ecommerce": "Retail & E-Commerce",
    "consulting_services": "Consulting/Services",
    "real_estate": "Real Estate",
    "finance": "Finance",
    "other": "Other",
}
INDUSTRY_CODES_BY_LABEL = {label.casefold(): code for code, label in INDUSTRY_LABELS.items()}

ACTIVITY_LABELS = {
    "food_handling": "Handles or prepares food",
    "food_manufacturing": "Manufactures food",
    "food_storage": "Stores food commercially",
    "food_import": "Imports food",
    "food_delivery": "Delivers food",
    "saas_digital_service": "Provides SaaS or digital services",
    "personal_data_processing": "Processes personal data",
    "online_intermediary": "Operates an online intermediary or platform",
    "ecommerce_marketplace": "Operates an e-commerce marketplace",
    "clinical_establishment": "Operates a clinical establishment",
    "pharmacy": "Operates a pharmacy",
    "diagnostics": "Provides diagnostic services",
    "medical_devices": "Makes, imports, or sells medical devices",
    "school_education": "Operates a school",
    "coaching_training": "Provides coaching or training",
    "higher_education": "Provides higher education",
    "online_education": "Provides online education",
    "awards_qualifications": "Awards qualifications",
    "factory_operations": "Operates a factory",
    "hazardous_process": "Uses a hazardous process",
    "pollution_generating": "Runs an activity requiring environmental consent review",
    "physical_retail": "Operates a physical retail location",
    "packaged_goods_sale": "Sells packaged goods",
    "professional_consulting": "Provides professional consulting services",
    "real_estate_promoter": "Acts as a real-estate promoter",
    "real_estate_agent": "Acts as a real-estate agent or broker",
    "construction": "Carries out construction",
    "lending": "Provides lending",
    "payments": "Provides payment services",
    "investment_advice": "Provides investment advice",
    "insurance": "Provides insurance services",
    "pension": "Provides pension services",
}

APPROVED_PROFILE_FIELDS = {
    "industry_code",
    "entity_type",
    "business_status",
    "regulated_activities",
    "gst_registration_status",
    "gst_scheme",
    "incorporation_stage",
    "turnover_band",
    "employee_count_band",
    "has_physical_establishment",
    "premises_status",
    "uses_contractors",
    "handles_personal_data",
    "operating_state_codes",
    "operates_multiple_states",
    "imports_goods_services",
    "exports_goods_services",
}
APPROVED_ANSWER_KEYS = {
    "handles_sensitive_personal_data",
    "offers_services_to_children",
    "uses_contract_labour",
    "handles_hazardous_materials",
    "sells_prepackaged_goods",
}
APPROVED_DATE_KEYS = {
    "incorporation_date",
    "operations_start_date",
    "gst_registration_date",
    "filing_period_end",
    "financial_year_end",
    "event_date",
}
APPROVED_OPERATORS = {"eq", "neq", "in", "contains_any", "contains_all"}


QUESTION_CATALOG: dict[str, dict[str, Any]] = {
    "regulated_activities": {
        "label": "Which regulated activities does this business perform?",
        "description": "Choose all that apply. Leave all unchecked only when none apply.",
        "answer_type": "multi_select",
        "options": [{"value": value, "label": label} for value, label in ACTIVITY_LABELS.items()],
    },
    "gst_registration_status": {
        "label": "Is this business registered for GST?",
        "description": "GSTR obligations are not shown until registration is confirmed.",
        "answer_type": "single_select",
        "options": [
            {"value": "registered", "label": "Yes, registered"},
            {"value": "not_registered", "label": "No, not registered"},
            {"value": "not_applicable", "label": "Not applicable"},
        ],
    },
    "gst_scheme": {
        "label": "Which GST scheme or filing arrangement applies?",
        "description": "Choose only what is confirmed from the GST registration and current tax advice.",
        "answer_type": "single_select",
        "options": [
            {"value": "regular", "label": "Regular"}, {"value": "composition", "label": "Composition"},
            {"value": "qrmp", "label": "QRMP"}, {"value": "not_known", "label": "Not known"},
            {"value": "not_applicable", "label": "Not applicable"},
        ],
    },
    "incorporation_stage": {
        "label": "What stage is the business in?",
        "description": "Lifecycle requirements depend on whether incorporation and operations have begun.",
        "answer_type": "single_select",
        "options": [
            {"value": "pre_incorporation", "label": "Before incorporation"},
            {"value": "incorporated", "label": "Incorporated, not operating"},
            {"value": "operating", "label": "Operating"},
            {"value": "winding_down", "label": "Winding down"},
        ],
    },
    "has_physical_establishment": {
        "label": "Does this business operate a physical office, shop, or establishment?",
        "description": "This helps evaluate state establishment requirements.",
        "answer_type": "boolean",
        "options": [
            {"value": True, "label": "Yes"},
            {"value": False, "label": "No"},
        ],
    },
    "premises_status": {
        "label": "What kind of premises does the business use?",
        "description": "Premises-specific requirements remain hidden until this fact is confirmed.",
        "answer_type": "single_select",
        "options": [
            {"value": "none", "label": "No physical premises"}, {"value": "owned", "label": "Owned"},
            {"value": "leased", "label": "Leased"}, {"value": "shared", "label": "Shared"},
            {"value": "virtual", "label": "Virtual office"},
        ],
    },
    "uses_contractors": {
        "label": "Does this business engage contractors or contract workers?",
        "description": "Contract-worker requirements are not inferred from employee count.",
        "answer_type": "boolean",
        "options": [{"value": True, "label": "Yes"}, {"value": False, "label": "No"}],
    },
    "handles_personal_data": {
        "label": "Does this business process personal data?",
        "description": "Data-related requirements are evaluated only after the activity is confirmed.",
        "answer_type": "boolean",
        "options": [{"value": True, "label": "Yes"}, {"value": False, "label": "No"}],
    },
    "turnover_band": {
        "label": "What is the business's annual turnover band?",
        "description": "Use the latest completed financial year where available.",
        "answer_type": "single_select",
        "options": [
            {"value": "under_20_lakh", "label": "Under ₹20 lakh"},
            {"value": "20_lakh_to_1_crore", "label": "₹20 lakh to ₹1 crore"},
            {"value": "1_to_5_crore", "label": "₹1 crore to ₹5 crore"},
            {"value": "over_5_crore", "label": "Over ₹5 crore"},
        ],
    },
    "employee_count_band": {
        "label": "How many people does this business employ?",
        "description": "Include workers where the applicable rule requires them to be counted.",
        "answer_type": "single_select",
        "options": [
            {"value": "0", "label": "None"},
            {"value": "1_to_9", "label": "1–9"},
            {"value": "10_to_19", "label": "10–19"},
            {"value": "20_to_49", "label": "20–49"},
            {"value": "50_to_99", "label": "50–99"},
            {"value": "100_plus", "label": "100 or more"},
        ],
    },
    "operates_multiple_states": {
        "label": "Does this business operate in more than one state?",
        "description": "State obligations are evaluated only for reviewed jurisdictions.",
        "answer_type": "boolean",
        "options": [{"value": True, "label": "Yes"}, {"value": False, "label": "No"}],
    },
    "imports_goods_services": {
        "label": "Does this business import goods or services?",
        "description": "Import-related obligations remain hidden until this is confirmed.",
        "answer_type": "boolean",
        "options": [{"value": True, "label": "Yes"}, {"value": False, "label": "No"}],
    },
    "exports_goods_services": {
        "label": "Does this business export goods or services?",
        "description": "Export-related obligations remain hidden until this is confirmed.",
        "answer_type": "boolean",
        "options": [{"value": True, "label": "Yes"}, {"value": False, "label": "No"}],
    },
}

for _answer_key, _answer_label in {
    "handles_sensitive_personal_data": "Does this business handle sensitive personal data?",
    "offers_services_to_children": "Does this business offer services to children?",
    "uses_contract_labour": "Does this business use contract labour?",
    "handles_hazardous_materials": "Does this business handle hazardous materials?",
    "sells_prepackaged_goods": "Does this business sell pre-packaged goods?",
}.items():
    QUESTION_CATALOG[f"answers.{_answer_key}"] = {
        "label": _answer_label,
        "description": "This answer is requested only when a reviewed catalog rule depends on it.",
        "answer_type": "boolean",
        "options": [{"value": True, "label": "Yes"}, {"value": False, "label": "No"}],
    }


class Outcome(str, Enum):
    APPLICABLE = "applicable"
    NOT_APPLICABLE = "not_applicable"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class Evaluation:
    outcome: Outcome
    unknown_fields: frozenset[str] = frozenset()


def normalize_industry_code(code: str | None, label: str | None = None) -> str:
    normalized = (code or "").strip().casefold()
    if normalized in INDUSTRY_LABELS:
        return normalized
    return INDUSTRY_CODES_BY_LABEL.get((label or "").strip().casefold(), "other")


def _validate_condition(node: dict[str, Any]) -> None:
    field = node.get("field")
    operator = node.get("op")
    if not isinstance(field, str) or (
        field not in APPROVED_PROFILE_FIELDS
        and not (field.startswith("answers.") and field.removeprefix("answers.") in APPROVED_ANSWER_KEYS)
    ):
        raise ValueError(f"Unknown applicability field: {field!r}")
    if operator not in APPROVED_OPERATORS:
        raise ValueError(f"Unknown applicability operator: {operator!r}")
    if "value" not in node:
        raise ValueError("Applicability conditions require a value.")
    if operator in {"in", "contains_any", "contains_all"} and not isinstance(node["value"], list):
        raise ValueError(f"Operator {operator} requires a list value.")
    values = node["value"] if isinstance(node["value"], list) else [node["value"]]
    if field == "industry_code" and any(value not in INDUSTRY_LABELS for value in values):
        raise ValueError("Applicability rule contains an unknown industry code.")
    if field == "regulated_activities" and any(value not in ACTIVITY_LABELS for value in values):
        raise ValueError("Applicability rule contains an unknown regulated activity.")


def validate_rule(rule: Any) -> None:
    if not isinstance(rule, dict) or not rule:
        raise ValueError("Applicability rule must be a non-empty object.")
    keys = set(rule)
    groups = keys & {"all", "any", "not"}
    if groups:
        if len(groups) != 1 or keys != groups:
            raise ValueError("Applicability groups may contain exactly one of all, any, or not.")
        group = next(iter(groups))
        children = rule[group]
        if group == "not":
            validate_rule(children)
            return
        if not isinstance(children, list) or not children:
            raise ValueError(f"Applicability {group} group must contain at least one rule.")
        for child in children:
            validate_rule(child)
        return
    if keys != {"field", "op", "value"}:
        raise ValueError("Applicability condition must contain only field, op, and value.")
    _validate_condition(rule)


def _field_value(context: dict[str, Any], field: str) -> tuple[bool, Any]:
    if field.startswith("answers."):
        key = field.removeprefix("answers.")
        answers = context.get("answers")
        return (isinstance(answers, dict) and key in answers, answers.get(key) if isinstance(answers, dict) else None)
    return (field in context and context[field] is not None, context.get(field))


def _evaluate_condition(node: dict[str, Any], context: dict[str, Any]) -> Evaluation:
    field = node["field"]
    known, actual = _field_value(context, field)
    if not known:
        return Evaluation(Outcome.UNKNOWN, frozenset({field}))
    expected = node["value"]
    operator = node["op"]
    if operator == "eq":
        matched = actual == expected
    elif operator == "neq":
        matched = actual != expected
    elif operator == "in":
        matched = actual in expected
    elif operator == "contains_any":
        matched = isinstance(actual, list) and bool(set(actual) & set(expected))
    else:
        matched = isinstance(actual, list) and set(expected).issubset(set(actual))
    return Evaluation(Outcome.APPLICABLE if matched else Outcome.NOT_APPLICABLE)


def evaluate_rule(rule: dict[str, Any], context: dict[str, Any]) -> Evaluation:
    validate_rule(rule)
    if "all" in rule:
        results = [evaluate_rule(child, context) for child in rule["all"]]
        if any(result.outcome == Outcome.NOT_APPLICABLE for result in results):
            return Evaluation(Outcome.NOT_APPLICABLE)
        unknown = frozenset().union(*(result.unknown_fields for result in results))
        return Evaluation(Outcome.UNKNOWN, unknown) if unknown else Evaluation(Outcome.APPLICABLE)
    if "any" in rule:
        results = [evaluate_rule(child, context) for child in rule["any"]]
        if any(result.outcome == Outcome.APPLICABLE for result in results):
            return Evaluation(Outcome.APPLICABLE)
        unknown = frozenset().union(*(result.unknown_fields for result in results))
        return Evaluation(Outcome.UNKNOWN, unknown) if unknown else Evaluation(Outcome.NOT_APPLICABLE)
    if "not" in rule:
        result = evaluate_rule(rule["not"], context)
        if result.outcome == Outcome.UNKNOWN:
            return result
        return Evaluation(
            Outcome.NOT_APPLICABLE if result.outcome == Outcome.APPLICABLE else Outcome.APPLICABLE
        )
    return _evaluate_condition(rule, context)


def question_for(field: str, current_value: Any = None) -> dict[str, Any] | None:
    definition = QUESTION_CATALOG.get(field)
    if not definition:
        return None
    return {"key": field, "current_value": current_value, **definition}
