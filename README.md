# FC27 Academy Engine v1.0.6

A Career Mode development engine for FC27. Players you track grow PlayStyles, PlayStyle+ and Role++ from how they actually play, within lifetime limits, and in later years can lose them again as they age. Everything runs outside FC27.exe: a thin Live Editor Lua adapter reads the game and makes verified writes, a Python engine decides, and an external overlay shows it all over the game.

See docs/RELEASE_NOTES_V103.md for the latest release. Players get release/README.txt instead of this file. Preserve existing engine data when upgrading; no reset is required. Developer orientation: docs/DEVELOPER_CONTEXT.md.

## Features (current)

- **Development** — PlayStyle, PlayStyle+ and Role++ progress from match evidence across checkpoints; progress, paths and history are visible per player.
- **New players** — starting PlayStyles queued for newly generated players, applied at the right time.
- **Lifetime limits** — a per-player cap on engine-added PlayStyles / PlayStyle+.
- **Decline with age** (v1.24.36, off by default) — each player gets a personal start age between 30 and 40 (later for better players); after that, sustained drops in the matching attributes remove a PlayStyle or downgrade a PlayStyle+. Two separate switches and a speed setting. At the cap, the cap shrinks with the loss.
- **Retirement** (v1.24.36) — players who leave the game for good (age 33+, missing across several checkpoints and at least 7 career days) are hidden completely; their data is trimmed after two seasons.
- **Save alignment** — checkpoints are keyed to the career branch/date; reloading an older save restores the matching Academy state.
- **Overlay** — dashboard, players list with filters (including Declining), player details with development and decline sections, events, timeline and settings; controller and mouse.
- **Faces** — built but hidden since v1.24.37 (`FACES_FEATURE_VISIBLE = False`; set `FC27AE_SHOW_FACES=1` to show it for testing). Saved faces are kept.

## Architecture

- FC27 + Live Editor Lua: thin game adapter for snapshots and verified writes.
- Python engine (`fc27_academy/`, `run_bridge_service.py`): authoritative progression, decline, retirement, events, reconciliation and transactional checkpoints.
- Launcher (`academy_manager/`, PySide6): setup, Live Editor location, settings, overlay export.
- External overlay (`native_overlay/`): `AcademyOverlayHost.exe`, one small C program (GDI) built from `native_overlay/source/academy_overlay.c`, outside FC27.exe.
- SQLite checkpoint journal: save-aligned rollback/resume and atomic read-generation publication.

See docs/ARCHITECTURE_V124.md.

## Storage

All engine-owned files use one root:

`%LOCALAPPDATA%\FC27AcademyEngine`

Runtime IPC is contained at:

`%LOCALAPPDATA%\FC27AcademyEngine\runtime\bridge`

No `%TEMP%` Academy Engine storage is used.

## Live Editor location

There is no fixed Live Editor install path. The launcher finds Live Editor automatically (the running Live Editor process, the registry and Live Editor's own logs) and remembers it in `manager_settings.json` under the Academy Engine root. Since v1.0.2 there are no folder pickers: until Live Editor has run once, the launcher asks the user to start FC27 through Live Editor and retries every 5 s.

## Clean architecture

This build contains no pre-v1.24 migration/import layer. Old generation/portrait engines, old adapter contracts, test write/restore handoffs, old backup/export helpers and unreachable legacy modules have been removed from the shipping tree.

## Version history

## v1.0.6 the overlay is one program

- AcademyOverlayHost.exe is built straight from the C overlay source: no DLL, no Go loader, no LoadLibrary (antivirus engines flagged the loader shape). See docs/RELEASE_NOTES_V106.md.

## v1.0.5 antivirus false positives

- Package install records removed from the bundled Python (VirusTotal took the download for the Pillow package); licences kept in runtime\licenses; overlay DLL and host carry Windows file details, host unstripped with a manifest. See docs/RELEASE_NOTES_V105.md.

## v1.0.4 overlay text, and checks on v1.0.3

- PlayStyle and role names are measured with the real font, so they no longer overlap; over-wide names wrap. Deleted careers remember their players, so only those come back as known. The log folder search is cheaper. See docs/RELEASE_NOTES_V104.md.

## v1.0.3 deleting engine data, and leaving a career

- Delete current career engine data removes every branch, stored checkpoints and the overlay cache; rebuilt players get no second starting PlayStyles; the main-menu log is found without the program folder. See docs/RELEASE_NOTES_V103.md.

## v1.0.2 simpler Live Editor setup

- No Live Editor folder pickers; the launcher asks to start FC27 through Live Editor once and finds it automatically. See docs/RELEASE_NOTES_V102.md.

## v1.0.1 FC27 running as administrator

- The launcher can restart Academy Engine as administrator (button, or automatically) when Live Editor runs FC27 as administrator. See docs/RELEASE_NOTES_V101.md.

## v1.0.0 first public release

- Internal build 1.24.39 released as version 1.0.0; no other changes. See docs/RELEASE_NOTES_V100.md.

## v1.24.39 release candidate packaging

- Windows release with its own Python (no install needed), trimmed Qt (~26 MB download), UNINSTALL.bat, a player README and third-party notices. See docs/RELEASE_NOTES_V12439.md.

## v1.24.38 cleanup before a public release

- Faster checkpoints (leftover diagnostic calculations removed), less Live Editor logging, bounded logs, debug / stress-test mode hidden, and a clean public release package. No gameplay changes. See docs/RELEASE_NOTES_V12438.md.

## v1.24.37 faces hidden for now

- The face (miniface) feature is hidden from the launcher and overlay and treated as off; saved faces are kept. See docs/RELEASE_NOTES_V12437.md.

## v1.24.36 PlayStyle decline and retirement

- Optional PlayStyle / PlayStyle+ loss with age (personal start 30–40, later for better players), visible on the Development page; cap shrinks at the cap.
- Retired players are hidden completely and their faces freed. See docs/RELEASE_NOTES_V12436.md.

## v1.24.35 face picker loading fixes

- 50 faces per batch; the current face is shown first instead of loading up to it; blank thumbnails in long lists fixed. See docs/RELEASE_NOTES_V12435.md.

## v1.24.34 face assignment speed-up

- First-time face assignment for large careers is much faster (region weights cached per library). See docs/RELEASE_NOTES_V12434.md.

## v1.24.33 face picker tweaks

- "Automatic face" closes the picker; "Load more faces" under the grid replaces paging; friendly region names. See docs/RELEASE_NOTES_V12433.md.

## v1.24.32 face picker

- "Change face" in Player Details opens a picker: regions most likely first, pages of faces, faces in use marked, "Automatic face" to go back.
- A pick shows at once and is saved with the career at the next checkpoint. See docs/RELEASE_NOTES_V12432.md.

## v1.24.31 player faces and gender

- Gender is recorded for every tracked player and shown in Player Details.
- Optional faces from your own regen-face library (men: one folder per region; women: `WF\<region>`), matched to nationality and gender, saved per career and shown in the Player Details header.
- An experimental writer for Live Editor minifaces is included but off by default. See docs/RELEASE_NOTES_V12431.md.

## v1.24.30 tidy-ups

- Event history can no longer be cleared; "PlayStyle(s)" wording; Settings "Misc" section; shared controller help; grey progress band.

## v1.24.29 settings, filters and paging

- Debug mode: speeds to 100×, PlayStyle/PlayStyle+ targets to 10; clamped back when debug is turned off.
- Settings: protected values at the top, collapsible coloured sections. OVR/POT multi-select; 100-row pages with Back to top.

## v1.24.28 detach on return to the main menu

- FC27 sends no event on exit to the main menu; the bridge now detects it from Live Editor's own log and detaches the career until the next load.

## v1.24.27 player list and details simplification

- Status column and legend removed; POS grey; PlayStyles / Next PS blue; events grey except the player name.
- No overview status line under the name; no development-history toggle for paths FC27 gave the player.

## v1.24.26 Role++ upgrades made by FC27

- FC27's own Role+ -> Role++ upgrades are recorded (history, "Upgraded by FC27" event, Development page) and do not start the Role++ cooldown.

## v1.24.25 player list, details and events polish

- Next Role column, status dots with legend, wrapped roles, two-row filters, free agents without a club.
- Player details: lane status chips, text PlayStyle lists, collapsible development sections.
- Events without the PS badge; statuses and event titles capitalised consistently.

## v1.24.24 starting-PlayStyle queue and settings timing

- A player found again replaces his unwritten starting-PlayStyle plan instead of stacking a second one.
- Settings are re-read for the active career at every checkpoint.

## v1.24.23 generation settings removed

- The v1.24.22 Starting PlayStyles / Lifetime PlayStyle cap settings are removed; per-career settings and the other v1.24.22 changes stay.

## v1.24.22 generation settings, settings never roll back

- New Generation settings: Starting PlayStyles and Lifetime PlayStyle cap (−2…+2), applied to players found after the change.
- Settings are stored per career (shared by every save branch), so reloading an unsaved or older point never restores older settings.
- NEXT PS header; negative decimal settings display correctly.

## v1.24.21 PlayStyle names, simpler overlay

- PlayStyles are listed by name in the player list (rows grow to fit) and details; the icon download/render pipeline is removed.
- PlayStyle+ eligibility is locked when a player is first found; multiplier changes only affect new players.
- Processing progress toast and Health tab removed.

## v1.24.20 cleanup, filters, wording

- Superseded name experiments removed; only the confirmed Huffman path remains.
- Read-only `FC27AE_SQUAD_DIAG` lines for young players' club links (squad-list visibility investigation).
- Status filter covers PlayStyle, PlayStyle+ and Role++ development and the lifetime PlayStyle cap; multi-select filter popups stage without their own apply (SEARCH applies); PlayStyle-count label fixed.
- PlayStyle / PlayStyle+ / Role++ spelled out where space allows; debug setting last; light normal icons on a dark tile.

## v1.24.19 base player names, acquired development paths

- Name decoding accepts the encoder's extra byte on byte-boundary strings (the last v1.24.18 mismatch).
- Development page: acquired PS / PS+ / Role++ at 100% with how and when obtained (starting PlayStyle on promotion, developed, or FC27); no green names; history ends with the acquisition.

## v1.24.18 name decoding: character counts

- The stored length counts UTF-8 characters (accented names were the 4/30 that failed); decoding now supports both conventions and logs near misses.

## v1.24.17 compressed base player names

- The base name pool is Huffman-compressed (tree + [count][bits] strings); the runtime decodes names on demand after validating the bit/child order against 30 stored strings.

## v1.24.16 base player names

- playernames.name is t3db type 13 (a 32-bit offset into a string pool), which Live Editor's Lua API cannot read; the runtime now reads the offsets and locates the pool by validation, or logs byte dumps if the pool is not plain text.

## v1.24.15 controller focus fix

- Opening the overlay with the controller combo now gives the overlay keyboard/controller focus, so the pad drives the overlay and FC27 no longer reacts to presses behind it.

## v1.24.14 names diagnostic, controller improvements

- Once-per-session `FC27AE_NAMES_DIAG` log lines to find why the base name dictionary yields no names.
- Controller: ring cursor while the pad drives the pointer; LT/RT switch sub-views (player details pages, event filters); launcher controller options on the main options row.

## v1.24.13 crash hardening and forensics

- Fixed player details staying on "Loading player details" when the same player is re-opened while the career data is unchanged (e.g. on match day).
- No game calls on menu/loading screen events unless a day capture is waiting; event trace with a NATIVE marker before every game call around loads, saves and exits.
- No idle timeout; while the bridge lease is lapsed, load boundaries are handled and days counted. Faster overlay publication for large careers.

## v1.24.12 player names, controller support, install fix

- Generated players get real names: Live Editor reads table sizes as signed 16-bit, so the 43k-row base name dictionary was skipped; counts are now corrected.
- Controller (XInput) support with configurable open combo; launcher installs the autorun into Live Editor's real data folder; engine-assigned starting PlayStyles appear as events; uniform blue dashboard cards.

## v1.24.11 career-exit crash, overlay and launcher fixes

- Quitting Career Mode no longer scans the game database during teardown (the crash at the save-selection screen); the overlay detaches and clears immediately.
- Native access only on settled in-career events; dashboard card overlap fixed; PlayStyle artwork recognised from free-form filenames; single launcher instance; Live Editor folder pickers hidden when auto-detected; elevation-mismatch warning; one-time name-table diagnostic.

## v1.24.10 progression evidence, performance and IPC reliability

- Development is credited from evidence (same branch, same runtime session, elapsed FC27 days) instead of the snapshot label. Mid-career Live Editor boundaries are logged and sent as `BOUNDARY_RESYNC`; in the 08-10-2026 session this moves credited growth from 15% to 99% of what was observed.
- About half the day-processing time removed; world file about 20% smaller.
- DNA aptitudes read on their real scale (average pace unchanged); all FC27 roles have evidence groups; newgen styles limited to FC27 bitfields; live PS+ eligibility multiplier.
- Windows sharing-violation retries everywhere; overlay commands queued per file and honoured while FC27 advances; Load-more button fixed; bounded snapshot/anchor/response storage; accent-insensitive search; verified exact-save restores.

See docs/RELEASE_NOTES_V12410.md for details, validation limits and install steps.

## v1.24.09 save-aligned rollback + progression history + overlay stability

- Added exact FC27 game-state fingerprints and transactional save anchors. Reloading an earlier FC27 save now restores the Academy state that belonged to that exact game state instead of retaining progression earned on an abandoned unsaved future timeline. This also covers same-date reloads where the calendar date alone cannot identify the rollback.
- Current v1.24 transactional snapshots/checkpoints can seed an exact save anchor when that game state was already observed before this release. No pre-v1.24 migration/import logic is reintroduced.
- Player Details -> Development now supports path drill-down. Click a normal PlayStyle, PlayStyle+ or Role++ path to inspect its recorded readiness changes/checkpoint history. Role readiness now records the same bounded path history used by PlayStyle/PlayStyle+.
- Player Details displays a dedicated LOADING PLAYER DETAILS indicator while the selected player's detail generation is being fetched/retried.
- Increased STATUS badges and progress bars to the same 30 px control height in player rows and development rows so status text is not vertically clipped.
- Fixed PS+ Status filter selection highlighting; the currently selected option is now visibly marked, matching the PS Count filter.
- Busy/filter/loading clicks and mouse-wheel input are swallowed while the busy card is active. The processing indicator stays pinned until the engine publishes READY/ERROR instead of disappearing into a blank overlay.
- Career advance shows an immediate REFRESHING CAREER DATA cue. If FC27 has announced a day advance but has not yet emitted a settled snapshot event, the cue no longer blocks the overlay indefinitely; the previous immutable generation remains browseable until the actual checkpoint arrives. Raw Live Editor event/request identifiers are not shown in user-facing processing text.
- Restored automatic acquisition of the real FC-style PlayStyle/PlayStyle+ artwork into `%LOCALAPPDATA%\FC27AcademyEngine\assets\playstyles`. Rendering remains offline-safe: generated fallbacks are used only until the real artwork has been cached. `tools\download_playstyle_icons.py` can manually retry missing artwork.
- Retains the v1.24 external-overlay architecture, consolidated LocalAppData storage, atomic read generations, generation-bound UI commands, host heartbeat recovery, settings keyboard entry, and receipt-gated FC27 writes.

No Academy data reset is required for v1.24.09. Fully exit FC27, Live Editor and Academy Engine before replacing the program files because the external overlay DLL/host changed.
