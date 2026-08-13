import pytest

from src.compliance.applicability import Outcome, evaluate_rule, validate_rule


def test_all_any_not_use_three_valued_logic():
    rule = {
        "all": [
            {"field": "industry_code", "op": "eq", "value": "technology_it"},
            {"not": {"field": "regulated_activities", "op": "contains_any", "value": ["food_handling"]}},
        ]
    }
    assert evaluate_rule(rule, {"industry_code": "technology_it", "regulated_activities": []}).outcome == Outcome.APPLICABLE
    unknown = evaluate_rule(rule, {"industry_code": "technology_it", "regulated_activities": None})
    assert unknown.outcome == Outcome.UNKNOWN
    assert unknown.unknown_fields == {"regulated_activities"}


@pytest.mark.parametrize(
    "rule",
    [
        {},
        {"any": []},
        {"field": "unknown", "op": "eq", "value": True},
        {"field": "industry_code", "op": "python", "value": "x"},
        {"field": "industry_code", "op": "in", "value": "technology_it"},
        {"field": "industry_code", "op": "eq", "value": "unknown_industry"},
        {"field": "gst_registration_status", "op": "eq", "value": "maybe"},
        {"field": "has_physical_establishment", "op": "eq", "value": "yes"},
        {"field": "regulated_activities", "op": "in", "value": ["food_handling"]},
        {"field": "turnover_band", "op": "contains_any", "value": ["over_5_crore"]},
        {"all": [{"field": "industry_code", "op": "eq", "value": "other"}], "unexpected": True},
    ],
)
def test_rule_validator_rejects_unknown_or_malformed_rules(rule):
    with pytest.raises(ValueError):
        validate_rule(rule)
