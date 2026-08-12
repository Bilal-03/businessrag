#!/usr/bin/env python3
"""Validate reviewed obligation catalog rows before a Supabase import."""

from __future__ import annotations

import csv
import sys
from datetime import date
from pathlib import Path
from urllib.parse import urlparse


REQUIRED = {
    "jurisdiction",
    "title",
    "description",
    "source_url",
    "source_version",
    "effective_from",
    "effective_to",
    "published",
}


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
            if not all(values.values()):
                errors.append(f"line {line}: all catalog fields are required (use false, not blank, for unpublished)")
                continue
            parsed = urlparse(values["source_url"])
            if parsed.scheme != "https" or not parsed.netloc:
                errors.append(f"line {line}: source_url must be an HTTPS URL")
            dates = []
            for field in ("effective_from", "effective_to"):
                try:
                    dates.append(date.fromisoformat(values[field]))
                except ValueError:
                    errors.append(f"line {line}: {field} must be ISO YYYY-MM-DD")
                    dates.append(None)
            if dates[0] and dates[1] and dates[1] < dates[0]:
                errors.append(f"line {line}: effective_to precedes effective_from")
            if values["published"].lower() not in {"true", "false"}:
                errors.append(f"line {line}: published must be true or false")
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
