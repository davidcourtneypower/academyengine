
import random
ARCHETYPES={
"EXPLOSIVE_WINGER":{"positions":{"LW","RW","LM","RM"},"weights":{"pace":1.30,"technique":1.14,"flair":1.12,"passing":.91,"shooting":.94,"physical":.88,"mentality":.94},"styles":["Rapid","Quick Step","Technical","Trickster","Flair"]},
"CREATIVE_WINGER":{"positions":{"LW","RW","LM","RM"},"weights":{"pace":1.08,"technique":1.22,"flair":1.22,"passing":1.10,"shooting":.92,"physical":.82,"mentality":.98},"styles":["Technical","Trickster","Flair","Whipped Pass","Inventive"]},
"POACHER":{"positions":{"ST","CF"},"weights":{"shooting":1.30,"pace":1.05,"technique":1.02,"passing":.80,"physical":.95,"mentality":1.10,"flair":.90},"styles":["Finesse Shot","Low Driven Shot","Precision Header","Acrobatic"]},
"COMPLETE_FORWARD":{"positions":{"ST","CF"},"weights":{"shooting":1.18,"pace":1.05,"technique":1.08,"passing":.95,"physical":1.10,"mentality":1.08,"flair":.98},"styles":["Power Shot","Finesse Shot","Aerial","First Touch"]},
"CREATIVE_10":{"positions":{"CAM","CM"},"weights":{"passing":1.28,"technique":1.22,"flair":1.15,"shooting":.95,"pace":.88,"physical":.78,"mentality":1.08},"styles":["Incisive Pass","Inventive","Technical","Tiki Taka","First Touch"]},
"DEEP_PLAYMAKER":{"positions":{"CM","CDM"},"weights":{"passing":1.28,"technique":1.12,"defending":.98,"mentality":1.18,"pace":.78,"physical":.92,"flair":.98},"styles":["Long Ball Pass","Pinged Pass","Tiki Taka","Press Proven","Intercept"]},
"BOX_TO_BOX":{"positions":{"CM","CDM"},"weights":{"passing":1.05,"technique":1.00,"defending":1.08,"mentality":1.12,"pace":1.00,"physical":1.18,"shooting":.98},"styles":["Relentless","Press Proven","Intercept","Pinged Pass"]},
"BALL_WINNER":{"positions":{"CDM","CM"},"weights":{"defending":1.28,"physical":1.18,"mentality":1.16,"passing":.90,"technique":.86,"pace":.94},"styles":["Intercept","Anticipate","Bruiser","Jockey","Relentless"]},
"BALL_PLAYING_CB":{"positions":{"CB"},"weights":{"defending":1.20,"physical":1.10,"passing":1.08,"technique":.98,"mentality":1.14,"pace":.91},"styles":["Anticipate","Intercept","Long Ball Pass","Aerial","Block"]},
"STOPPER_CB":{"positions":{"CB"},"weights":{"defending":1.30,"physical":1.24,"mentality":1.12,"passing":.82,"technique":.80,"pace":.90},"styles":["Bruiser","Block","Aerial Fortress","Anticipate","Slide Tackle"]},
"ATTACKING_FULLBACK":{"positions":{"LB","RB","LWB","RWB"},"weights":{"pace":1.18,"passing":1.08,"technique":1.04,"defending":1.00,"physical":1.04,"mentality":1.00},"styles":["Whipped Pass","Rapid","Relentless","Jockey"]},
"DEFENSIVE_FULLBACK":{"positions":{"LB","RB","LWB","RWB"},"weights":{"defending":1.20,"physical":1.10,"pace":1.06,"passing":.94,"technique":.92,"mentality":1.08},"styles":["Jockey","Anticipate","Intercept","Relentless"]},
"SHOT_STOPPER":{"positions":{"GK"},"weights":{"goalkeeping":1.30,"mentality":1.12,"passing":.65,"physical":.96},"styles":["Quick Reflexes","Far Reach","Deflector"]},
"SWEEPER_KEEPER":{"positions":{"GK"},"weights":{"goalkeeping":1.18,"mentality":1.12,"passing":1.04,"physical":1.00},"styles":["Rush Out","Footwork","Far Throw","Cross Claimer"]},
}

ROLE_PREFERENCES={
"EXPLOSIVE_WINGER":["Inside Forward","Winger"],"CREATIVE_WINGER":["Wide Playmaker","Winger"],
"POACHER":["Poacher","Advanced Forward"],"COMPLETE_FORWARD":["Advanced Forward","Target Forward"],
"CREATIVE_10":["Playmaker","Classic 10"],"DEEP_PLAYMAKER":["Deep-Lying Playmaker","Holding"],
"BOX_TO_BOX":["Box-to-Box","Box Crasher"],"BALL_WINNER":["Holding","Centre Half"],
"BALL_PLAYING_CB":["Ball-Playing Defender","Defender"],"STOPPER_CB":["Stopper","Defender"],
"ATTACKING_FULLBACK":["Attacking Wingback","Wingback"],"DEFENSIVE_FULLBACK":["Fullback","Inverted Wingback"],
"SHOT_STOPPER":["Goalkeeper"],"SWEEPER_KEEPER":["Sweeper Keeper","Ball-Playing Keeper"]}
GROUP_ATTRS={
"pace":["acceleration","sprintspeed"],"shooting":["finishing","shotpower","longshots","positioning","volleys"],
"passing":["shortpassing","longpassing","vision","crossing","curve"],"technique":["dribbling","ballcontrol","agility","balance"],
"defending":["defensiveawareness","interceptions","standingtackle","slidingtackle"],"physical":["strength","stamina","jumping","aggression"],
"mentality":["reactions","composure"],"goalkeeping":["gkdiving","gkhandling","gkkicking","gkpositioning","gkreflexes"]}
def choose_archetype(position,seed):
 r=random.Random(seed^0xF00D);valid=[k for k,v in ARCHETYPES.items() if position in v["positions"]]
 return r.choice(valid) if valid else "BOX_TO_BOX"
def make_dna(position,seed,country_multipliers=None):
 r=random.Random(seed^0xD1A);name=choose_archetype(position,seed);a=ARCHETYPES[name];cm=country_multipliers or {}
 apt={}
 for group,w in a["weights"].items():
  modifier=cm.get(group,1.0)
  apt[group]=round(max(.55,min(1.45,w*modifier*r.uniform(.91,1.09))),3)
 return {"archetype":name,"aptitudes":apt,"preferred_playstyles":list(a["styles"]),"preferred_roles":list(ROLE_PREFERENCES.get(name,[])),"position":position}
def shape_attributes(attrs,dna,strength=.38):
 """Redistribute attribute emphasis while keeping overall level broadly stable."""
 out=dict(attrs);apt=dna["aptitudes"]
 touched=[]
 for group,names in GROUP_ATTRS.items():
  w=apt.get(group,1.0)
  for n in names:
   if n in out:
    old=out[n];out[n]=max(1,min(99,round(old+(w-1)*10*strength)));touched.append((n,old))
 # recenter touched attributes so archetype changes shape much more than raw average.
 if touched:
  before=sum(v for _,v in touched)/len(touched);after=sum(out[n] for n,_ in touched)/len(touched);shift=before-after
  for n,_ in touched:out[n]=max(1,min(99,round(out[n]+shift)))
 return out
def growth_allocation(dna):
 a=dna["aptitudes"];total=sum(max(.01,v) for v in a.values())
 return {k:round(v/total,4) for k,v in a.items()}
