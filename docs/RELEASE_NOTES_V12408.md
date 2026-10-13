# FC27 Academy Engine v1.24.08

All five agreed performance improvements are implemented. The progression rules,
award limits, cooldown lengths and player eligibility are unchanged.

1. **Incremental player-list storage.** Compare incoming rows with the existing
   career cache, batch writes for changed/new rows only, and delete only removed
   players. A complete incoming snapshot remains the source of truth. Player
   changes, settings-derived display values and career changes still refresh.
2. **Outstanding transaction index.** Recovery and staging use an in-memory index
   of pending manifests. Writes update it immediately. Startup rebuilds it from
   durable manifests; a 60-second metadata sweep catches external changes without
   reparsing unchanged completed records. Manifests and receipts remain the
   authority; an index is never used as proof of a game write.
3. **Earlier cooldown exits.** Each PS/PS+ lane checks its own cooldown before
   calculating gains. The development checkpoint counter, existing readiness,
   history, caps and independent PS+ lane retain their previous behaviour.
4. **Separate detailed path history.** PS, PS+ and role progression histories are
   immutable compressed records in the existing academy_engine.sqlite3 database.
   Worlds/checkpoints carry content references, so rewind and Save As select the
   correct historical version. Inline histories migrate on a successful world
   write. Records commit before references are published. Full evidence is loaded
   for the selected expanded path, rather than for every list refresh. The small
   operational player history remains inline for age/lifecycle/event bookkeeping.
   Existing limits remain 12 entries per PS/PS+ path and 48 per role path.
5. **Revision-driven overlay publication.** Full payloads refresh when relevant
   inputs change: world, career context, events, filters, selection, settings,
   icon assets, game process or lifecycle. Notification expiry has its own refresh
   deadline. Native UI checks file timestamps before reading unchanged payloads.
   The lightweight processing indicator and connection heartbeat remain active.

History maintenance runs at most daily after at least 60 seconds without snapshot
work. It removes only old unreferenced records, preserving all current worlds,
retained checkpoints, exact-save anchors, UI cache references and a one-day grace
for new records. Unreadable roots abort deletion. SQLite reuses freed pages.

## Validation

- Full load/growth/rewind/resume bridge replay produced identical hydrated player
  state and history to v1.24.07 at every checkpoint.
- 540 progression updates matched v1.24.07 across cooldown combinations, owned
  styles and deterministic training opportunities, including independent PS+.
- Actual receipt recovery after a simulated crash between world persistence and
  manifest completion produced one acquisition record and retained other PS progress.
- Save As, bounded-history migration, history retention, failed writes and missing
  references were tested in isolated state.
- The real exporter was tested with mocked game detection/assets: idle does not
  rewrite the payload; collapsed paths do not read history; expanding one path
  reads one history; expiry, detach and game exit refresh correctly.
- Native Windows x86_64 DLL rebuilt. Live FC27/Live Editor execution and native
  Windows visual validation remain to be performed on the user's system.

## Local synthetic measurements

For 5,032 unchanged player rows, five-run median cache sync was 71.60 ms in
v1.24.07 and 45.19 ms in v1.24.08 (about 37% lower in this microbenchmark). Player
row writes fell from 5,032 to zero. A one-row edit wrote one row; removals were
handled independently.

A deliberately history-heavy synthetic world (5,032 players, one 12-entry path
per player) shrank from 11,869,391 to 814,087 bytes in the frequently rewritten
world JSON. Its initial history migration took 169.08 ms locally. History was
moved to the database, not discarded; these figures are not total storage savings.
These Linux synthetic measurements do not predict FC27 frame rate or end-to-end
calendar processing time. Bridge logs include overlay publication timing.

## Installation and test focus

Close the engine, FC27 and Live Editor, extract this complete build to a new app
folder and restart. Use the matching v1.24.08 runtime if installing it manually.
Do not reset existing engine data. No new runtime dependencies are required.

Because this release changes history storage, keep a backup of the complete
%LOCALAPPDATA%\FC27AcademyEngine folder before first launch if you need to return
to v1.24.07. Older builds do not understand the new history references. Backups
must include academy_engine.sqlite3, not just generated_world.json.

Retest queued acquisition, filters/selection/settings, expanding individual
histories, Save As and loading an earlier save. Compare responsiveness at normal
processing limits before increasing them to debug maximum.
