"""v1.24.10 regression: DNA scale, role coverage, FC27-only styles, live PS+ eligibility."""
from __future__ import annotations
import os, sys, tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ["LOCALAPPDATA"] = tempfile.mkdtemp(prefix="fc27ae_v12410_model_")

from fc27_academy.aptitude import aptitude_score
from fc27_academy.existing_career_bootstrap import bootstrap_existing_player
from fc27_academy.bridge_service import OUTFIELD
from fc27_academy import playstyle_development_planner as planner
from fc27_academy.playstyle_acquisition_control import _fit
from fc27_academy.role_sync import _BASE
from fc27_academy.role_progression_evidence import ROLE_GROUPS, ROLE_GROUP_ATTRS, role_training_signal
from fc27_academy.newgen_playstyle_enrichment import _candidate_styles
from fc27_academy.playstyle_sync import PLAYSTYLE1, PLAYSTYLE2_GK

# 1. Aptitude scale: multipliers map onto the 0..100 scores the formulas expect.
assert aptitude_score(1.0) == 50.0 and aptitude_score(1.35) == 100.0 and aptitude_score(0.65) == 0.0
assert aptitude_score(None) == 50.0 and aptitude_score(72) == 72.0

w = {a: 55 for a in OUTFIELD}; w.update(acceleration=88, sprintspeed=90, dribbling=80, agility=84, balance=80, ballcontrol=78,
                                         standingtackle=25, slidingtackle=22, defensiveawareness=25, interceptions=24, strength=45)
_, dna = bootstrap_existing_player({"playerid": 500000, "preferredposition1": 27, "attributes": w}, "x")
player = {"playerid": 500000, "engine": {"football_dna": dna}, "game": {"preferredposition1": 27, "attributes": w, "overallrating": 70, "potential": 80}}
gains = {}
for style in ("Rapid", "Block"):
    pl = {"playerid": 500000, "engine": {"football_dna": dna}, "game": dict(player["game"])}
    attrs = planner.RULES[style]["attributes"]
    planner.update_from_evidence(pl, {"attribute_changes": {a: 2 for a in attrs}}, checkpoint_id="c1")
    gains[style] = pl["engine"]["playstyle_progress"][style] / (2 * len(attrs))
assert gains["Rapid"] > gains["Block"] * 1.25, gains          # pace-strong winger learns Rapid faster than Block
_, dna_fit_rapid, *_ = _fit(player, "Rapid"); _, dna_fit_block, *_ = _fit(player, "Block")
assert dna_fit_rapid > 80 and dna_fit_block < 30, (dna_fit_rapid, dna_fit_block)
print(f"DNA: winger gains per point Rapid {gains['Rapid']:.2f} vs Block {gains['Block']:.2f}; acquisition DNA fit {dna_fit_rapid:.0f} vs {dna_fit_block:.0f}: PASS")

# Population pace from native growth is unchanged on average (rates rescaled).
neutral = 2.5 * (0.70 + 50 / 150) * planner.NORMAL_PROGRESS_RATE
old_flat = 2.5 * (0.70 + 1.0 / 150) * 1.35
assert abs(neutral / old_flat - 1.0) < 0.02, (neutral, old_flat)
print(f"DNA: neutral-aptitude pace per attribute point {neutral:.3f} vs v1.24.09 flat {old_flat:.3f}: PASS")

# 2. Every FC27 role has evidence groups and every group resolves to attributes.
names = {v.split(" ", 1)[1] for v in _BASE.values()}
assert not (names - set(ROLE_GROUPS)), names - set(ROLE_GROUPS)
assert all(g in ROLE_GROUP_ATTRS for gs in ROLE_GROUPS.values() for g in gs)
before = {a: 60 for a in OUTFIELD}; after = dict(before); after.update(dribbling=63, agility=63, balance=63, curve=63, ballcontrol=63)
assert role_training_signal("False Winger", before, after) > 0
print("Roles: all 52 FC27 roles have evidence groups; flair resolves to attributes: PASS")

# 3. Newgen starting styles only come from FC27's PlayStyle bitfields.
for pos in (0, 5, 14, 25, 27):
    g = {"preferredposition1": pos, "attributes": {a: 70 for a in OUTFIELD + ("gkdiving", "gkhandling", "gkkicking", "gkpositioning", "gkreflexes")}}
    from fc27_academy.position_attributes import FC27_POSITION_IDS
    rows = _candidate_styles({"engine": {"football_dna": dna}}, g, [FC27_POSITION_IDS[pos]])
    allowed = PLAYSTYLE2_GK if pos == 0 else PLAYSTYLE1
    assert rows and all(r[2] in allowed for r in rows), (pos, [r[2] for r in rows if r[2] not in allowed])
print("Newgen: candidate starting styles are restricted to FC27 bitfield styles: PASS")

# 4. v1.24.21: PS+ eligibility is locked at adoption; the multiplier only affects new players.
import json
from fc27_academy import runtime_config
from fc27_academy.playstyle_lifetime import ensure_policy
cfg = runtime_config.SETTINGS_PATH; cfg.parent.mkdir(parents=True, exist_ok=True)
def set_mult(m):
    cfg.write_text(json.dumps({"development": {"playstyle_plus_eligibility_multiplier": m}})); runtime_config.load_runtime_settings(force=True)
def population(start):
    return [{"playerid": start + i, "engine": {}, "game": {"overallrating": 75, "potential": 85, "birthdate": i, "nationality": 1}} for i in range(2000)]
set_mult(1.0)
pop = population(470000)
base = sum(ensure_policy(p)["plus_eligible"] for p in pop)
set_mult(3.0)
existing = sum(ensure_policy(p)["plus_eligible"] for p in pop)
newcomers = sum(ensure_policy(p)["plus_eligible"] for p in population(480000))
assert existing == base, (base, existing)
assert newcomers > base * 2, (base, newcomers)
set_mult(1.0)
print(f"Lifetime: PS+ eligibility locked at adoption ({base} stay {existing} at 3x); new players use the new rate ({newcomers}/2000): PASS")
