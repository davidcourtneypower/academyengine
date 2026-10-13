from __future__ import annotations

# EA/FC player nationality identifiers. The sequence has remained stable across
# the Career Mode database family used by Live Editor; unknown/new IDs fall back
# safely to their numeric label rather than being guessed.
_NATIONS = [
    None,
    'Albania','Andorra','Armenia','Austria','Azerbaijan','Belarus','Belgium','Bosnia Herzegovina','Bulgaria','Croatia','Cyprus','Czech Republic','Denmark','England','Montenegro','Faroe Islands','Finland','France','North Macedonia','Georgia','Germany','Greece','Hungary','Iceland','Republic of Ireland','Israel','Italy','Latvia','Liechtenstein','Lithuania','Luxembourg','Malta','Moldova','Netherlands','Northern Ireland','Norway','Poland','Portugal','Romania','Russia','San Marino','Scotland','Slovakia','Slovenia','Spain','Sweden','Switzerland','Turkey','Ukraine','Wales','Serbia','Argentina','Bolivia','Brazil','Chile','Colombia','Ecuador','Paraguay','Peru','Uruguay','Venezuela','Anguilla','Antigua & Barbuda','Aruba','Bahamas','Barbados','Belize','Bermuda','British Virgin Islands','Canada','Cayman Islands','Costa Rica','Cuba','Dominica','International','El Salvador','Grenada','Guatemala','Guyana','Haiti','Honduras','Jamaica','Mexico','Montserrat','Netherlands Antilles','Nicaragua','Panama','Puerto Rico','St Kitts & Nevis','St Lucia','St Vincent & the Grenadines','Suriname','Trinidad & Tobago','Turks & Caicos Islands','United States','US Virgin Islands','Algeria','Angola','Benin','Botswana','Burkina Faso','Burundi','Cameroon','Cape Verde','Central African Republic','Chad','Congo','Ivory Coast','Djibouti','DR Congo','Egypt','Equatorial Guinea','Eritrea','Ethiopia','Gabon','Gambia','Ghana','Guinea','Guinea-Bissau','Kenya','Lesotho','Liberia','Libya','Madagascar','Malawi','Mali','Mauritania','Mauritius','Morocco','Mozambique','Namibia','Niger','Nigeria','Rwanda','São Tomé & Príncipe','Senegal','Seychelles','Sierra Leone','Somalia','South Africa','Sudan','Eswatini','Tanzania','Togo','Tunisia','Uganda','Zambia','Zimbabwe','Afghanistan','Bahrain','Bangladesh','Bhutan','Brunei','Cambodia','China PR','Chinese Taipei','Guam','Hong Kong','India','Indonesia','Iran','Iraq','Japan','Jordan','Kazakhstan','Korea DPR','Korea Republic','Kuwait','Kyrgyzstan','Laos','Lebanon','Macau','Malaysia','Maldives','Mongolia','Myanmar','Nepal','Oman','Pakistan','Palestine','Philippines','Qatar','Saudi Arabia','Singapore','Sri Lanka','Syria','Tajikistan','Thailand','Turkmenistan','United Arab Emirates','Uzbekistan','Vietnam','Yemen','American Samoa','Australia','Cook Islands','Fiji','New Zealand','Papua New Guinea','Samoa','Solomon Islands','Tahiti','Tonga','Vanuatu','Gibraltar','Greenland','Dominican Republic','Estonia','Created Players','Free Agents','Rest of World','Timor-Leste','Chinese Taipei','Comoros','New Caledonia'
]
_EXTRA = {219: 'Kosovo'}


def nationality_name(value) -> str:
    try:
        nation_id = int(value)
    except (TypeError, ValueError):
        return 'Unknown nationality'
    if 0 < nation_id < len(_NATIONS) and _NATIONS[nation_id]:
        return str(_NATIONS[nation_id])
    if nation_id in _EXTRA:
        return _EXTRA[nation_id]
    return f'Nationality ID {nation_id}'
