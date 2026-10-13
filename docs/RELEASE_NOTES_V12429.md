# FC27 Academy Engine v1.24.29 — Settings, filters and paging

(Includes v1.24.28: the career is detached when FC27 returns to the main menu.)

## Debug / stress-test mode
- Development speeds (PlayStyle, PlayStyle+, Role++) up to 100× (normally 10×); PlayStyle and PlayStyle+
  progress targets down to 10 (normally 50 / 100). PlayStyle+ is still never below the PlayStyle target.
- Turning debug off brings speeds, targets and throughput back into their normal ranges.

## Settings page
- Protected values listed at the top; the separate protected-rules section is gone.
- Each section can be hidden/shown from its header and has its own colour.
- No "Recommended" for UI theme and overlay hotkey; Controller support default shows "On".
- "NO PENDING CHANGES" / "N UNSAVED CHANGES" in capitals.

## Player list and Events
- OVR and POT filters are multi-select (e.g. 60-64 + 80+); the query ORs the chosen ranges.
- 100 rows per load (up to 1000); the next 100 load silently as you scroll — no FILTERING card, and nothing
  is requested at the real end of the list. "Load more" replaced by "Back to top".
- RESET FILTERS is always orange.

## Player details
- Current development status shown as plain text; CURRENT PLAYSTYLES heading in blue; count reads "x / y PlayStyles".
- Development: "PLAYSTYLE PATHS"; a player not eligible for PlayStyle+ shows just "Not eligible" in red.

## Progress bars
- The blue band (50–74%) is now white, with dark text on it.
