# FC27 Academy Engine v1.24.28 — Detach on return to the main menu

## What the 09-10-2026 logs showed
- Exiting a career to FC27's main menu sends **no** Career Mode event. Live Editor does log
  `[LE::UnsupportedLeaguesManager::Load] Start` each time the main menu is entered (never during a career).
- Event 2 (TOURNAMENT_MODE_ACTIVATED), which earlier builds treated as "career exit", is actually the start
  of a career **load**: 2 -> 146/93 -> 29 POST_LOAD_PREPARE -> 26 ENTERED_HUB. That is why the earlier
  "exit then reload within 2 s" looked like FC27 reloading in the background — those were real loads.
- The save ID stayed the same across autosaves, saves and a save to a new slot: it identifies the career.

## Change
- The bridge tails the newest Live Editor log (`<Live Editor>\Logs\*.log`, new lines only, follows
  log rotation). On the main-menu line it detaches the career (overlay shows "Load a Career Mode save")
  and keeps it detached — even if a checkpoint finishes afterwards — until the Lua runtime reports the
  next career load. Logged as `FC27AE_MAIN_MENU source=LIVE_EDITOR_LOG …` in bridge.log.
- If the Live Editor folder can't be found, behaviour is unchanged.
