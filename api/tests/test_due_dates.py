from datetime import date

import pytest

from src.compliance.due_dates import DueDateRuleError, evaluate_due_date


def test_days_after_uses_only_confirmed_date_answer():
    rule = {"type": "days_after", "input_key": "incorporation_date", "days": 30}
    assert evaluate_due_date(rule, {}, date(2026, 8, 13))[0] is None
    due, basis = evaluate_due_date(rule, {"incorporation_date": "2026-08-01"}, date(2026, 8, 13))
    assert due == date(2026, 8, 31)
    assert "30 calendar days" in basis


def test_due_date_rule_rejects_dynamic_or_unknown_input():
    with pytest.raises(DueDateRuleError):
        evaluate_due_date({"type": "python", "code": "eval(user_input)"}, {}, date.today())
    with pytest.raises(DueDateRuleError):
        evaluate_due_date({"type": "days_after", "input_key": "made_up", "days": 1}, {}, date.today())
