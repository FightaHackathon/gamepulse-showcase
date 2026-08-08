"""Presentation helpers shared by the native GamePulse desktop UI."""

from __future__ import annotations


def compact_number(value: int | float | None) -> str:
    if value is None:
        return "—"
    number = float(value)
    absolute = abs(number)
    if absolute >= 1_000_000_000:
        return f"{number / 1_000_000_000:.1f}B"
    if absolute >= 1_000_000:
        return f"{number / 1_000_000:.1f}M"
    if absolute >= 1_000:
        return f"{number / 1_000:.1f}K"
    return f"{int(number):,}" if number.is_integer() else f"{number:,.1f}"


def money(value: float | None) -> str:
    if value is None:
        return "—"
    if float(value) == 0:
        return "Free"
    return f"${float(value):,.2f}"


def percent(value: float | None) -> str:
    if value is None:
        return "—"
    return f"{float(value):.0%}"


def owner_range(low: int | None, high: int | None) -> str:
    if low is None or high is None:
        return "—"
    return f"{compact_number(low)}–{compact_number(high)}"
