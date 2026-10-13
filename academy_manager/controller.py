"""Controller (XInput) settings shared by the launcher, exporter and native overlay (v1.24.12).

The native overlay reads CONTROLLER_ENABLED and CONTROLLER_COMBO (an XInput button
mask) from overlay_state.txt. Triggers are analog in XInput, so LT/RT use two
pseudo-bits above the 16-bit button word; the overlay treats a trigger past half
travel as pressed.
"""
from __future__ import annotations

BUTTONS = {
    'UP': 0x0001, 'DOWN': 0x0002, 'LEFT': 0x0004, 'RIGHT': 0x0008,
    'MENU': 0x0010, 'VIEW': 0x0020, 'L3': 0x0040, 'R3': 0x0080,
    'LB': 0x0100, 'RB': 0x0200, 'A': 0x1000, 'B': 0x2000, 'X': 0x4000, 'Y': 0x8000,
    'LT': 0x10000, 'RT': 0x20000,
}
ALIASES = {'START': 'MENU', 'BACK': 'VIEW', 'SELECT': 'VIEW', 'LS': 'L3', 'RS': 'R3',
           'OPTIONS': 'MENU', 'SHARE': 'VIEW', 'L1': 'LB', 'R1': 'RB', 'L2': 'LT', 'R2': 'RT'}
# Presets chosen to be rare in FC27 menus; the game still sees the same presses.
PRESETS = ('L3+R3', 'VIEW+MENU', 'VIEW+RB', 'LB+RB+Y', 'VIEW+LT+RT')
DEFAULT_COMBO = 'L3+R3'
# Canonical display order: system buttons, shoulders, triggers, sticks, face, D-pad.
DISPLAY_ORDER = ('VIEW', 'MENU', 'LB', 'RB', 'LT', 'RT', 'L3', 'R3', 'A', 'B', 'X', 'Y', 'UP', 'DOWN', 'LEFT', 'RIGHT')


def normalize_combo(text) -> str:
    """Canonical 'A+B' form, or '' if invalid (needs 2-4 distinct known buttons)."""
    parts = []
    for raw in str(text or '').upper().replace(' ', '').replace(',', '+').split('+'):
        if not raw:
            continue
        name = ALIASES.get(raw, raw)
        if name not in BUTTONS:
            return ''
        if name not in parts:
            parts.append(name)
    if not 2 <= len(parts) <= 4:
        return ''
    return '+'.join(sorted(parts, key=DISPLAY_ORDER.index))


def combo_mask(text) -> int:
    combo = normalize_combo(text) or DEFAULT_COMBO
    mask = 0
    for name in combo.split('+'):
        mask |= BUTTONS[name]
    return mask


def settings_view(mgr: dict) -> tuple[bool, str, int]:
    enabled = bool(mgr.get('controller_enabled', True))
    combo = normalize_combo(mgr.get('controller_combo', DEFAULT_COMBO)) or DEFAULT_COMBO
    return enabled, combo, combo_mask(combo)


def controller_help_text(combo: str, enabled: bool = True) -> str:
    """One description of controller navigation, shared by the launcher and the overlay (v1.24.30)."""
    if not enabled:
        return 'Controller input is ignored by the overlay.'
    return (f'Hold {combo or DEFAULT_COMBO} with FC27 focused to open or close the overlay. Left stick moves the cursor '
            '(shown as a ring), A clicks, B goes back, right stick scrolls, LB/RB switch tabs, LT/RT switch sub-views '
            '(player details pages, event filters).')
