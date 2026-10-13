# v1.24.06 progression and throughput audit

## Own signed academy players
No user-team penalty was found in the progress formula or the club-to-club development gate. A test changing only club identity gives exactly equal PS progress for equal attributes, DNA, player ID and checkpoint. This does not reproduce the user's save: slower real progress may reflect smaller relevant native attribute gains, cooldowns, lifetime eligibility or chance-based passive training. Role progression currently requires observed native attribute gains; roles have no passive training opportunity. Processing ceilings control awards/starting profiles, not progress accumulation. Match results/minutes/ratings are not inputs to this inspected PS planner.

## Changes
- Previously normal PS candidates consumed the shared bundle capacity before PS+, roles and newgen starting styles. All validated candidates are now selected through rotating family slots and per-family player cursors, with existing user-team priority retained. Every role's matching fields stay in one atomic group. Existing family and total limits remain enforced.
- Fixed grouped newgen queue rows not being marked STAGED when only queue_ids was populated.
- Unresolved non-user names previously received one direct resolver attempt per game session. A transient failure became permanent for that session. They now receive bounded oldest-attempt-first retries; successful names remain cached. Actual names require Live Editor to return valid metadata; placeholder elimination cannot be guaranteed offline.
- STATUS now describes active PS/PS+/role lanes, explicitly pauses free agents/missing players, and does not call an empty ledger Developing. PS-specific detail remains independent. Ready PS+/role lane labels distinguish gate holds.
- Completed PS/PS+ paths no longer calculate training gains or append zero-increment history while awaiting acquisition. Owned PS+ paths are skipped. Role evidence only accrues for upgradeable Role+ fields and stops at 100%; Role++ fields are excluded.
- Fixed GK PS+ target field selection for preferredposition1=0.

## 100% does not guarantee an immediate award
Completion enters acquisition validation. Cooldowns, position/attribute plausibility, lifetime caps/PS+ eligibility, unobserved/free-agent status, shared throughput and pending/unresolved transactions can still hold it. Raising 50/64/40/12/12 settings does not override these rules. Normal, plus, role and newgen family limits are ceilings; the shared total counts database fields. One role may consume several fields. The scheduler addresses fixed-order starvation but does not bypass eligibility or receipt safety.

## Processing and stored history after awards
Normal PS acquisition stops that normal path; the owned style may start a separate PS+ path if eligible. PS+ and Role++ completion stops their upgrade path. Historical entries remain for drill-down; normal/plus per-path histories are bounded at 12 entries, role per-path histories at 48, and the checkpoint-ingested player history at 96. Players still need snapshots and state comparisons for other paths, transfers, identity/lifecycle and native changes. Transaction manifests, event logs and save restore points are separate persistence mechanisms: this patch does not claim to bound total disk use.

## Longer-term performance priorities (not implemented here)
1. Measure snapshot, ingest, audits, read-model publishing and rendering separately. Existing audit timing is aggregate; add per-stage/player-count measurements before changing rates.
2. Share decoded styles, roles, lifetime slots and attribute fit across audit passes rather than repeatedly walking/recomputing the same world.
3. Update only changed rows in the SQLite read model and commit the whole checkpoint in one transaction; it currently deletes and rebuilds rows for the active world.
4. Use checkpoint-wide settings/constants and dirty-player sets; retain explicit invalidation for date/cooldown changes, club moves, new generations and settings edits.
5. Separate diagnostic reports from required acquisition checks; lower the frequency of broad diagnostics while keeping award safety checks current.
6. Incremental or batched durable state writes with checkpoint recovery, keeping save rollback anchors and write receipts transactional.
7. Compact resolved queue/manifests and archive older diagnostics under an explicit retention policy; preserve acquisition records and save anchors needed for rollback/history.

Already batched: multiple verified awards share one Lua changeset, newgen starting styles share one additive bitfield write, and matching role fields are atomic. More batching must preserve branch identity, compare-before-write guards, receipt acknowledgement and rollback semantics.

## Installation and testing
Close Academy Engine and restart FC27/Live Editor before loading the replacement runtime: the resident adapter intentionally refuses a second registration in an already active game process. Extract the complete build to a new folder and use its launcher. Keep existing data/settings; no factory reset is required. Use the included v1.24.06 runtime when the established installation requires a manual Lua run.
Offline regression results are in BUILD_VALIDATION.txt. Name resolution, visual column fit and live acquisition must be checked in FC27.
