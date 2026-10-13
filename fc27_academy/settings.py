from fc27_academy.fsutil import replace_retry
import copy
import json
import os
from pathlib import Path

from .paths import CONFIG_ROOT, PROJECT_ROOT

ROOT = PROJECT_ROOT


def _merge(a, b):
    out = copy.deepcopy(a)
    for k, v in b.items():
        out[k] = _merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else copy.deepcopy(v)
    return out


def validate(settings):
    errors = []
    development = settings.get("development", {})
    production = settings.get("production", {})
    notifications = settings.get("notifications", {})

    debug_mode = bool(production.get("debug_stress_mode", False))
    speed_max = 100.0 if debug_mode else 10.0
    for key in ("playstyle_progression_speed", "playstyle_plus_progression_speed", "role_progression_speed"):
        if not 0.10 <= development.get(key, 1.0) <= speed_max:
            errors.append(f"{key} 0.10..{speed_max:g}")
    if not 0.0 <= development.get("playstyle_plus_eligibility_multiplier", 1.0) <= 5.0:
        errors.append("PS+ eligibility multiplier 0..5")

    if not 0 <= production.get("normal_playstyle_cooldown_days", 120) <= 365:
        errors.append("normal cooldown 0..365")
    if not 0 <= production.get("playstyle_plus_cooldown_days", 180) <= 720:
        errors.append("plus cooldown 0..720")
    if not 0 <= production.get("role_upgrade_cooldown_days", 120) <= 365:
        errors.append("role cooldown 0..365")
    nlo, plo = (10, 10) if debug_mode else (50, 100)
    if not nlo <= production.get("normal_playstyle_threshold", 100.0) <= 200:
        errors.append(f"normal threshold {nlo}..200")
    if not plo <= production.get("playstyle_plus_threshold", 180.0) <= 360:
        errors.append(f"plus threshold {plo}..360")
    if production.get("playstyle_plus_threshold", 180.0) < production.get("normal_playstyle_threshold", 100.0):
        errors.append("PlayStyle+ threshold must be >= PlayStyle threshold")

    debug = bool(production.get("debug_stress_mode", False))
    throughput_cap = 512 if debug else 64
    newgen_cap = 500 if debug else 50
    if not 0 <= production.get("newgen_enrichment_per_checkpoint", 4) <= newgen_cap:
        errors.append(f"newgen throughput 0..{newgen_cap}")
    if not 4 <= production.get("max_total_changes_per_checkpoint", 12) <= throughput_cap:
        errors.append(f"overall production writes 4..{throughput_cap}")
    if not 0 <= production.get("max_normal_playstyles_per_checkpoint", 6) <= throughput_cap:
        errors.append(f"PlayStyle throughput 0..{throughput_cap}")
    if not 0 <= production.get("max_playstyle_plus_per_checkpoint", 3) <= throughput_cap:
        errors.append(f"PlayStyle+ throughput 0..{throughput_cap}")
    if not 0 <= production.get("max_role_transactions_per_checkpoint", 3) <= throughput_cap:
        errors.append(f"Role throughput 0..{throughput_cap}")

    decline = settings.get("decline", {})
    if not 0.10 <= float(decline.get("decline_speed", 1.0)) <= speed_max:
        errors.append(f"decline speed 0.10..{speed_max:g}")
    if not 3 <= int(notifications.get("popup_seconds", 6)) <= 20:
        errors.append("notification popup duration 3..20 seconds")
    return errors


class Settings:
    def __init__(self, path=None, base_path=None):
        self.path = Path(path) if path else CONFIG_ROOT / "academy_settings.json"
        self.base_path = Path(base_path) if base_path else None
        self.defaults = json.loads((ROOT / "data" / "academy_settings.default.json").read_text(encoding="utf-8"))
        self.data = copy.deepcopy(self.defaults)
        if self.base_path and self.base_path.exists():
            self.data = _merge(self.data, json.loads(self.base_path.read_text(encoding="utf-8")))
        if self.path.exists():
            self.data = _merge(self.data, json.loads(self.path.read_text(encoding="utf-8")))

    def set(self, section, key, value):
        self.update_many([(section, key, value)])

    def update_many(self, changes):
        candidate = copy.deepcopy(self.data)
        for section, key, value in changes:
            candidate.setdefault(section, {})[key] = value
        errors = validate(candidate)
        if errors:
            raise ValueError("; ".join(errors))
        self.data = candidate

    def save(self):
        errors = validate(self.data)
        if errors:
            raise ValueError("; ".join(errors))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps(self.data, indent=2), encoding="utf-8")
        replace_retry(tmp, self.path)
