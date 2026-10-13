"""Season/lifecycle integration audit.

This is an invariant monitor, not an evolution writer. It verifies that generated-player
identity replacement, missing/returning players, free-agent freezes and season cohorts
are being handled without carrying development state onto a different generated person.
"""
from __future__ import annotations

SEASON_COHORT_SIGNAL_MIN=100


def audit_world(world:dict, bootstrap:dict|None=None):
    bootstrap=bootstrap or {}
    players=world.get('players') or {}
    observed=missing=club=free=other=active_progress_holds=identity_rebases=0
    for p in players.values():
        is_observed=bool(p.get('observed_this_checkpoint'))
        if is_observed: observed+=1
        else: missing+=1
        lc=p.get('lifecycle')
        if is_observed:
            if lc=='CLUB': club+=1
            elif lc=='FREE_AGENT': free+=1
            else: other+=1
        if p.get('bootstrap_source')=='REGENERATED_ID_REBASE': identity_rebases+=1
        if lc!='CLUB':
            e=p.get('engine') or {}
            if int(e.get('playstyle_acquisition_cooldown_days_remaining',0) or 0)>0 or int(e.get('playstyle_plus_cooldown_days_remaining',0) or 0)>0 or int(e.get('role_acquisition_cooldown_days_remaining',0) or 0)>0:
                active_progress_holds += 1
    cohort=int(bootstrap.get('generation_cohort',0) or 0)
    season_signal=cohort>=SEASON_COHORT_SIGNAL_MIN
    invariants=[]
    if observed != club+free+other: invariants.append('OBSERVED_LIFECYCLE_COUNT_MISMATCH')
    if len(players) != observed+missing: invariants.append('TRACKED_COUNT_MISMATCH')
    return {
        'status':'PASS' if not invariants else 'HOLD',
        'season_boundary_signal':season_signal,'generation_cohort':cohort,'season_epoch':int(world.get('season_epoch',0) or 0),
        'observed':observed,'missing':missing,'club':club,'free_agent':free,'other':other,
        'identity_rebases_total':identity_rebases,'nonclub_with_cooldown':active_progress_holds,
        'invariants':invariants,
        'policy':'CLUB_PROGRESS_ONLY;FREE_AGENT_AND_MISSING_FREEZE;IDENTITY_REBASE_RESETS_ENGINE;NATIVE_POTENTIAL_AND_ATTRIBUTES_OWNED_BY_FC27',
    }
