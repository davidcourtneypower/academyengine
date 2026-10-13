"""FC27 PlayStyle storage and production-safe mapping boundary.

The mapping source is FC 27 Live Editor v27.1.0's playstyles enum; save/reload
verified bits retain the stronger evidence label.  Normal and PlayStyle+ writes
still pass through generated-player, expected-value, additive-bit, readback,
rollback and durable-receipt guards.
"""


PLAYSTYLE1 = {
    "Finesse Shot":1,"Chip Shot":2,"Power Shot":4,"Dead Ball":8,
    "Precision Header":16,"Acrobatic":32,"Low Driven Shot":64,"Gamechanger":128,
    "Incisive Pass":256,"Pinged Pass":512,"Long Ball Pass":1024,"Tiki Taka":2048,
    "Whipped Pass":4096,"Inventive":8192,"Jockey":16384,"Block":32768,
    "Intercept":65536,"Anticipate":131072,"Slide Tackle":262144,"Aerial Fortress":524288,
    "Technical":1048576,"Rapid":2097152,"First Touch":4194304,"Trickster":8388608,
    "Press Proven":16777216,"Quick Step":33554432,"Relentless":67108864,
    "Long Throw":134217728,"Bruiser":268435456,"Enforcer":536870912,
}
PLAYSTYLE2_GK = {
    "Far Throw":1,"Footwork":2,"Cross Claimer":4,"Rush Out":8,"Far Reach":16,"Deflector":32,
}
PLAYSTYLE2_NON_PLAYSTYLE_MASK = 64|128|256|512|1024|2048|4096|8192

# Directly demonstrated in FC27 itself. These labels intentionally remain stronger
# than source-enum evidence when both are available.
FC27_SAVE_RELOAD_VERIFIED_BITS = {
    ("trait1", 1): "Finesse Shot",
    ("trait1", 65536): "Intercept",
    ("icontrait1", 65536): "Intercept+",
    ("trait2", 4): "Cross Claimer",
    ("icontrait2", 4): "Cross Claimer+",
}

# FC 27 Live Editor v27.1.0 source evidence:
# lua/libs/v2/imports/other/playstyles_enum.lua
# The UI uses the same bit enum for trait1/icontrait1 and trait2/icontrait2.
FC27_LE_V271_NORMAL_BITS = {
    **{("trait1", bit): name for name, bit in PLAYSTYLE1.items()},
    **{("trait2", bit): name for name, bit in PLAYSTYLE2_GK.items()},
}
FC27_LE_V271_PLUS_BITS = {
    **{("icontrait1", bit): f"{name}+" for name, bit in PLAYSTYLE1.items()},
    **{("icontrait2", bit): f"{name}+" for name, bit in PLAYSTYLE2_GK.items()},
}
FC27_LE_V271_ALL_BITS = {**FC27_LE_V271_NORMAL_BITS, **FC27_LE_V271_PLUS_BITS}


FC27_VERIFIED_BITS = dict(FC27_LE_V271_ALL_BITS)
FC27_VERIFIED_BITS.update(FC27_SAVE_RELOAD_VERIFIED_BITS)


def mapping_evidence(field, bit):
    key=(str(field), int(bit))
    if key in FC27_SAVE_RELOAD_VERIFIED_BITS:
        return "FC27_SAVE_RELOAD_VERIFIED_PER_BIT"
    if key in FC27_LE_V271_NORMAL_BITS:
        return "FC27_LIVE_EDITOR_V27_1_0_SOURCE_ENUM_NORMAL"
    if key in FC27_LE_V271_PLUS_BITS:
        return "FC27_LIVE_EDITOR_V27_1_0_SOURCE_ENUM_PLUS"
    return None



def verified_mapping(field, bit):
    return FC27_VERIFIED_BITS.get((str(field), int(bit)))

def normal_mapping(field, bit):
    return FC27_LE_V271_NORMAL_BITS.get((str(field), int(bit)))

def plus_mapping(field, bit):
    return FC27_LE_V271_PLUS_BITS.get((str(field), int(bit)))
