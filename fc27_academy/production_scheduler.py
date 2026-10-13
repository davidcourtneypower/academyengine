"""Fair, bounded scheduling of receipt-gated atomic production groups."""
from collections import defaultdict, deque

FAMILIES=('NORMAL_ACQUISITION','PLUS_ACQUISITION','ROLE_UPGRADE','NEWGEN_ENRICHMENT','PLAYSTYLE_LOSS','PLUS_DOWNGRADE')

def select_groups(entries,total,limits,state=None,user_priority=lambda pid:1):
    state=dict(state or {}); cursors=dict(state.get('cursors') or {})
    grouped={}
    for e in entries:
        # A Role++ or a PlayStyle+ downgrade can span several fields; they stay one atomic group.
        key=(e['kind'],e['playerid'],e.get('role') if e['kind']=='ROLE_UPGRADE' else (e.get('style') if e['kind']=='PLUS_DOWNGRADE' else e['field']))
        grouped.setdefault(key,[]).append(e)
    queues={}
    for kind in FAMILIES:
        cursor=int(cursors.get(kind,0)); rows=[g for k,g in grouped.items() if k[0]==kind]
        rows.sort(key=lambda g:(user_priority(g[0]['playerid']),g[0]['playerid']<=cursor,g[0]['playerid']))
        queues[kind]=deque(rows)
    start=int(state.get('family_turn',0))%len(FAMILIES)
    order=FAMILIES[start:]+FAMILIES[:start]; chosen=[]; holds=[]; used=set(); counts=defaultdict(int)
    while any(queues.values()) and len(chosen)<total:
        for kind in order:
            q=queues[kind]
            if not q: continue
            group=q.popleft(); pid=group[0]['playerid']; reason=None
            if counts[kind]>=limits.get(kind,0): reason='FAMILY_LIMIT'
            elif pid in used: reason='ONE_CHANGE_FAMILY_PER_PLAYER_PER_CHECKPOINT'
            elif len(chosen)+len(group)>total: reason='BUNDLE_FIELD_LIMIT'
            if reason:
                holds.append({'kind':kind,'playerid':pid,'reason':reason}); continue
            chosen.extend(group); used.add(pid); counts[kind]+=1; cursors[kind]=pid
    for kind,q in queues.items():
        holds.extend({'kind':kind,'playerid':g[0]['playerid'],'reason':'BUNDLE_FIELD_LIMIT'} for g in q)
    state.update(cursors=cursors,family_turn=(start+1)%len(FAMILIES))
    return chosen,state,holds
