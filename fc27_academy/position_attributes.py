"""Position-aware FC27 attribute families.

Goalkeepers have five primary goalkeeper attributes. Outfield attributes still exist
on FC records, but are secondary for GK generation/development and must never be
used as the keeper's primary OVR/development signal.
"""
OUTFIELD_ATTRIBUTES=(
"crossing","finishing","headingaccuracy","shortpassing","volleys","defensiveawareness",
"standingtackle","slidingtackle","dribbling","curve","freekickaccuracy","longpassing","ballcontrol",
"shotpower","jumping","stamina","strength","longshots","acceleration","sprintspeed","agility",
"reactions","balance","aggression","composure","interceptions","positioning","vision","penalties")
GOALKEEPER_ATTRIBUTES=("gkdiving","gkhandling","gkkicking","gkpositioning","gkreflexes")
ALL_ATTRIBUTES=OUTFIELD_ATTRIBUTES+GOALKEEPER_ATTRIBUTES

FC27_POSITION_IDS={0:"GK",2:"RWB",3:"RB",5:"CB",7:"LB",8:"LWB",10:"CDM",12:"RM",14:"CM",16:"LM",18:"CAM",21:"CF",23:"RW",25:"ST",27:"LW"}

def normalize_position(position):
    if isinstance(position,(int,float)) and int(position) in FC27_POSITION_IDS:
        return FC27_POSITION_IDS[int(position)]
    s=str(position if position is not None else "").upper()
    if s.isdigit() and int(s) in FC27_POSITION_IDS:
        return FC27_POSITION_IDS[int(s)]
    return s or "UNKNOWN"

def is_goalkeeper(position):
    return normalize_position(position)=="GK"

def primary_attributes(position):
    return GOALKEEPER_ATTRIBUTES if is_goalkeeper(position) else OUTFIELD_ATTRIBUTES

def secondary_attributes(position):
    return OUTFIELD_ATTRIBUTES if is_goalkeeper(position) else GOALKEEPER_ATTRIBUTES

def split_attributes(attributes, position):
    attrs=attributes or {}
    return ({k:attrs[k] for k in primary_attributes(position) if k in attrs},
            {k:attrs[k] for k in secondary_attributes(position) if k in attrs})

def validate_position_attributes(attributes, position):
    attrs=attributes or {}; required=primary_attributes(position)
    missing=[k for k in required if k not in attrs]
    return {"valid":not missing,"position":normalize_position(position),
            "family":"GOALKEEPER" if is_goalkeeper(position) else "OUTFIELD",
            "required":list(required),"missing":missing}
