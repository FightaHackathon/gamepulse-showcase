from __future__ import annotations

import csv
import json
from contextlib import contextmanager
from io import TextIOWrapper
from pathlib import Path
from typing import Iterator
from zipfile import ZipFile


@contextmanager
def open_zip_csv(archive_path: Path, member_name: str) -> Iterator[csv.DictReader]:
    """Yield a UTF-8 CSV reader for one member of a ZIP archive."""
    with ZipFile(archive_path) as archive:
        with archive.open(member_name) as binary_file:
            with TextIOWrapper(binary_file, encoding="utf-8-sig", newline="") as text_file:
                reader = csv.DictReader(text_file)
                # The downloaded catalogue has a known one-column header typo:
                # rows contain separate Discount and DLC count values, while the
                # header contains the merged name ``DiscountDLC count``. Repair
                # only that exact schema before exposing rows to transformations.
                if reader.fieldnames and "DiscountDLC count" in reader.fieldnames:
                    repaired = []
                    for field in reader.fieldnames:
                        if field == "DiscountDLC count":
                            repaired.extend(["Discount", "DLC count"])
                        else:
                            repaired.append(field)
                    reader.fieldnames = repaired
                yield reader


def parse_delimited_values(value: str | None) -> list[str]:
    """Parse comma-delimited or JSON-list values into unique, ordered strings."""
    if not value:
        return []
    candidate = value.strip()
    if candidate.startswith("[") and candidate.endswith("]"):
        try:
            decoded = json.loads(candidate.replace("'", '"'))
        except json.JSONDecodeError:
            decoded = None
        if isinstance(decoded, list):
            values = [str(item).strip() for item in decoded]
        else:
            values = candidate.split(",")
    else:
        values = candidate.split(",")
    return list(dict.fromkeys(item.strip() for item in values if item.strip()))


def optional_int(value: str | int | None) -> int | None:
    if value is None or str(value).strip() == "":
        return None
    try:
        return int(float(str(value).replace(",", "").strip()))
    except ValueError:
        return None


def optional_float(value: str | float | None) -> float | None:
    if value is None or str(value).strip() == "":
        return None
    try:
        return float(str(value).replace(",", "").strip())
    except ValueError:
        return None


def parse_bool(value: str | bool | None) -> bool | None:
    if value is None or str(value).strip() == "":
        return None
    if isinstance(value, bool):
        return value
    normalized = value.strip().lower()
    if normalized in {"true", "1", "yes"}:
        return True
    if normalized in {"false", "0", "no"}:
        return False
    return None
