"""Read-only season-boundary/new-player cohort audit. Never writes FC27."""
from __future__ import annotations
from .playstyle_development_planner import current_styles

def audit_world(world, checkpoint_id=None):
    rows=[]
    for p in (world.get('players') or {}).values():
        if not p.get('observed_this_checkpoint',False): continue
        if not p.get('generation_new_this_checkpoint',False): continue
        g=p.get('game') or {}; normal,plus,_=current_styles(g)
        rows.append({'playerid':int(p.get('playerid',0)),'age':g.get('age'),'ovr':g.get('overallrating'),'potential':g.get('potential'),'position':g.get('preferredposition1'),'lifecycle':p.get('lifecycle'),'normal_count':len(normal),'plus_count':len(plus),'normal':sorted(normal),'plus':sorted(plus)})
    n=len(rows)
    def pct(k): return round(100.0*k/n,1) if n else 0.0
    buckets={str(i):sum(r['normal_count']==i for r in rows) for i in range(4)}
    buckets['4+']=sum(r['normal_count']>=4 for r in rows)
    plus_players=sum(r['plus_count']>0 for r in rows)
    return {'checkpoint_new':n,'ps0':buckets['0'],'ps1':buckets['1'],'ps2':buckets['2'],'ps3':buckets['3'],'ps4plus':buckets['4+'],'with_ps_pct':pct(n-buckets['0']),'with_psplus':plus_players,'with_psplus_pct':pct(plus_players),'rows':rows[:25]}
