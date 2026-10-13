# FC27 Academy Engine v1.24.11: career-exit crash, overlay and launcher fixes

Builds on v1.24.10; no data reset needed. Event IDs below come from Live Editor 27.1.0's
`lua/libs/v2/imports/career_mode/enums.lua`.

## Crash when quitting Career Mode

Cause, from the 08-10-2026 Live Editor log (09:11:13):

- Quitting fired event 2 (`TOURNAMENT_MODE_ACTIVATED`) with a different save UID.
- The runtime treated this as a "save switch" and then, after 146 (`HIGHLIGHTS_READY`), ran a
  full database scan while FC27 was tearing the career down (`SAVE_STABILIZED players=0`).
- Live Editor's next start is at 09:15, so the game had crashed. The 09:49 quit (event 68) took
  the same path.

Fix:

- Native game/database access is now allowed only on settled in-career events: 12, 13, 15–19,
  26, 27, 28, 53, 68 and 147. Match, sim, news and transfer events return before any native call.
- A save-UID change outside a hub (26), day (15) or save (28) event is treated as leaving the
  career:
  - all game access is held;
  - `LEFT_CAREER` is published, so the engine detaches and the overlay clears its data;
  - `FC27AE_CAREER_EXIT` is logged.
- Events 2, 3, 4, 6 and 30 (menus / career creation) quarantine immediately.
- Reloading the same save resumes as a re-sync; loading another career starts a fresh baseline.
- Toasts and processing cards are cleared whenever no career is loaded.

## Overlay

- **Dashboard cards:** the value, subtitle and progress bar no longer overlap. Before, the
  subtitle at y+78–96 overlapped the bar at y+90–100.
- **PlayStyle icons:** any image in `%LOCALAPPDATA%\FC27AcademyEngine\assets\playstyles`
  (subfolders included; PNG, WebP, JPG, BMP or GIF) is matched to a style by its filename, e.g.
  `Finesse Shot.png`, `finesse_shot_plus.png`, `PS_Long-Ball-Pass+.webp`. Exact manifest names
  are no longer required.

## Player names

Live Editor 27.1.0 does not register `GetPlayerName`, `GetTeamName` or `GetGameLocString`; none
of them appear in `FCLiveEditor.DLL`, and the v2 `players_manager:GetPlayerName` is a stub.
In-session logs also showed the base `playernames` dictionary missing (`static_names=0`).
Generated players reference that dictionary (e.g. firstnameid 34045 / lastnameid 5371), so only
players with an edited-name row (your academy, signings) resolve.

v1.24.11 logs `FC27AE_NAME_TABLES …` once per game session, listing which name tables exist with
their row counts, to decide the next step.

## Launcher

- **Single instance:** a second launcher brings the first to the front and exits.
- **Live Editor folders:** the folder pickers are hidden once both folders are auto-detected
  (running Live Editor process or its registry entry). They reappear only if detection fails.
- **Administrator rights:** not required. If FC27 is elevated and the launcher is not, the
  launcher now warns, because Windows then blocks the overlay from taking focus over the game.

## Validation

- All previous regression scripts pass. Also passing:
  - `test_career_exit_v12411`, which replays the logged quit sequence: no snapshot and no database
    access during teardown; same-save reload resumes; another career gets a fresh baseline.
  - `test_ui_v12411`: icon matching end to end, launcher guards, overlay card geometry.
- `test_boundary_resync_v12410` now settles on event 68 instead of 0, because unsettled events
  no longer touch the game.
- The native DLL and host were rebuilt.

Not performed: in-game runs, Windows runs of the DLL or launcher.
