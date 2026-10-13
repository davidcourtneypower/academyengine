# FC27 Academy Engine v1.24 architecture (current to v1.24.37)

## Process boundary

FC27 hosts only the Live Editor Lua game adapter. Academy Engine UI code is never injected into FC27.exe.

`AcademyOverlayHost.exe` is one small C program (plain GDI) built from `academy_overlay.c`; until v1.0.5 a Go host loaded the same code as `AcademyOverlay.dll`. The renderer follows the FC27 window using the PID published by Python and exchanges state/commands through the canonical runtime bridge.

## Canonical storage

`%LOCALAPPDATA%\FC27AcademyEngine`

- `engine_data\academy_engine.sqlite3` — lifecycle, game snapshots, checkpoints and read generations.
- `engine_data\academy_state` — current branch world state (one world file per branch; `face_choices.json` beside it holds pending face picks).
- `engine_data\events` — current branch event state.
- `config` — Academy settings.
- `cache` — rebuildable read-model cache.
- `face_cache` — rebuildable overlay face thumbnails (BMP).
- `logs` — diagnostics.
- `runtime\bridge` — live Lua/Python/overlay IPC only.

No Academy Engine runtime state is stored under `%TEMP%`.

## Lifecycle

`NO_GAME -> CAREER_LOADING -> RECONCILING -> READY -> ADVANCING -> RECONCILING -> READY`

`DETACHED` invalidates the active read generation without deleting persistent career checkpoints. Returning to FC27's main menu detaches (v1.24.28).

## Save alignment

Academy checkpoints are keyed to career branch/date and stored transactionally. Reloading an older FC27 save restores the matching Academy checkpoint. Returning to a newer known save resumes its branch. Settings never roll back with a save.

## Write path

1. Each checkpoint, the engine updates per-player evidence (`playstyle_development_planner`, `role_progression_evidence`, `playstyle_decline`).
2. `production_scheduler` picks ready changes per kind with per-checkpoint limits (decline: `DECLINE_WRITES_PER_CHECKPOINT = 6`).
3. `live_playstyle_writer.stage_bundle` stages a changeset; `staged_sync.validate_change` checks every write family. Loss families `PLAYSTYLE_LOSS` / `PLAYSTYLE_PLUS_LOSS` must clear exactly one known bit.
4. Lua applies and verifies the writes and returns a receipt; `apply_receipt` commits engine state. Receipt replay is idempotent.

## Decline (v1.24.36)

`fc27_academy/playstyle_decline.py`. State in `player['engine']['decline']`. A personal start age is drawn once (hazard per birthday from 30, certain by 40; ELITE ≥85 and STRONG ≥80 bands start later). After it, each PlayStyle is judged on its attributes (`LOSS_ATTRS`; goalkeepers on GK attributes) against a peak; a sustained drop below the floor across several active checkpoints removes it or downgrades the PlayStyle+. Lost styles cannot be re-acquired unless the attribute recovers well above the floor. Switches `decline.playstyle_loss_enabled` and `decline.playstyle_plus_loss_enabled` (both off by default), `decline.decline_speed`.

## Retirement (v1.24.36)

`world_bootstrap_store.update_retirements`. A tracked player aged 33+ who is missing from trusted snapshots for 3 checkpoints and at least 7 career days is flagged retired, hidden from rows, read model and events, and trimmed after 2 seasons (policy keys, football DNA, face and decline history kept). An empty or shrunken snapshot is never trusted. A returning player is un-retired.

## Faces (hidden since v1.24.37)

`fc27_academy/faces.py`, `face_regions.py`, `academy_manager/face_render.py`, `face_sync.py`. Hidden by `FACES_FEATURE_VISIBLE = False`; `FC27AE_SHOW_FACES=1` shows it. While hidden, face settings read as off and face commands are ignored. Writing faces into FC27 (`face_ingame.py`) is experimental and off.

## Read model

The overlay receives only atomically published complete generations. Dashboard, players, progression, events, timeline and settings are not exposed piecemeal while a new career snapshot is being reconciled.
