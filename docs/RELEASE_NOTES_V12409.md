# FC27 Academy Engine v1.24.09 — save-selection startup hotfix

A concrete unsafe startup path was found after reports of crashes at career save
selection. The runtime called refresh_tables() and build_club_teams() at module
load, before its intended career readiness guard. The autorun bootstrap could
load that runtime on any career event. Lua pcall does not protect the game from
native access violations caused by unsafe database access.

Changes:
- Removed all module-level database acquisition/scans and deferred helper imports.
- Autorun ignores selection/loading/data-ready/screen-loaded events. It loads the
  runtime only on ENTERED_HUB_FIRST_TIME (26), DAY_PASSED (15) or PREPARE_FOR_SAVE (28).
- The runtime independently requires one of those trusted events plus a successful
  IsInCM check before querying save identity or database tables.
- Load boundaries (5/29) invalidate cached table handles and pending writes before
  making any native call. An arbitrary event count or event 27/68 cannot unlock a
  new career. Missing/failed career-context checks hold all native data access.
- The v1.24.08 performance changes remain included.

Validation: mocked Lua startup executes repeated selection/loading event sequences
with native calls forbidden; zero database, save-ID, context or helper calls occur.
Trusted hub/day attachment works; failed context checks hold access. Existing Lua
award handoff, lease recovery, load quarantine, syntax and progression/staging
regressions pass. Python compileall passes. Native overlay unchanged from v1.24.08.

This fixes a demonstrated unsafe code path consistent with the report. It is not
confirmation of the exact native crash cause without an in-game retest/crash log.

Installation:
1. Close FC27, Live Editor and the old engine completely.
2. Extract and launch the complete v1.24.09 build before starting FC27/Live Editor.
   Confirm the launcher reports the Live Editor autorun as ready/updated. The full
   package updates both the bootstrap and runtime_current.lua.
3. Preserve existing engine data; do not reset it.
4. Load the career. If the initial hub event was already dispatched before the
   resident handler registered, advance one day to establish the baseline.

Manual bootstrap replacement: copy the separately supplied autorun script to the
Live Editor data folder as lua/autorun/FC27_Academy_Engine.lua, replacing that file
rather than adding another autorun copy. The resident runtime is a separate file;
it must not replace the bootstrap in the autorun folder.

If the game still crashes, close the engine and move that Academy autorun file out
of lua/autorun, then restart FC27/Live Editor and try loading the same career. Report
whether the crash remains with Academy disabled and provide the Live Editor crash/log
output and Academy bridge.log. Do not reset or delete the career/save data.
