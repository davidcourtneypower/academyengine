# FC27 Academy Engine v1.24.20 — Cleanup, filters, wording

## Names cleanup
- Removed the superseded name experiments: per-player GetPlayerName / retry targets, NAME_TABLES probe,
  names diagnostic dumps, CSTR/PSTR pool modes, header-qword scan, UTF-8/LSB/swap Huffman variants.
- Kept only the confirmed path: edited/DC names, then the `playernames` Huffman pool (MSB, first child = bit 0)
  validated on 30 strings. Logs: `FC27AE_STATIC_NAMES_POOL`, `FC27AE_STATIC_NAMES`, METADATA `base_names=`.

## Squad visibility diagnostic (read-only)
- Once per session: `FC27AE_SQUAD_DIAG young pid=… link: field=value …` for up to 5 tracked players aged ≤16,
  and a summary of `teamplayerlinks` fields and players with more than one club link.

## Player list filters
- Status: All Development Statuses / Developing a PlayStyle / Developing a PlayStyle+ / Developing a Role++ /
  At lifetime PlayStyle cap.
- PlayStyle+ filter: Any PlayStyle+ Status / PlayStyle+ eligible / Not PlayStyle+ eligible / Has PlayStyle+.
- PlayStyle-count button now shows the selected option (`N+ PLAYSTYLE(S)`), not "PS+".
- Positions, PlayStyles and Roles: choices are staged as you tick them (no separate apply in the popup);
  DONE closes the popup and SEARCH still applies the filters. Saved views from older builds migrate.

## Wording
- PlayStyle / PlayStyle+ / Role++ spelled out on dashboard cards, summary chips, development page and lane text.
  Narrow table column headers stay abbreviated.

## Settings / icons
- Debug stress-test setting moved to the bottom of the settings page.
- Normal PlayStyle icons with light artwork are drawn on a dark tile (they were white-on-white); PlayStyle+ unchanged.
  Icon cache renamed (`_v8_`) so icons rebuild.
