"""FC27 Role / Role+ / Role++ ID mapping used by the production engine."""
from __future__ import annotations

_BASE = {
 1:"GK Goalkeeper",2:"GK Sweeper Keeper",3:"RB Fullback",4:"RB Falseback",5:"RB Wingback",6:"RB Attacking Wingback",
 7:"LB Fullback",8:"LB Falseback",9:"LB Wingback",10:"LB Attacking Wingback",11:"CB Defender",12:"CB Stopper",
 13:"CB Ball-Playing Defender",14:"CDM Holding",15:"CDM Centre Half",16:"CDM Deep-Lying Playmaker",17:"CDM Wide Half",
 18:"CM Box-to-Box",19:"CM Holding",20:"CM Deep-Lying Playmaker",21:"CM Playmaker",22:"CM Half-Winger",
 23:"RM Winger",24:"RM Wide Midfielder",25:"RM Wide Playmaker",26:"RM Inside Forward",27:"LM Winger",
 28:"LM Wide Midfielder",29:"LM Wide Playmaker",30:"LM Inside Forward",31:"CAM Playmaker",32:"CAM Shadow Striker",
 33:"CAM Half Winger",34:"CAM Classic 10",35:"RW Winger",36:"RW Inside Forward",37:"RW Wide Playmaker",
 38:"LW Winger",39:"LW Inside Forward",40:"LW Wide Playmaker",41:"ST Advanced Forward",42:"ST Poacher",
 43:"ST False 9",44:"ST Target Forward",45:"GK Ball-Playing Keeper",46:"RB Inverted Wingback",47:"LB Inverted Wingback",
 48:"CB Wide Back",49:"CDM Box Crasher",50:"ST Roaming Striker",51:"RW False Winger",52:"LW False Winger",
}

ROLE_ID_TO_LABEL = {0:"None"}
for i, name in _BASE.items():
    ROLE_ID_TO_LABEL[i] = name + "+"
    ROLE_ID_TO_LABEL[i + 100] = name + "++"


def decode_role(value:int) -> str:
    return ROLE_ID_TO_LABEL.get(int(value), f"UNKNOWN({int(value)})")
