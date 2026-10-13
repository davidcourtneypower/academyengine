"""Persistent PlayStyle lifetime policy for generated FC27 players.

Normal PlayStyles:
- every generated player receives a deterministic, quality-weighted lifetime ceiling;
- Academy Engine never adds normal PlayStyles above that personal ceiling;
- an absolute engine safety ceiling of seven normal PlayStyles is always enforced.

PlayStyle+:
- eligibility is assigned once, when the engine first adopts the player, using the
  multiplier in force at that moment; later multiplier changes only affect new players;
- only a minority of generated players are eligible for an Academy Engine PS+;
- Academy Engine may add at most one PS+ per player (native FC27 PS+ is preserved
  and counts toward that limit).
"""
from __future__ import annotations
import hashlib
from .playstyle_sync import PLAYSTYLE1, PLAYSTYLE2_GK
from .runtime_config import plus_eligibility_multiplier

def _decode(value, mapping):
    try: value=int(value or 0)
    except (TypeError,ValueError): value=0
    return {n for n,b in mapping.items() if value & b}

def current_styles(game):
    is_gk=int(game.get("preferredposition1",-1))==0
    normal=_decode(game.get("trait1"),PLAYSTYLE1); plus=_decode(game.get("icontrait1"),PLAYSTYLE1)
    if is_gk:
        normal |= _decode(game.get("trait2"),PLAYSTYLE2_GK)
        plus |= _decode(game.get("icontrait2"),PLAYSTYLE2_GK)
    return normal,plus,is_gk

POLICY_VERSION = "v1.24"
ABSOLUTE_NORMAL_CAP = 7
ENGINE_PLUS_CAP = 1

# Persistent career ceilings. These are deliberately broader than starting
# distributions: many players stop below their ceiling because they never earn
# enough development evidence, while exceptional players have room to grow.
LIFETIME_CAP_PROFILES = {
    "DEVELOPING": ((2, .42), (3, .35), (4, .18), (5, .05)),
    "PROMISING":  ((3, .35), (4, .35), (5, .20), (6, .08), (7, .02)),
    "HIGH":       ((4, .28), (5, .34), (6, .26), (7, .12)),
    "ELITE":      ((5, .25), (6, .40), (7, .35)),
}

# Only a minority may ever receive an Academy Engine PlayStyle+.
# The roll is fixed for the player's identity, so eligibility does not change
# when OVR/potential subsequently move.
PLUS_ELIGIBILITY_PROBABILITY = {
    "DEVELOPING": .02,
    "PROMISING": .06,
    "HIGH": .15,
    "ELITE": .30,
}


def quality_score(game: dict) -> float:
    return .60 * float(game.get("overallrating") or 0) + .40 * float(game.get("potential") or 0)


def quality_band(quality: float) -> str:
    if quality < 60: return "DEVELOPING"
    if quality < 70: return "PROMISING"
    if quality < 80: return "HIGH"
    return "ELITE"


def _identity_seed(player: dict) -> str:
    g = player.get("game") or {}
    return f"{int(player.get('playerid',0))}|{g.get('birthdate')}|{g.get('nationality')}"


def _u01(player: dict, purpose: str) -> float:
    b = f"FC27AE_LIFETIME_V124|{_identity_seed(player)}|{purpose}".encode("utf-8")
    return int.from_bytes(hashlib.sha256(b).digest()[:8], "big") / 2**64


def _sample_cap(player: dict, band: str) -> int:
    roll = _u01(player, "NORMAL_CAP")
    acc = 0.0
    for cap, prob in LIFETIME_CAP_PROFILES[band]:
        acc += prob
        if roll < acc:
            return int(cap)
    return int(LIFETIME_CAP_PROFILES[band][-1][0])


def ensure_policy(player: dict) -> dict:
    """Assign (or return) immutable lifetime policy for one generated identity."""
    eng = player.setdefault("engine", {})
    g = player.get("game") or {}
    normal, plus, _ = current_styles(g)

    # Identity replacement rebuilds the player entry, so an existing policy can
    # safely be treated as immutable for this player identity.
    if eng.get("playstyle_lifetime_policy_version") == POLICY_VERSION:
        # v1.24.36: a cap can shrink to 0 through PlayStyle decline, so 0 is a real value.
        _nc = eng.get("playstyle_lifetime_normal_cap")
        ncap = ABSOLUTE_NORMAL_CAP if _nc is None else int(_nc)
        band_now = str(eng.get("playstyle_lifetime_quality_band") or quality_band(quality_score(g)))
        # v1.24.21: PS+ eligibility is locked when the player is first adopted. Changing
        # the eligibility multiplier only affects players the engine finds afterwards
        # (v1.24.10-v1.24.20 re-scored every tracked player live).
        return {
            "normal_cap": ncap,
            "plus_eligible": bool(eng.get("playstyle_plus_lifetime_eligible", False)),
            "plus_cap": int(eng.get("playstyle_plus_lifetime_cap", ENGINE_PLUS_CAP) or ENGINE_PLUS_CAP),
            "quality": float(eng.get("playstyle_lifetime_quality", quality_score(g)) or 0),
            "band": str(eng.get("playstyle_lifetime_quality_band", quality_band(quality_score(g)))),
        }

    quality = quality_score(g)
    band = quality_band(quality)
    sampled = _sample_cap(player, band)
    # Never delete FC27-native/current PlayStyles, but Academy Engine will never
    # add beyond seven. If FC27 somehow already has >7, the cap remains 7 and all
    # further Academy Engine normal additions are held.
    normal_cap = min(ABSOLUTE_NORMAL_CAP, max(len(normal), sampled))
    plus_roll = _u01(player, "PLUS_ELIGIBLE")
    effective_plus_probability = min(0.95, PLUS_ELIGIBILITY_PROBABILITY[band] * plus_eligibility_multiplier())
    plus_eligible = bool(normal_cap >= 4 and plus_roll < effective_plus_probability)

    eng["playstyle_lifetime_policy_version"] = POLICY_VERSION
    eng["playstyle_lifetime_quality"] = round(quality, 3)
    eng["playstyle_lifetime_quality_band"] = band
    eng["playstyle_lifetime_normal_cap"] = int(normal_cap)
    eng["playstyle_lifetime_normal_cap_roll"] = round(_u01(player, "NORMAL_CAP"), 6)
    eng["playstyle_plus_lifetime_eligible"] = plus_eligible
    eng["playstyle_plus_lifetime_eligibility_roll"] = round(plus_roll, 6)
    eng["playstyle_plus_lifetime_cap"] = ENGINE_PLUS_CAP
    eng["playstyle_plus_lifetime_probability"] = effective_plus_probability
    return {"normal_cap": normal_cap, "plus_eligible": plus_eligible, "plus_cap": ENGINE_PLUS_CAP, "quality": quality, "band": band}


def normal_cap(player: dict) -> int:
    return min(ABSOLUTE_NORMAL_CAP, max(0, int(ensure_policy(player)["normal_cap"])))


def plus_eligible(player: dict) -> bool:
    return bool(ensure_policy(player)["plus_eligible"])


def normal_addition_slots(player: dict) -> int:
    normal, _, _ = current_styles(player.get("game") or {})
    return max(0, min(ABSOLUTE_NORMAL_CAP, normal_cap(player)) - len(normal))


def plus_addition_slots(player: dict) -> int:
    _, plus, _ = current_styles(player.get("game") or {})
    if not plus_eligible(player): return 0
    return max(0, ENGINE_PLUS_CAP - len(plus))


def audit_world(world: dict) -> dict:
    cap_hist = {str(i): 0 for i in range(0, ABSOLUTE_NORMAL_CAP + 1)}
    eligible = 0; observed = 0; at_cap = 0; plus_at_cap = 0
    bands = {k: 0 for k in LIFETIME_CAP_PROFILES}
    for p in (world.get("players") or {}).values():
        if not p.get("observed_this_checkpoint", False): continue
        observed += 1
        pol = ensure_policy(p); cap = int(pol["normal_cap"])
        cap_hist[str(cap)] = cap_hist.get(str(cap), 0) + 1
        bands[pol["band"]] = bands.get(pol["band"], 0) + 1
        normal, plus, _ = current_styles(p.get("game") or {})
        if len(normal) >= min(ABSOLUTE_NORMAL_CAP, cap): at_cap += 1
        if pol["plus_eligible"]: eligible += 1
        if len(plus) >= ENGINE_PLUS_CAP: plus_at_cap += 1
    return {
        "policy_version": POLICY_VERSION,
        "observed": observed,
        "absolute_normal_cap": ABSOLUTE_NORMAL_CAP,
        "normal_cap_hist": cap_hist,
        "quality_band_hist": bands,
        "normal_at_cap": at_cap,
        "plus_eligible": eligible,
        "plus_eligible_pct": round(100.0 * eligible / observed, 1) if observed else 0.0,
        "plus_cap": ENGINE_PLUS_CAP,
        "plus_at_cap": plus_at_cap,
    }
