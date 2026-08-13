from __future__ import annotations

from calendar import monthrange
from datetime import date, timedelta
from typing import Any

from src.compliance.applicability import APPROVED_DATE_KEYS


class DueDateRuleError(ValueError):
    pass


def _valid_date(value: Any) -> date | None:
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def evaluate_due_date(rule: dict[str, Any] | None, date_answers: dict[str, Any], as_of: date) -> tuple[date | None, str]:
    """Evaluate only approved, deterministic calendar-day formulas."""
    if not rule:
        return None, "No reviewed due-date formula is published."
    if not isinstance(rule, dict) or set(rule) - {"type", "input_key", "days", "month", "day"}:
        raise DueDateRuleError("Malformed due-date rule")
    kind = rule.get("type")
    if kind == "days_after":
        if set(rule) != {"type", "input_key", "days"}:
            raise DueDateRuleError("days_after requires input_key and days")
        input_key = rule["input_key"]
        days = rule["days"]
        if input_key not in APPROVED_DATE_KEYS or not isinstance(days, int) or days < 0 or days > 3660:
            raise DueDateRuleError("Unsupported due-date input or offset")
        start = _valid_date(date_answers.get(input_key))
        if not start:
            return None, f"Confirm {input_key.replace('_', ' ')} to determine the deadline."
        return start + timedelta(days=days), f"Reviewed formula: {days} calendar days after confirmed {input_key.replace('_', ' ')}."
    if kind == "annual_fixed":
        if set(rule) != {"type", "month", "day"}:
            raise DueDateRuleError("annual_fixed requires month and day")
        month, day = rule["month"], rule["day"]
        if not isinstance(month, int) or not isinstance(day, int) or month not in range(1, 13):
            raise DueDateRuleError("Unsupported fixed date")
        try:
            candidate = date(as_of.year, month, day)
        except ValueError as exc:
            raise DueDateRuleError("Invalid fixed date") from exc
        if candidate < as_of:
            candidate = date(as_of.year + 1, month, min(day, monthrange(as_of.year + 1, month)[1]))
        return candidate, "Reviewed annual fixed-date formula; verify any current extension or exception in the cited source."
    raise DueDateRuleError("Unsupported due-date formula type")
