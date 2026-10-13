"""Nationality -> face-region weights for generated-player minifaces (v1.24.31).

Weights use the region names of the men's NG_Regens folders. Each region has a
fallback chain so the same table works for the women's ``WF`` library and for
packs that lack a region (e.g. women's ``African`` stands in for West/Central/East
Africa, ``Middle-East`` for Mashriq/Gulf). A small "any region" share is added to
every nationality for mixed heritage (``CROSS_HERITAGE``); weights need not sum to 1.

A user file ``face_regions.json`` in the Academy Engine data folder can override or
add nationalities: {"Republic of Ireland": [["Ireland", 0.8], ["Anglosphere", 0.2]]}.
"""
from __future__ import annotations

CROSS_HERITAGE = 0.03

# Region -> folders tried in order (first that exists in the library for that gender).
FALLBACKS: dict[str, list[str]] = {
    'Anglosphere': ['Anglosphere', 'England', 'Australia', 'CaucasianNA', 'Ireland'],
    'Ireland': ['Ireland', 'England', 'Anglosphere'],
    'CaucasianNA': ['CaucasianNA', 'Anglosphere', 'England'],
    'Australia': ['Australia', 'Anglosphere', 'England'],
    'England': ['England', 'Anglosphere', 'Ireland'],
    'Afroamerican': ['Afroamerican', 'African', 'Afrocaribbean', 'WestAfrica'],
    'Afrocaribbean': ['Afrocaribbean', 'African', 'Afroamerican', 'WestAfrica'],
    'WestAfrica': ['WestAfrica', 'African', 'SahelianAfrica', 'CentralAfrica'],
    'CentralAfrica': ['CentralAfrica', 'African', 'WestAfrica'],
    'EastAfrica': ['EastAfrica', 'African', 'HornOfAfrica'],
    'HornOfAfrica': ['HornOfAfrica', 'African', 'EastAfrica'],
    'SouthernAfrica': ['SouthernAfrica', 'African', 'CentralAfrica'],
    'SahelianAfrica': ['SahelianAfrica', 'African', 'WestAfrica'],
    'Maghreb': ['Maghreb', 'Middle-East', 'Mashriq'],
    'Mashriq': ['Mashriq', 'Middle-East', 'ArabGulf', 'Maghreb'],
    'ArabGulf': ['ArabGulf', 'Middle-East', 'Mashriq'],
    'Iran': ['Iran', 'Middle-East', 'Mashriq', 'Caucasus'],
    'Israel': ['Israel', 'Middle-East', 'Mashriq', 'CentralEurope'],
    'Turkish': ['Turkish', 'Middle-East', 'Caucasus', 'EastBalkan'],
    'Armenian': ['Armenian', 'Caucasus', 'Middle-East'],
    'Azerbaijan': ['Azerbaijan', 'Caucasus', 'Turkish', 'Middle-East'],
    'Caucasus': ['Caucasus', 'Armenian', 'Azerbaijan', 'Middle-East'],
    'CentralAsian': ['CentralAsian', 'Kazakhstan', 'Uzbekistan', 'Tajikistan', 'Mongolia'],
    'Uzbekistan': ['Uzbekistan', 'CentralAsian', 'Kazakhstan'],
    'Tajikistan': ['Tajikistan', 'CentralAsian', 'Uzbekistan', 'Iran'],
    'Mongolia': ['Mongolia', 'CentralAsian', 'Kazakhstan', 'China'],
    'China': ['China', 'Korea', 'Japan'],
    'Japan': ['Japan', 'Korea', 'China'],
    'Korea': ['Korea', 'China', 'Japan'],
    'MainlandSEA': ['MainlandSEA', 'Thailand', 'Vietnam'],
    'Vietnam': ['Vietnam', 'MainlandSEA', 'Thailand'],
    'Malaysia': ['Malaysia', 'Indonesia', 'Singapore', 'MainlandSEA', 'Philippines'],
    'Indonesia': ['Indonesia', 'Malaysia', 'Philippines'],
    'Singapore': ['Singapore', 'Malaysia', 'China'],
    'Filipino': ['Filipino', 'Philippines', 'Indonesia', 'Malaysia'],
    'SouthAsia': ['SouthAsia'],
    'PacificIslanders': ['PacificIslanders', 'Polynesia', 'Melanesia'],
    'Polynesia': ['Polynesia', 'PacificIslanders', 'Melanesia'],
    'Melanesia': ['Melanesia', 'PacificIslanders', 'Polynesia'],
    'BrazilMixed': ['BrazilMixed', 'MixedRace', 'SouthConeSA'],
    'MixedRace': ['MixedRace', 'BrazilMixed', 'Afrocaribbean'],
    'SouthConeSA': ['SouthConeSA', 'Spain', 'Italia', 'Italy'],
    'NorthernSA': ['NorthernSA', 'Mestizo', 'Andean', 'BrazilMixed'],
    'Mestizo': ['Mestizo', 'Mexico', 'Andean', 'NorthernSA'],
    'Mexico': ['Mexico', 'Mestizo'],
    'Andean': ['Andean', 'IndigenousSA', 'Mestizo'],
    'IndigenousSA': ['IndigenousSA', 'Andean', 'Mestizo'],
    'Spain': ['Spain', 'Portugal', 'Italia', 'Italy'],
    'Portugal': ['Portugal', 'Spain'],
    'Italia': ['Italia', 'Italy', 'Spain'],
    'France': ['France', 'CentralEurope', 'Germany', 'Spain'],
    'Netherlands': ['Netherlands', 'CentralEurope', 'Germany', 'Denmark'],
    'CentralEurope': ['CentralEurope', 'Germany', 'Netherlands', 'WestSlavic'],
    'Germany': ['Germany', 'CentralEurope'],
    'Denmark': ['Denmark', 'Scandinavian', 'Norway', 'Sweden'],
    'Norway': ['Norway', 'Scandinavian', 'Sweden', 'Denmark'],
    'Sweden': ['Sweden', 'Scandinavian', 'Norway', 'Denmark'],
    'Scandinavian': ['Scandinavian', 'Sweden', 'Norway', 'Denmark'],
    'Iceland': ['Iceland', 'Scandinavian', 'Norway'],
    'Finstonia': ['Finstonia', 'Baltics', 'Scandinavian', 'Sweden'],
    'Baltics': ['Baltics', 'Finstonia', 'EastSlavic', 'Poland'],
    'Poland': ['Poland', 'WestSlavic', 'EastSlavic'],
    'WestSlavic': ['WestSlavic', 'Poland', 'CentralEurope'],
    'EastSlavic': ['EastSlavic', 'Poland', 'Baltics'],
    'Hungary': ['Hungary', 'CentralEurope', 'Romania', 'WestSlavic'],
    'Romania': ['Romania', 'EastBalkan', 'Hungary'],
    'EastBalkan': ['EastBalkan', 'Romania', 'WestBalkan', 'Serbia'],
    'WestBalkan': ['WestBalkan', 'Serbia', 'EastBalkan'],
    'Albania': ['Albania', 'AlbanianGreek', 'WestBalkan', 'Serbia'],
    'AlbanianGreek': ['AlbanianGreek', 'Albania', 'EastBalkan', 'Italia', 'Italy'],
}

W = list  # readability: W([("Region", weight), ...])

NATION_WEIGHTS: dict[str, list[tuple[str, float]]] = {
    # --- British Isles & Anglosphere ---
    'Republic of Ireland': [('Ireland', .86), ('Anglosphere', .06), ('Afrocaribbean', .02), ('WestAfrica', .02), ('EastSlavic', .01)],
    'Northern Ireland': [('Ireland', .80), ('Anglosphere', .14), ('Afrocaribbean', .02)],
    'England': [('Anglosphere', .62), ('Ireland', .06), ('Afrocaribbean', .12), ('WestAfrica', .07), ('SouthAsia', .05), ('MixedRace', .05)],
    'Scotland': [('Anglosphere', .70), ('Ireland', .20), ('WestAfrica', .03), ('SouthAsia', .02)],
    'Wales': [('Anglosphere', .80), ('Ireland', .10), ('Afrocaribbean', .04), ('SouthAsia', .02)],
    'United States': [('CaucasianNA', .46), ('Afroamerican', .24), ('Mestizo', .16), ('MixedRace', .06), ('China', .02), ('Korea', .02)],
    'Canada': [('CaucasianNA', .55), ('Afrocaribbean', .14), ('WestAfrica', .08), ('SouthAsia', .07), ('China', .04), ('Mestizo', .04)],
    'Australia': [('Anglosphere', .70), ('SouthAsia', .05), ('China', .05), ('Mashriq', .05), ('PacificIslanders', .04), ('EastAfrica', .04)],
    'New Zealand': [('Anglosphere', .62), ('PacificIslanders', .30), ('China', .03)],
    'Gibraltar': [('Spain', .5), ('Anglosphere', .4), ('Maghreb', .1)],
    # --- Western Europe ---
    'France': [('France', .50), ('WestAfrica', .14), ('Maghreb', .14), ('Afrocaribbean', .10), ('CentralAfrica', .08)],
    'Belgium': [('CentralEurope', .40), ('France', .20), ('Netherlands', .10), ('CentralAfrica', .14), ('Maghreb', .10), ('WestAfrica', .04)],
    'Netherlands': [('Netherlands', .64), ('Afrocaribbean', .14), ('Maghreb', .10), ('Turkish', .05), ('WestAfrica', .04)],
    'Luxembourg': [('CentralEurope', .55), ('Portugal', .25), ('France', .15)],
    'Germany': [('CentralEurope', .66), ('Turkish', .12), ('WestAfrica', .06), ('WestBalkan', .06), ('Mashriq', .05), ('Poland', .03)],
    'Austria': [('CentralEurope', .70), ('WestBalkan', .12), ('Turkish', .08), ('WestAfrica', .05)],
    'Switzerland': [('CentralEurope', .55), ('Italia', .10), ('France', .08), ('Albania', .12), ('WestBalkan', .07), ('WestAfrica', .05)],
    'Liechtenstein': [('CentralEurope', .9), ('Italia', .05)],
    'Spain': [('Spain', .80), ('SouthConeSA', .05), ('Maghreb', .06), ('WestAfrica', .05), ('NorthernSA', .03)],
    'Andorra': [('Spain', .7), ('Portugal', .15), ('France', .15)],
    'Portugal': [('Portugal', .76), ('Afrocaribbean', .04), ('WestAfrica', .10), ('BrazilMixed', .06), ('CentralAfrica', .03)],
    'Italy': [('Italia', .84), ('WestAfrica', .05), ('Maghreb', .04), ('Albania', .03), ('SouthConeSA', .03)],
    'San Marino': [('Italia', .95)],
    'Malta': [('Italia', .55), ('Mashriq', .25), ('Anglosphere', .15)],
    # --- Nordics & Baltics ---
    'Denmark': [('Denmark', .80), ('Mashriq', .05), ('Turkish', .04), ('EastAfrica', .04), ('WestBalkan', .03)],
    'Norway': [('Norway', .80), ('EastAfrica', .06), ('HornOfAfrica', .04), ('Mashriq', .04), ('SouthAsia', .03)],
    'Sweden': [('Sweden', .70), ('HornOfAfrica', .07), ('Mashriq', .07), ('WestBalkan', .06), ('EastAfrica', .04), ('Iran', .03)],
    'Finland': [('Finstonia', .85), ('Scandinavian', .06), ('HornOfAfrica', .04), ('WestAfrica', .02)],
    'Estonia': [('Finstonia', .70), ('EastSlavic', .25)],
    'Iceland': [('Iceland', .92), ('Scandinavian', .05)],
    'Faroe Islands': [('Scandinavian', .55), ('Iceland', .30), ('Denmark', .15)],
    'Greenland': [('Mongolia', .55), ('Scandinavian', .45)],
    'Latvia': [('Baltics', .80), ('EastSlavic', .18)],
    'Lithuania': [('Baltics', .86), ('EastSlavic', .08), ('Poland', .05)],
    # --- Central & Eastern Europe ---
    'Poland': [('Poland', .92), ('EastSlavic', .05)],
    'Czech Republic': [('WestSlavic', .90), ('CentralEurope', .05), ('EastSlavic', .03)],
    'Slovakia': [('WestSlavic', .88), ('Hungary', .08)],
    'Hungary': [('Hungary', .90), ('Romania', .04), ('WestSlavic', .03)],
    'Slovenia': [('WestBalkan', .55), ('CentralEurope', .40)],
    'Croatia': [('WestBalkan', .94)],
    'Serbia': [('WestBalkan', .94)],
    'Bosnia Herzegovina': [('WestBalkan', .94)],
    'Montenegro': [('WestBalkan', .85), ('Albania', .10)],
    'North Macedonia': [('EastBalkan', .55), ('WestBalkan', .25), ('Albania', .20)],
    'Kosovo': [('Albania', .90), ('WestBalkan', .07)],
    'Albania': [('Albania', .92), ('AlbanianGreek', .05)],
    'Greece': [('AlbanianGreek', .82), ('Albania', .08), ('EastBalkan', .05)],
    'Cyprus': [('AlbanianGreek', .70), ('Turkish', .20), ('Mashriq', .05)],
    'Bulgaria': [('EastBalkan', .88), ('Turkish', .07)],
    'Romania': [('Romania', .90), ('Hungary', .05)],
    'Moldova': [('Romania', .70), ('EastSlavic', .28)],
    'Ukraine': [('EastSlavic', .94), ('Poland', .03)],
    'Belarus': [('EastSlavic', .94), ('Poland', .03)],
    'Russia': [('EastSlavic', .82), ('CentralAsian', .05), ('Caucasus', .07), ('Baltics', .03)],
    'Georgia': [('Caucasus', .90), ('Armenian', .05)],
    'Armenia': [('Armenian', .92), ('Caucasus', .05)],
    'Azerbaijan': [('Azerbaijan', .88), ('Caucasus', .08)],
    'Turkey': [('Turkish', .88), ('Caucasus', .05), ('Mashriq', .04)],
    'Israel': [('Israel', .82), ('Mashriq', .08), ('EastSlavic', .05), ('HornOfAfrica', .03)],
    # --- South America ---
    'Brazil': [('BrazilMixed', .64), ('MixedRace', .14), ('SouthConeSA', .14), ('Afrocaribbean', .05)],
    'Argentina': [('SouthConeSA', .84), ('Mestizo', .08), ('IndigenousSA', .04)],
    'Uruguay': [('SouthConeSA', .88), ('MixedRace', .06), ('Afrocaribbean', .03)],
    'Chile': [('SouthConeSA', .55), ('Mestizo', .35), ('IndigenousSA', .07)],
    'Paraguay': [('Mestizo', .55), ('SouthConeSA', .35), ('IndigenousSA', .08)],
    'Bolivia': [('IndigenousSA', .50), ('Mestizo', .42), ('SouthConeSA', .05)],
    'Peru': [('Mestizo', .50), ('IndigenousSA', .38), ('SouthConeSA', .05), ('Afrocaribbean', .04)],
    'Ecuador': [('Mestizo', .45), ('IndigenousSA', .15), ('NorthernSA', .15), ('Afrocaribbean', .22)],
    'Colombia': [('NorthernSA', .55), ('Mestizo', .20), ('Afrocaribbean', .20)],
    'Venezuela': [('NorthernSA', .62), ('Mestizo', .18), ('Afrocaribbean', .12), ('SouthConeSA', .05)],
    'Guyana': [('Afrocaribbean', .45), ('SouthAsia', .40), ('MixedRace', .12)],
    'Suriname': [('Afrocaribbean', .50), ('SouthAsia', .25), ('Indonesia', .10), ('MixedRace', .12)],
    # --- Central America & Caribbean ---
    'Mexico': [('Mestizo', .82), ('IndigenousSA', .08), ('SouthConeSA', .06)],
    'Guatemala': [('Mestizo', .55), ('IndigenousSA', .40)],
    'Honduras': [('Mestizo', .70), ('Afrocaribbean', .22), ('IndigenousSA', .05)],
    'El Salvador': [('Mestizo', .88), ('IndigenousSA', .08)],
    'Nicaragua': [('Mestizo', .80), ('Afrocaribbean', .12)],
    'Costa Rica': [('Mestizo', .62), ('SouthConeSA', .18), ('Afrocaribbean', .18)],
    'Panama': [('Mestizo', .50), ('Afrocaribbean', .45)],
    'Belize': [('Afrocaribbean', .50), ('Mestizo', .45)],
    'Cuba': [('Afrocaribbean', .45), ('MixedRace', .30), ('SouthConeSA', .22)],
    'Dominican Republic': [('MixedRace', .55), ('Afrocaribbean', .38)],
    'Puerto Rico': [('MixedRace', .55), ('Afrocaribbean', .20), ('SouthConeSA', .20)],
    'Haiti': [('Afrocaribbean', .96)],
    'Jamaica': [('Afrocaribbean', .95)],
    'Trinidad & Tobago': [('Afrocaribbean', .55), ('SouthAsia', .30), ('MixedRace', .12)],
    'Netherlands Antilles': [('Afrocaribbean', .80), ('MixedRace', .15)],
    'Aruba': [('MixedRace', .60), ('Afrocaribbean', .30)],
    'Bermuda': [('Afrocaribbean', .62), ('Anglosphere', .33)],
    'Cayman Islands': [('Afrocaribbean', .55), ('MixedRace', .25), ('Anglosphere', .15)],
    'Bahamas': [('Afrocaribbean', .90), ('Anglosphere', .06)],
    'Barbados': [('Afrocaribbean', .94)],
    'Turks & Caicos Islands': [('Afrocaribbean', .94)],
    'US Virgin Islands': [('Afrocaribbean', .90)],
    'British Virgin Islands': [('Afrocaribbean', .90)],
    'Anguilla': [('Afrocaribbean', .94)], 'Antigua & Barbuda': [('Afrocaribbean', .94)],
    'Dominica': [('Afrocaribbean', .94)], 'Grenada': [('Afrocaribbean', .94)], 'Montserrat': [('Afrocaribbean', .94)],
    'St Kitts & Nevis': [('Afrocaribbean', .94)], 'St Lucia': [('Afrocaribbean', .94)],
    'St Vincent & the Grenadines': [('Afrocaribbean', .94)],
    # --- North Africa & Middle East ---
    'Morocco': [('Maghreb', .94)], 'Algeria': [('Maghreb', .94)], 'Tunisia': [('Maghreb', .94)],
    'Libya': [('Maghreb', .90), ('SahelianAfrica', .05)], 'Mauritania': [('Maghreb', .55), ('SahelianAfrica', .42)],
    'Egypt': [('Mashriq', .88), ('Maghreb', .08)], 'Sudan': [('HornOfAfrica', .55), ('SahelianAfrica', .30), ('Mashriq', .12)],
    'Lebanon': [('Mashriq', .95)], 'Syria': [('Mashriq', .95)], 'Jordan': [('Mashriq', .95)],
    'Palestine': [('Mashriq', .95)], 'Iraq': [('Mashriq', .88), ('Iran', .07)],
    'Saudi Arabia': [('ArabGulf', .85), ('Mashriq', .08), ('HornOfAfrica', .05)],
    'Kuwait': [('ArabGulf', .90), ('Mashriq', .07)], 'Qatar': [('ArabGulf', .80), ('Mashriq', .08), ('SouthAsia', .05), ('Maghreb', .05)],
    'Bahrain': [('ArabGulf', .90)], 'United Arab Emirates': [('ArabGulf', .88), ('SouthAsia', .06)],
    'Oman': [('ArabGulf', .85), ('EastAfrica', .10)], 'Yemen': [('ArabGulf', .85), ('HornOfAfrica', .10)],
    'Iran': [('Iran', .90), ('Azerbaijan', .05)], 'Afghanistan': [('Tajikistan', .45), ('SouthAsia', .30), ('Iran', .22)],
    # --- Sub-Saharan Africa ---
    'Nigeria': [('WestAfrica', .95)], 'Ghana': [('WestAfrica', .96)], 'Ivory Coast': [('WestAfrica', .95)],
    'Senegal': [('WestAfrica', .80), ('SahelianAfrica', .17)], 'Gambia': [('WestAfrica', .85), ('SahelianAfrica', .12)],
    'Guinea': [('WestAfrica', .90), ('SahelianAfrica', .07)], 'Guinea-Bissau': [('WestAfrica', .94)],
    'Sierra Leone': [('WestAfrica', .95)], 'Liberia': [('WestAfrica', .95)], 'Togo': [('WestAfrica', .95)],
    'Benin': [('WestAfrica', .95)], 'Burkina Faso': [('SahelianAfrica', .55), ('WestAfrica', .42)],
    'Mali': [('SahelianAfrica', .60), ('WestAfrica', .37)], 'Niger': [('SahelianAfrica', .80), ('WestAfrica', .17)],
    'Chad': [('SahelianAfrica', .70), ('CentralAfrica', .27)], 'Cape Verde': [('Afrocaribbean', .45), ('MixedRace', .30), ('WestAfrica', .22)],
    'Cameroon': [('CentralAfrica', .80), ('WestAfrica', .17)], 'Gabon': [('CentralAfrica', .95)],
    'Congo': [('CentralAfrica', .95)], 'DR Congo': [('CentralAfrica', .95)], 'Central African Republic': [('CentralAfrica', .95)],
    'Equatorial Guinea': [('CentralAfrica', .95)], 'São Tomé & Príncipe': [('CentralAfrica', .70), ('MixedRace', .25)],
    'Angola': [('CentralAfrica', .70), ('SouthernAfrica', .25)], 'Burundi': [('EastAfrica', .90), ('CentralAfrica', .07)],
    'Rwanda': [('EastAfrica', .90), ('CentralAfrica', .07)], 'Uganda': [('EastAfrica', .95)], 'Kenya': [('EastAfrica', .95)],
    'Tanzania': [('EastAfrica', .93)], 'Ethiopia': [('HornOfAfrica', .95)], 'Eritrea': [('HornOfAfrica', .95)],
    'Somalia': [('HornOfAfrica', .96)], 'Djibouti': [('HornOfAfrica', .90)],
    'South Africa': [('SouthernAfrica', .72), ('Anglosphere', .14), ('MixedRace', .10)],
    'Namibia': [('SouthernAfrica', .85), ('Anglosphere', .08)], 'Botswana': [('SouthernAfrica', .95)],
    'Zimbabwe': [('SouthernAfrica', .95)], 'Zambia': [('SouthernAfrica', .90), ('CentralAfrica', .07)],
    'Malawi': [('SouthernAfrica', .90), ('EastAfrica', .07)], 'Mozambique': [('SouthernAfrica', .90), ('EastAfrica', .07)],
    'Lesotho': [('SouthernAfrica', .96)], 'Eswatini': [('SouthernAfrica', .96)],
    'Madagascar': [('EastAfrica', .45), ('Indonesia', .35), ('MixedRace', .17)],
    'Mauritius': [('SouthAsia', .60), ('Afrocaribbean', .25), ('MixedRace', .12)],
    'Seychelles': [('MixedRace', .60), ('EastAfrica', .30)], 'Comoros': [('EastAfrica', .70), ('ArabGulf', .25)],
    # --- Asia ---
    'China PR': [('China', .95)], 'Hong Kong': [('China', .90), ('Anglosphere', .03)], 'Macau': [('China', .90), ('Portugal', .05)],
    'Chinese Taipei': [('China', .95)], 'Japan': [('Japan', .93), ('MixedRace', .03)], 'Korea Republic': [('Korea', .96)],
    'Korea DPR': [('Korea', .97)], 'Mongolia': [('Mongolia', .95)],
    'Kazakhstan': [('CentralAsian', .70), ('EastSlavic', .25)], 'Uzbekistan': [('Uzbekistan', .92), ('CentralAsian', .05)],
    'Kyrgyzstan': [('CentralAsian', .85), ('Uzbekistan', .10)], 'Tajikistan': [('Tajikistan', .90), ('Uzbekistan', .07)],
    'Turkmenistan': [('CentralAsian', .60), ('Uzbekistan', .20), ('Iran', .17)],
    'India': [('SouthAsia', .96)], 'Pakistan': [('SouthAsia', .90), ('Tajikistan', .07)], 'Bangladesh': [('SouthAsia', .96)],
    'Sri Lanka': [('SouthAsia', .96)], 'Nepal': [('SouthAsia', .70), ('MainlandSEA', .15), ('China', .12)],
    'Bhutan': [('SouthAsia', .45), ('MainlandSEA', .25), ('China', .27)], 'Maldives': [('SouthAsia', .95)],
    'Thailand': [('MainlandSEA', .92), ('China', .05)], 'Laos': [('MainlandSEA', .95)], 'Cambodia': [('MainlandSEA', .95)],
    'Myanmar': [('MainlandSEA', .80), ('SouthAsia', .15)], 'Vietnam': [('Vietnam', .95)],
    'Malaysia': [('Malaysia', .60), ('China', .22), ('SouthAsia', .12)], 'Singapore': [('Singapore', .62), ('Malaysia', .18), ('SouthAsia', .12)],
    'Brunei': [('Malaysia', .80), ('China', .12)], 'Indonesia': [('Indonesia', .95)],
    'Philippines': [('Filipino', .88), ('MixedRace', .06), ('Anglosphere', .03)],
    'Timor-Leste': [('Indonesia', .60), ('Melanesia', .30), ('Portugal', .07)],
    'Guam': [('Filipino', .40), ('PacificIslanders', .45), ('CaucasianNA', .12)],
    # --- Oceania ---
    'Fiji': [('Melanesia', .55), ('SouthAsia', .40)], 'Papua New Guinea': [('Melanesia', .96)],
    'Solomon Islands': [('Melanesia', .96)], 'Vanuatu': [('Melanesia', .96)], 'New Caledonia': [('Melanesia', .60), ('France', .30)],
    'Samoa': [('Polynesia', .96)], 'American Samoa': [('Polynesia', .96)], 'Tonga': [('Polynesia', .96)],
    'Cook Islands': [('Polynesia', .96)], 'Tahiti': [('Polynesia', .85), ('France', .10)],
}

# Fallback for nationalities without an entry ('Rest of World', 'Free Agents', unknown IDs):
DEFAULT_WEIGHTS: list[tuple[str, float]] = [
    ('Anglosphere', .10), ('WestAfrica', .10), ('SouthConeSA', .08), ('BrazilMixed', .08), ('Spain', .06), ('France', .06),
    ('CentralEurope', .06), ('Mashriq', .06), ('Maghreb', .05), ('SouthAsia', .05), ('China', .05), ('Mestizo', .05),
    ('EastSlavic', .05), ('WestBalkan', .04), ('Afrocaribbean', .04), ('Turkish', .03),
]

# Broad families: used when a library (typically the smaller women's WF set) has no
# folder for a region or any of its fallbacks. The face then comes from a folder of the
# same family -- one of that family's region folders, or a broad folder such as
# "European" or "African".
FAMILY_OF: dict[str, str] = {}
for _fam, _regions in {
    'european': ['Anglosphere', 'Ireland', 'England', 'CaucasianNA', 'Australia', 'France', 'Netherlands', 'CentralEurope',
                 'Germany', 'Denmark', 'Norway', 'Sweden', 'Scandinavian', 'Iceland', 'Finstonia', 'Baltics', 'Poland',
                 'WestSlavic', 'EastSlavic', 'Hungary', 'Romania', 'EastBalkan', 'WestBalkan', 'Albania', 'AlbanianGreek',
                 'Spain', 'Portugal', 'Italia', 'SouthConeSA'],
    'african': ['Afroamerican', 'Afrocaribbean', 'WestAfrica', 'CentralAfrica', 'EastAfrica', 'HornOfAfrica',
                'SouthernAfrica', 'SahelianAfrica'],
    'middleeast': ['Maghreb', 'Mashriq', 'ArabGulf', 'Iran', 'Israel', 'Turkish', 'Armenian', 'Azerbaijan', 'Caucasus'],
    'centralasian': ['CentralAsian', 'Uzbekistan', 'Tajikistan', 'Mongolia'],
    'eastasian': ['China', 'Japan', 'Korea'],
    'southeastasian': ['MainlandSEA', 'Vietnam', 'Malaysia', 'Indonesia', 'Singapore', 'Filipino'],
    'southasian': ['SouthAsia'],
    'pacific': ['PacificIslanders', 'Polynesia', 'Melanesia'],
    'latin': ['Mestizo', 'Mexico', 'NorthernSA', 'Andean', 'IndigenousSA', 'BrazilMixed', 'MixedRace'],
}.items():
    for _r in _regions:
        FAMILY_OF[_r] = _fam

# Broad folder names that stand for a whole family (normalised: lowercase, letters/digits).
FAMILY_FOLDERS: dict[str, list[str]] = {
    'european': ['european', 'europe', 'caucasian', 'white'],
    'african': ['african', 'africa', 'black'],
    'middleeast': ['middleeast', 'middleeastern', 'arab', 'arabic', 'northafrica'],
    'centralasian': ['centralasian', 'centralasia'],
    'eastasian': ['eastasian', 'eastasia', 'asian', 'asia'],
    'southeastasian': ['southeastasian', 'southeastasia', 'seasian', 'asian', 'asia'],
    'southasian': ['southasian', 'indian', 'asian'],
    'pacific': ['pacific', 'pacificislander', 'oceania'],
    'latin': ['latin', 'latino', 'latinamerican', 'hispanic', 'southamerican', 'mixed'],
}
# Families to borrow from when a family is missing entirely.
FAMILY_NEAR: dict[str, list[str]] = {
    'european': ['latin', 'middleeast'], 'latin': ['european', 'african'], 'african': ['latin'],
    'middleeast': ['european', 'centralasian', 'southasian'], 'centralasian': ['eastasian', 'middleeast'],
    'eastasian': ['southeastasian', 'centralasian'], 'southeastasian': ['eastasian', 'pacific'],
    'southasian': ['middleeast', 'southeastasian'], 'pacific': ['southeastasian', 'latin'],
}

# Display names for region folders (v1.24.33). Folder names stay as they are on disk;
# anything not listed here is spelled out from its CamelCase / dashes ("SouthAsia" -> "South Asia").
REGION_LABELS: dict[str, str] = {
    'Afroamerican': 'African American', 'Afrocaribbean': 'Afro-Caribbean', 'AlbanianGreek': 'Albania & Greece',
    'ArabGulf': 'Arab Gulf', 'BrazilMixed': 'Brazil (mixed heritage)', 'CaucasianNA': 'North America (Caucasian)',
    'CentralAfrica': 'Central Africa', 'CentralAsian': 'Central Asia', 'CentralEurope': 'Central Europe',
    'EastAfrica': 'East Africa', 'EastBalkan': 'Eastern Balkans', 'EastSlavic': 'East Slavic', 'Filipino': 'Philippines',
    'Finstonia': 'Finland & Estonia', 'HornOfAfrica': 'Horn of Africa', 'IndigenousSA': 'Indigenous South America',
    'Italia': 'Italy', 'MainlandSEA': 'Mainland Southeast Asia', 'Mestizo': 'Mestizo (Latin America)',
    'Middle-East': 'Middle East', 'MixedRace': 'Mixed heritage', 'NorthernSA': 'Northern South America',
    'PacificIslanders': 'Pacific Islands', 'SahelianAfrica': 'Sahel', 'SouthAsia': 'South Asia',
    'SouthConeSA': 'Southern Cone (South America)', 'SouthernAfrica': 'Southern Africa', 'Turkish': 'Turkey',
    'WestAfrica': 'West Africa', 'WestBalkan': 'Western Balkans', 'WestSlavic': 'West Slavic', 'Armenian': 'Armenia',
}
_LABEL_NORM = {''.join(c for c in k.lower() if c.isalnum()): v for k, v in REGION_LABELS.items()}


def region_label(folder: str) -> str:
    """Friendly name for a region folder."""
    name = str(folder or '')
    hit = _LABEL_NORM.get(''.join(c for c in name.lower() if c.isalnum()))
    if hit:
        return hit
    out = []
    for i, ch in enumerate(name.replace('_', ' ').replace('-', ' ')):
        prev = name[i - 1] if i else ''
        nxt = name[i + 1] if i + 1 < len(name) else ''
        if i and ch.isupper() and (prev.islower() or (prev.isupper() and nxt.islower())):
            out.append(' ')
        out.append(ch)
    label = ' '.join(''.join(out).split())
    return label[:1].upper() + label[1:]
