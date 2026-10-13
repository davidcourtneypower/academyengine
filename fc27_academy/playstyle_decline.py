"""PlayStyle decline with age (v1.24.36).

FC27 ages attributes but never removes PlayStyles. Once a generated player's personal
decline phase has started, a PlayStyle whose key attributes have fallen below a floor and
well below the player's own peak builds "decline progress"; at 100% it is lost (a
PlayStyle+ first drops to the normal PlayStyle). Progress eases back when the attributes
recover, faster for younger players.

State lives in ``player['engine']['decline']``:

    start_age, band, roll          personal decline start (30-40), fixed once decided
    peak_ovr, peaks{attr: value}   highest values seen since the engine began tracking
    active, active_since_age       decline phase started
    active_checkpoints             development checkpoints credited since it started
    days_since_loss                days since the last loss (spacing between losses)
    progress{style: 0-100}         decline progress per owned PlayStyle
    status{style: {...}}           last evaluation, for the overlay
    ready{style, kind}             a loss ready to be written (LOSS / PLUS_DOWNGRADE)
    lost[{style, kind, age, ...}]  history of losses (also blocks re-earning)

Nothing here writes to FC27; ``ready`` is picked up by the live writer.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .playstyle_development_planner import current_styles

RULES = json.loads((Path(__file__).parent / 'data' / 'playstyle_generation_rules.json').read_text(encoding='utf-8'))

# Chance that decline starts at each birthday, for a player whose decline has not
# started yet. At 40 every remaining player starts.
HAZARD = {30: .08, 31: .11, 32: .15, 33: .20, 34: .26, 35: .33, 36: .42, 37: .52, 38: .64, 39: .80, 40: 1.0}
FIRST_AGE, LAST_AGE = 30, 40
# Peak-OVR bands: better players tend to start later (their yearly chance is scaled down).
BANDS = (('ELITE', 85, .50), ('STRONG', 80, .75), ('REGULAR', 0, 1.0))

FLOOR = 70.0                 # key attributes must average below this ...
MIN_DROP = 4.0               # ... and be at least this far below the player's peak
REACQUIRE_LEVEL = 78.0       # a lost PlayStyle can be earned again only from here
BASE_RATE = 100.0 / 120.0    # progress per day of sustained decline at normal speed (~4 months)
GAP_DAYS = 60                # minimum days between two losses for one player
MIN_ACTIVE_CHECKPOINTS = 3   # grace: development checkpoints after the phase starts

# Attributes judged for a loss where they differ from the acquisition rules.
LOSS_ATTRS = {
    'Jockey': ('agility', 'balance'),
    'Far Reach': ('gkdiving', 'gkreflexes'),
    'Deflector': ('gkreflexes', 'gkdiving'),
    'Rush Out': ('gkreflexes', 'gkdiving'),        # GK snapshots carry GK attributes only (no pace)
    'Far Throw': ('gkkicking',),
    'Footwork': ('gkkicking', 'gkreflexes'),
    'Cross Claimer': ('gkhandling', 'gkpositioning'),
    'Quick Reflexes': ('gkreflexes',),
}

# A goalkeeper's snapshot carries goalkeeper attributes only, so his outfield PlayStyles
# are judged on the nearest goalkeeper attribute (distribution for passing styles);
# those with no sensible equivalent do not decline for goalkeepers.
GK_OUTFIELD_LOSS_ATTRS = {s: ('gkkicking',) for s in ('Long Ball Pass', 'Pinged Pass', 'Incisive Pass', 'Tiki Taka', 'Whipped Pass')}

STATUS_DECLINING, STATUS_RECOVERING, STATUS_PENDING, STATUS_LOST, STATUS_HOLDING = 0, 1, 2, 3, 4


def loss_attributes(style: str) -> tuple:
    return tuple(LOSS_ATTRS.get(style) or (RULES.get(style) or {}).get('attributes') or ())


def band_for(peak_ovr) -> tuple[str, float]:
    try:
        v = float(peak_ovr or 0)
    except (TypeError, ValueError):
        v = 0.0
    for name, lo, factor in BANDS:
        if v >= lo:
            return name, factor
    return 'REGULAR', 1.0


def start_age_for(roll: float, factor: float) -> int:
    """Age at which decline starts for a uniform roll in [0, 1)."""
    survive = 1.0
    for age in range(FIRST_AGE, LAST_AGE + 1):
        p = 1.0 if age == LAST_AGE else min(1.0, HAZARD[age] * factor)
        survive_next = survive * (1.0 - p)
        if roll >= survive_next:      # inverse CDF: started by this birthday
            return age
        survive = survive_next
    return LAST_AGE


def _roll(seed: str, game: dict) -> float:
    key = f"FC27AE_DECLINE|{seed}|{game.get('playerid')}|{game.get('birthdate')}|{game.get('nationality')}"
    return int.from_bytes(hashlib.sha256(key.encode('utf-8')).digest()[:8], 'big') / float(2 ** 64)


def _num(v, default=None):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _mean(vals):
    vals = [v for v in vals if v is not None]
    return sum(vals) / len(vals) if vals else None


def age_factor(age) -> float:
    """Decline builds faster the older the player is (x1.0 to x2.2)."""
    return min(2.2, 1.0 + 0.2 * max(0, int(age or 0) - 31))


def recovery_factor(age) -> float:
    """Recovery eases back progress; slower the older the player is."""
    return max(0.15, 0.8 - 0.1 * max(0, int(age or 0) - 30))


def reacquire_blocked(player: dict, style: str) -> bool:
    """A lost PlayStyle cannot be earned again unless its attributes clearly recover."""
    d = ((player.get('engine') or {}).get('decline') or {})
    gone = [x for x in d.get('lost') or [] if x.get('style') == style and
            (x.get('kind') == 'LOSS' or (x.get('kind') == 'PLUS_DOWNGRADE' and x.get('kept_normal') is False))]
    if not gone:
        return False
    attrs = (player.get('game') or {}).get('attributes') or {}
    now = _mean([_num(attrs.get(a)) for a in loss_attributes(style)])
    return now is None or now < REACQUIRE_LEVEL


PEAK_TRACK_AGE = 26
_PEAK_ATTRS = None


def _peak_attrs() -> frozenset:
    global _PEAK_ATTRS
    if _PEAK_ATTRS is None:
        names = set()
        for style, rule in RULES.items():
            names.update(rule.get('attributes') or ())
        for attrs in LOSS_ATTRS.values():
            names.update(attrs)
        _PEAK_ATTRS = frozenset(names)
    return _PEAK_ATTRS


def _track_peaks(d: dict, game: dict):
    """Peaks are kept from 26 (the career-best years) for PlayStyle-relevant attributes only,
    which keeps the world file small."""
    ovr = _num(game.get('overallrating'))
    if ovr is not None and ovr > float(d.get('peak_ovr') or 0):
        d['peak_ovr'] = int(ovr)
    peaks = d.setdefault('peaks', {})
    wanted = _peak_attrs()
    for a, v in (game.get('attributes') or {}).items():
        if a not in wanted:
            continue
        fv = _num(v)
        if fv is not None and fv > float(peaks.get(a, -1)):
            peaks[a] = int(fv)


def evaluate_style(d: dict, game: dict, style: str) -> dict:
    attrs = loss_attributes(style)
    if str(game.get('preferredposition1')) == '0' and not all(a.startswith('gk') for a in attrs):
        attrs = GK_OUTFIELD_LOSS_ATTRS.get(style, ())
    cur = game.get('attributes') or {}
    now = _mean([_num(cur.get(a)) for a in attrs])
    peak = _mean([_num((d.get('peaks') or {}).get(a)) for a in attrs])
    if now is None or peak is None:
        return {'attrs': list(attrs), 'now': None, 'peak': None, 'declining': False}
    declining = now < FLOOR and (peak - now) >= MIN_DROP
    return {'attrs': list(attrs), 'now': round(now, 1), 'peak': round(peak, 1), 'declining': declining,
            'values': {a: cur.get(a) for a in attrs}, 'peaks': {a: (d.get('peaks') or {}).get(a) for a in attrs}}


def update_player(player: dict, *, seed: str, credit: bool, days: int, normal_on: bool, plus_on: bool, speed: float = 1.0,
                  checkpoint_id=None) -> dict:
    """Advance one observed player's decline. Returns a small summary."""
    out = {'active': False, 'ready': None}
    eng = player.get('engine') or {}
    if isinstance(eng.get('decline'), dict):
        eng['decline']['ready'] = None               # recomputed below; never left over from an earlier checkpoint
    if player.get('retired'):
        return out
    game = player.get('game') or {}
    age = _num(game.get('age'))
    if age is None or age < PEAK_TRACK_AGE:
        return out                                   # nothing to record yet (keeps young players' records small)
    eng = player.setdefault('engine', {})
    d = eng.setdefault('decline', {})
    _track_peaks(d, game)
    if not (normal_on or plus_on):
        return out                                   # feature off: progress frozen, nothing ready
    if age < FIRST_AGE:
        return out
    age = int(age)
    if 'start_age' not in d:
        band, factor = band_for(d.get('peak_ovr') or game.get('overallrating'))
        roll = _roll(seed, game)
        d.update(start_age=start_age_for(roll, factor), band=band, roll=round(roll, 6))
    if age < int(d['start_age']):
        return out
    if not d.get('active'):
        # Shown as "since age N": his personal start age (also when the switch was turned on later).
        d.update(active=True, active_since_age=int(d['start_age']), active_checkpoints=0, days_since_loss=GAP_DAYS,
                 first_active_checkpoint=checkpoint_id)
    out['active'] = True
    normal, plus, _ = current_styles(game)
    owned = set(normal) | set(plus)
    prog = d.setdefault('progress', {})
    for s in list(prog):
        if s not in owned:
            prog.pop(s, None)
    status = {}
    for s in sorted(owned):
        is_plus = s in plus
        if (is_plus and not plus_on) or (not is_plus and not normal_on):
            continue
        ev = evaluate_style(d, game, s)
        status[s] = {**ev, 'plus': is_plus}
    d['status'] = status
    if credit and player.get('lifecycle') == 'CLUB' and days > 0:
        d['active_checkpoints'] = int(d.get('active_checkpoints', 0) or 0) + 1
        d['days_since_loss'] = int(d.get('days_since_loss', 0) or 0) + int(days)
        for s, ev in status.items():
            old = float(prog.get(s, 0.0) or 0.0)
            if ev['declining']:
                sev = 1.0 + min(1.0, max(0.0, (FLOOR - ev['now']) / 10.0))
                new = min(100.0, old + days * BASE_RATE * age_factor(age) * sev * max(0.0, float(speed)))
            else:
                new = max(0.0, old - days * BASE_RATE * recovery_factor(age) * max(0.0, float(speed)))
            prog[s] = round(new, 3)
    # A loss becomes ready after the grace period and the spacing between losses.
    d['ready'] = None
    if int(d.get('active_checkpoints', 0) or 0) >= MIN_ACTIVE_CHECKPOINTS and int(d.get('days_since_loss', 0) or 0) >= GAP_DAYS:
        due = [(float(prog.get(s, 0) or 0), s) for s in status if float(prog.get(s, 0) or 0) >= 100.0]
        if due:
            due.sort(key=lambda x: (-int(status[x[1]]['plus']), -x[0], x[1]))   # PlayStyle+ first
            s = due[0][1]
            d['ready'] = {'style': s, 'kind': 'PLUS_DOWNGRADE' if status[s]['plus'] else 'LOSS'}
    out['ready'] = d['ready']
    return out


def update_world(world: dict, *, credit: bool, days: int, settings: dict, checkpoint_id=None) -> dict:
    normal_on = bool(settings.get('playstyle_loss_enabled'))
    plus_on = bool(settings.get('playstyle_plus_loss_enabled'))
    speed = float(settings.get('decline_speed', 1.0) or 1.0)
    seed = str(world.get('career_uid') or world.get('save_uid') or 'career')
    res = {'active': 0, 'ready': 0, 'enabled': normal_on or plus_on}
    for p in (world.get('players') or {}).values():
        if not p.get('observed_this_checkpoint', False) or p.get('retired'):
            continue
        r = update_player(p, seed=seed, credit=credit, days=int(days or 0), normal_on=normal_on, plus_on=plus_on,
                          speed=speed, checkpoint_id=checkpoint_id)
        res['active'] += int(r['active'])
        res['ready'] += int(bool(r['ready']))
    return res


def apply_committed_loss(player: dict, kind: str, style: str, *, normal_before: int, added_normal: bool = False,
                         kept_normal=None, career_date=None, changeset_id=None) -> dict:
    """Bookkeeping after FC27 confirmed a loss or downgrade. Returns cap change info."""
    eng = player.setdefault('engine', {})
    d = eng.setdefault('decline', {})
    game = player.get('game') or {}
    info = {'cap_before': None, 'cap_after': None}
    for x in d.get('lost') or []:
        if changeset_id and x.get('changeset_id') == changeset_id and x.get('style') == style and x.get('kind') == kind:
            return {'cap_before': x.get('cap_before'), 'cap_after': x.get('cap_after'), 'replayed': True}   # receipt replay
    cap_before = int(eng.get('playstyle_lifetime_normal_cap') if eng.get('playstyle_lifetime_normal_cap') is not None else 7)
    info['cap_before'] = cap_before
    if kind == 'LOSS':
        # At the lifetime cap the cap shrinks with the loss (4/4 -> 3/3, 1/1 -> 0/0);
        # below it only the count drops (2/4 -> 1/4).
        if normal_before >= cap_before:
            eng['playstyle_lifetime_normal_cap'] = max(0, min(cap_before, normal_before - 1))
        (eng.setdefault('playstyle_progress', {}))[style] = 0.0
        (eng.setdefault('playstyle_plus_progress', {})).pop(style, None)
    else:   # PLUS_DOWNGRADE
        eng['playstyle_plus_lifetime_eligible'] = False
        (eng.setdefault('playstyle_plus_progress', {}))[style] = 0.0
        if added_normal and normal_before + 1 > cap_before:
            eng['playstyle_lifetime_normal_cap'] = min(7, normal_before + 1)
    info['cap_after'] = int(eng.get('playstyle_lifetime_normal_cap') if eng.get('playstyle_lifetime_normal_cap') is not None else 7)
    (d.setdefault('progress', {}))[style] = 0.0
    d['days_since_loss'] = 0
    d['ready'] = None
    d.setdefault('lost', []).append({'style': style, 'kind': kind, 'age': game.get('age'), 'career_date': dict(career_date or {}),
                                     'changeset_id': changeset_id, 'cap_before': info['cap_before'], 'cap_after': info['cap_after'],
                                     'added_normal': bool(added_normal) if kind != 'LOSS' else None,
                                     # a downgrade keeps the normal PlayStyle unless his PlayStyles were full
                                     'kept_normal': (bool(kept_normal) if kept_normal is not None else None) if kind != 'LOSS' else None})
    if len(d['lost']) > 24:
        del d['lost'][:-24]
    return info


DECLINE_WRITES_PER_CHECKPOINT = 6


def loss_entries(player: dict, ready: dict) -> tuple[list, str | None]:
    """Writer entries for a ready loss/downgrade, or ([], reason) when it cannot be built."""
    from .playstyle_sync import PLAYSTYLE1, PLAYSTYLE2_GK
    from .playstyle_lifetime import ABSOLUTE_NORMAL_CAP
    from .staged_sync import Change, validate_change
    game = player.get('game') or {}
    style = str((ready or {}).get('style') or '')
    kind = str((ready or {}).get('kind') or '')
    normal, plus, is_gk = current_styles(game)
    if is_gk and style in PLAYSTYLE2_GK:
        bit, nfield, pfield = PLAYSTYLE2_GK[style], 'trait2', 'icontrait2'
    elif style in PLAYSTYLE1:
        bit, nfield, pfield = PLAYSTYLE1[style], 'trait1', 'icontrait1'
    else:
        return [], 'NO_FIELD_MAPPING'
    try:
        cur_n = int(game.get(nfield) or 0)
        cur_p = int(game.get(pfield) or 0)
    except (TypeError, ValueError):
        return [], 'FIELD_UNREADABLE'
    pid = int(game.get('playerid') or player.get('playerid') or 0)
    base = {'playerid': pid, 'style': style, 'bit': bit, 'progress_before': 100.0, 'cooldown_days': 0,
            'mapping_evidence': 'FC27_DECLINE', 'queue_id': None, 'normal_before': len(normal), 'age': game.get('age')}
    if kind == 'LOSS':
        if not cur_n & bit:
            return [], 'NOT_OWNED'
        return [{**base, 'kind': 'PLAYSTYLE_LOSS', 'family': 'PLAYSTYLE_LOSS', 'field': nfield,
                 'expected': cur_n, 'proposed': cur_n & ~bit}], None
    if kind == 'PLUS_DOWNGRADE':
        if not cur_p & bit:
            return [], 'NOT_OWNED'
        out = [{**base, 'kind': 'PLUS_DOWNGRADE', 'family': 'PLAYSTYLE_PLUS_LOSS', 'field': pfield,
                'expected': cur_p, 'proposed': cur_p & ~bit, 'added_normal': False, 'kept_normal': bool(cur_n & bit)}]
        if not cur_n & bit and len(normal) < ABSOLUTE_NORMAL_CAP:
            add = {**base, 'kind': 'PLUS_DOWNGRADE', 'family': 'PLAYSTYLE', 'field': nfield,
                   'expected': cur_n, 'proposed': cur_n | bit, 'added_normal': True}
            try:
                validate_change(Change(pid, nfield, cur_n, cur_n | bit, 'PLAYSTYLE', 'decline'))
                out.append(add)
                out[0]['added_normal'] = True
                out[0]['kept_normal'] = True
            except Exception:
                pass      # unverified normal mapping: the PlayStyle+ is removed without the fallback
        return out, None
    return [], 'UNKNOWN_KIND'
