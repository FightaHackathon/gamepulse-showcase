"""Backward-compatible import helpers for GamePulse signal snapshots.

The original module name is retained because scripts and older callers import
it, but validation is now handled by the generic versioned snapshot layer.
"""

from __future__ import annotations

from pathlib import Path

from gamepulse.providers.snapshot import import_snapshot, normalize_snapshot


def validate_snapshot(payload: object) -> dict:
    """Validate legacy or schema-v2 snapshots and return the original object."""

    normalize_snapshot(payload)
    if not isinstance(payload, dict):
        raise ValueError("GamePulse snapshot must be a JSON object")
    return payload


__all__ = ["import_snapshot", "validate_snapshot", "Path"]
