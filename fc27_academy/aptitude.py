"""Football DNA aptitude scale conversion (v1.24.10).

DNA aptitudes are stored as relative multipliers around 1.0 (bootstrap clamps them
to 0.65..1.35). Several PlayStyle formulas were written for a 0..100 score with 50
as neutral, and read the multiplier directly, which flattened every player to the
same ~0.707 DNA factor. All consumers now convert through this helper.
"""
from __future__ import annotations

NEUTRAL_SCORE = 50.0
_SPAN = 0.35  # multiplier distance from 1.0 that maps to 0 or 100


def aptitude_score(value, default: float = NEUTRAL_SCORE) -> float:
    """Return a 0..100 aptitude score (50 = neutral) from a stored DNA value."""
    try:
        v = float(value)
    except (TypeError, ValueError):
        return float(default)
    if v != v:  # NaN
        return float(default)
    if v > 3.0:
        # Already a 0..100 score (defensive: external/legacy data).
        return max(0.0, min(100.0, v))
    return max(0.0, min(100.0, NEUTRAL_SCORE + (v - 1.0) / _SPAN * NEUTRAL_SCORE))


def aptitudes_of(player: dict) -> dict:
    dna = (player.get('engine') or {}).get('football_dna') or player.get('dna') or {}
    return dna.get('aptitudes') or dna.get('aptitude') or {}


def player_aptitude_score(player: dict, group) -> float:
    return aptitude_score(aptitudes_of(player).get(group))
