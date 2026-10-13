# FC27 Academy Engine v1.24.21 — PlayStyle names, simpler overlay

## PlayStyles shown by name
- The player list PlayStyles column lists names, wrapping onto extra lines; a row grows to fit
  (e.g. 7 PlayStyles ≈ 5 lines / 132 px at the default column width) with the `n/cap PlayStyles` count beneath.
  Clicking and hover follow the variable row heights. Next PlayStyle / Next PS+ show the full name.
- Player details: PlayStyle / PlayStyle+ chips are text-only. Events use a small PS / PS+ / R++ badge.
- Removed the icon pipeline: `academy_manager/local_icons.py` (third-party download, BMP/SVG rendering),
  `tools/download_playstyle_icons.py`, `assets/playstyles`, the `ICONS` overlay block and the overlay's bitmap loader.
  Old `%LOCALAPPDATA%\FC27AcademyEngine\bridge\icon_bmp` / `icon_svg` / `assets\playstyles` folders are no longer used and can be deleted.

## PlayStyle+ eligibility locked at adoption
- Eligibility is decided once, when the engine first finds a player, with the multiplier in force then.
  Changing "PlayStyle+ eligibility chance" now only affects players found afterwards (v1.24.10–v1.24.20 re-scored everyone).
  Players already tracked keep their current eligibility.

## Removed
- Processing progress toast (and its Notifications setting) — the overlay's loading cards remain.
- Health tab. Tabs are now Dashboard, Players, Events, Settings (LB/RB wrap across four).
