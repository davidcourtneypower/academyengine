# FC27 Academy Engine v1.24.10: progression evidence, performance and IPC reliability

This release addresses the 15 issues found in the v1.24.09 review, using the bridge.log and the
Live Editor log from the 08-10-2026 session. No Academy data reset is required.

## Why progression was under-credited

In that session, 43 of 57 snapshots were labelled `SCREEN_LOADED_BASELINE` while the career was
not being reloaded. Baselines credit no progress, and they carried **58,031 of 68,592 observed
attribute changes (85%)**. The Live Editor log shows the in-flight snapshot being dropped
without its response, which only happens on the silent load-boundary path (events 5/29) or the
`IsInCM()==false` path.

Replaying that session's snapshots through the new rule credits **99%** of the growth. The rest
came from snapshots in which no day had passed.

## Changes

1. **Growth is credited from evidence, not the snapshot label.**
   - Lua now logs `FC27AE_LOAD_BOUNDARY event=…`, `FC27AE_DETACH` and `FC27AE_REATTACH`. The
     next session's log will show which of the two causes it is.
   - Lua counts days that pass across a boundary or while detached. v1.24.09 dropped them.
   - A boundary inside a career that already has a baseline is sent as `BOUNDARY_RESYNC`.
   - Python credits growth on any snapshot when all of these hold:
     - the branch continues (no load, rewind, Save-As or exact-save restore);
     - the runtime session is the same;
     - at least one FC27 day has elapsed (or it is a day snapshot).
   - This also fixes growth being lost when it was first seen in a save snapshot.
2. **Day processing is faster.** On 7,240 synthetic players (Linux, unprofiled), a day takes
   2.0–2.9 s, down from 4.5–5.7 s. Changes:
   - The full deep copy of every player is gone.
   - Settings are cached instead of re-read from disk about 60,000 times per day.
   - Training rolls use one generator per player.
   - Unused progress metadata and the duplicated DNA copy were removed: the world file
     shrank from about 40 MB to 32 MB.
   - The just-written world is reused instead of re-parsed.

   Most of the removed work was file I/O, so the gain on Windows should be larger. That has not
   been measured.
3. **DNA is read on its real scale.**
   - Aptitude multipliers (0.65–1.35) are converted to the 0–100 scores the formulas expect. In
     v1.24.09 every player got the same flat factor of about 0.707.
   - Base rates are rescaled so the population-average pace from native growth is unchanged
     (2.387 vs 2.385 per attribute point). DNA now only shifts progress toward a player's
     strengths.
4. **Windows file locking.**
   - All 26 places that replace a file now retry briefly on a sharing violation.
   - The overlay opens its files with `FILE_SHARE_DELETE`.
   - A failed heartbeat write no longer stops the main loop.
5. **Clicks are no longer dropped while FC27 advances.**
   - Filter, selection and settings commands are tied to the career, not only to the exact READY
     snapshot, and are applied during ADVANCING. The overlay refreshes its view from the last
     processed data without marking processing as finished.
   - Commands sent mid-processing wait for it to finish.
   - Clear and delete actions still need the exact visible READY data.
6. **Roles.**
   - Evidence groups added for Falseback, Wide Half, Half-Winger, Half Winger, Wide Midfielder,
     Shadow Striker, Wide Back and False Winger.
   - "flair" now maps to attributes for role evidence.
   - Not done: granting brand-new roles. Writing a role ID into an empty `roleN` field has never
     been tested in FC27.
7. **The "Load 80 more" button works.** Clicks below the drawn rows no longer open a hidden
   player. The events list has the same fix.
8. **Command queue.** The overlay writes one uniquely named `overlay_cmd_<tick>_<seq>.txt` file
   per command via an atomic rename. Python processes them in order and still accepts the old
   single file.
9. **Storage is bounded.**
   - Snapshot journal: 120 per career.
   - Save fingerprints: 96 per career, keeping real saves first. They are now written only on
     real loads and saves, not on re-syncs.
   - `responses/` files are pruned after 15 minutes.
10. **Less process inspection.**
    - Command lines are read only for candidate processes.
    - FC27's loaded-module list is checked once per process when Live Editor is found; otherwise
      at most every 30 s.
11. **The database schema runs once per process.** A status read no longer opens a write
    transaction.
12. **Style rules and eligibility.**
    - Newgen starting styles come only from FC27's PlayStyle bitfields.
    - Training rolls once per elapsed day.
    - The PS+ eligibility multiplier now applies to existing players. Each player's fixed roll is
      kept, so eligibility is reproducible.
13. **Search ignores accents and case** ("muller" finds "Müller"; "odegard" finds "Ødegård").
14. **Exact-save restores are verified.** A save fingerprint is used only if its stored world
    really matches the loaded FC27 state; otherwise it is rejected and logged. Re-syncs consider
    only real save fingerprints, not the general snapshot journal. The bridge log now records
    exact-lookup, restore and crediting outcomes on each snapshot.
15. **Smaller fixes.**
    - The bundle log shows the real configured limits.
    - Version strings are unified to 1.24.10.
    - The Lua write loop has a nil check.
    - Mouse coordinates are sign-extended for column drags.
    - An oversized state file is skipped instead of parsed half-read.
    - Dead code was removed.
    - The bridge runs under console `python.exe` so its startup errors are logged.

## Validation performed

- All eight v1.24.06–v1.24.09 regression scripts pass. One fixture was updated:
  `test_progression_v12406` now sets the identity roll, because PS+ eligibility follows the live
  multiplier by design.
- New tests:
  - `test_boundary_resync_v12410`
  - `test_development_model_v12410`
  - `test_ipc_reliability_v12410`
  - `test_maintenance_v12410`
- The overlay DLL and host were rebuilt from the patched source with clang/LLD and Go
  (GUI subsystem and import table checked).

## Not performed

- Running anything in FC27 / Live Editor.
- Running the rebuilt DLL on Windows.
- Re-tuning progression rates. Because about 6× more observed growth now counts, careers that
  raised the speed multipliers will progress much faster. Reset them to 1.0, play a season and
  re-tune from the new logs.

## Installation

1. Fully close FC27, Live Editor and the old Academy Engine.
2. Extract this build and start its launcher **before** starting Live Editor. Confirm it reports
   the autorun as updated. Your 08-10 Live Editor log shows the installed autorun was still the
   **v1.24.02** bootstrap (`V12402_AUTORUN_ARMED`), which loads the runtime on event 68.
3. Keep existing engine data. The first snapshot after the upgrade is an offline re-baseline, as
   usual.
4. After a session, send the new `bridge.log` and Live Editor log. Look for `FC27AE_LOAD_BOUNDARY`
   / `FC27AE_DETACH` and `development_credited=` lines.
