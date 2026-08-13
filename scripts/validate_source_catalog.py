#!/usr/bin/env python3
"""Validate reviewed obligation catalog rows before a Supabase import."""

from __future__ import annotations

import csv
import json
import sys
from datetime import UTC, date, datetime
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "api"))

from src.compliance.applicability import validate_rule  # noqa: E402


REQUIRED = {
    "jurisdiction",
    "title",
    "description",
    "source_url",
    "source_version",
    "source_citation",
    "effective_from",
    "effective_to",
    "review_status",
    "review_owner",
    "reviewed_at",
    "published",
    "applicability_version",
    "applicability_rule",
}
OPTIONAL = {"effective_to", "reviewed_at"}
REVIEW_STATES = {"draft", "reviewed", "published"}


def _parse_date(value: str) -> date | None:
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _parse_timestamp(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else None
    except ValueError:
        return None


def main(path: str) -> int:
    source = Path(path)
    if not source.exists():
        print(f"catalog not found: {source}", file=sys.stderr)
        return 2
    errors: list[str] = []
    keys: set[tuple[str, str, str]] = set()
    with source.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if set(reader.fieldnames or []) != REQUIRED:
            errors.append(f"header must contain exactly: {', '.join(sorted(REQUIRED))}")
        for line, row in enumerate(reader, start=2):
            values = {key: (row.get(key) or "").strip() for key in REQUIRED}
            missing = [key for key in REQUIRED - OPTIONAL if not values[key]]
            if missing:
                errors.append(f"line {line}: missing required fields: {', '.join(sorted(missing))}")

            parsed = urlparse(values["source_url"])
            hostname = (parsed.hostname or "").casefold()
            if parsed.scheme != "https" or not parsed.netloc:
                errors.append(f"line {line}: source_url must be an HTTPS URL")
            elif not (hostname.endswith(".gov.in") or hostname.endswith(".nic.in") or hostname.endswith(".org.in")):
                errors.append(f"line {line}: source_url must use an official .gov.in, .nic.in, or .org.in host")

            effective_from = _parse_date(values["effective_from"]) if values["effective_from"] else None
            effective_to = _parse_date(values["effective_to"]) if values["effective_to"] else None
            if values["effective_from"] and effective_from is None:
                errors.append(f"line {line}: effective_from must be ISO YYYY-MM-DD")
            if values["effective_to"] and effective_to is None:
                errors.append(f"line {line}: effective_to must be ISO YYYY-MM-DD")
            if effective_from and effective_to and effective_to < effective_from:
                errors.append(f"line {line}: effective_to precedes effective_from")

            review_status = values["review_status"].lower()
            if review_status not in REVIEW_STATES:
                errors.append(f"line {line}: review_status must be draft, reviewed, or published")
            if values["published"].lower() not in {"true", "false"}:
                errors.append(f"line {line}: published must be true or false")
            elif (values["published"].lower() == "true") != (review_status == "published"):
                errors.append(f"line {line}: published must be true exactly when review_status is published")

            if values["applicability_version"] not in {"1", "2"}:
                errors.append(f"line {line}: applicability_version must be 1 or 2")
            try:
                rule = json.loads(values["applicability_rule"])
                validate_rule(rule)
            except (json.JSONDecodeError, ValueError) as exc:
                errors.append(f"line {line}: invalid applicability_rule: {exc}")

            if not values["source_citation"]:
                errors.append(f"line {line}: source_citation is required")
            if not values["review_owner"]:
                errors.append(f"line {line}: review_owner is required")

            if review_status == "draft" and values["reviewed_at"]:
                errors.append(f"line {line}: draft rows must not have reviewed_at")
            if review_status in {"reviewed", "published"}:
                if not values["reviewed_at"]:
                    errors.append(f"line {line}: reviewed and published rows require reviewed_at")
                elif _parse_timestamp(values["reviewed_at"]) is None:
                    errors.append(f"line {line}: reviewed_at must be an ISO timestamp")
                elif _parse_timestamp(values["reviewed_at"]) > datetime.now(UTC):
                    errors.append(f"line {line}: reviewed_at cannot be in the future")
                if not effective_from:
                    errors.append(f"line {line}: reviewed and published rows require effective_from")
            elif values["reviewed_at"] and _parse_timestamp(values["reviewed_at"]) is None:
                errors.append(f"line {line}: reviewed_at must be an ISO timestamp")

            if review_status == "published" and effective_to and effective_to < date.today():
                errors.append(f"line {line}: published row is already outside its effective window")

            key = (values["jurisdiction"].casefold(), values["title"].casefold(), values["source_version"])
            if key in keys:
                errors.append(f"line {line}: duplicate jurisdiction/title/source_version")
            keys.add(key)

    if errors:
        print("Source catalog validation failed:")
        print("\n".join(f"- {error}" for error in errors))
        return 1
    print(f"Source catalog valid: {len(keys)} rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1] if len(sys.argv) > 1 else "supabase/seed/obligations.csv"))
