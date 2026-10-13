# FC27 Academy Engine v1.24.07

## Changes

- Ready award handoffs are consumed before day/save event early returns. An outstanding snapshot blocks consumption until acknowledged, and load boundaries require a fresh baseline before writes.
- The eight-second adapter lease now pauses rather than permanently unregistering the runtime. A separate two-second heartbeat keeps synchronous engine processing from starving the lease. Unchanged runtime markers no longer repeatedly invalidate a completed read generation.
- Transaction identity guards cover selected players and no longer reject a handoff merely because overall rating grew. Expected field values, player identity, runtime session, branch and career checks remain enforced.
- Forward Save As hints retain the parent context. Validated child branches copy development state, event history and career settings. Exact-anchor restores inherit settings independently of world creation. Copied staged new-player queues return to queued because their parent transactions are not copied.
- Recovered committed receipts also produce acquisition events.
- Player details and settings clip scrollable content below fixed navigation. Development history expands beneath its own PS/PS+/role path. Dashboard and player list show separate active PS, PS+ and role counts.
- Icons preserve source colour/transparency, use separate regular/plus assets and use content-versioned BMP paths so the overlay reloads changed artwork. Missing artwork retains labelled fallback icons. This does not certify every remotely supplied icon as correct.

## Progression and performance answers

Own-club players have no blanket normal-PS speed penalty: equal evidence and player inputs produce equal progress in the regression. Individual attributes, DNA, caps and eligibility can produce different results. Free agents do not receive club-development awards. Zero-readiness paths are labelled accordingly; combined status and separate family counts avoid interpreting normal-PS status as the whole player.

Tracked generated-player attributes are read at settled career checkpoints after day advancement. Rapid simulation can coalesce days; this is event-driven, not a fixed wall-clock polling interval. Full discovery runs every seven career days and on save/load. The engine compares snapshots; it does not replace FC27 native attribute growth.

Completed/owned PS and PS+ paths and fully upgraded Role++ fields stop accumulating further evidence/history for that completed path. Players still need snapshot reconciliation and may have other eligible paths. Historical records remain available rather than being deleted on completion.

The adapter's eight-second heartbeat was a real timeout risk during expensive synchronous processing. Waiting can also mean career tables are still settling, a request has not been acknowledged, or a safe baseline is required. This release logs prolonged response waits without discarding outstanding work.

Longer-term performance candidates: profile large checkpoints; batch journal/read-model database writes into one transaction; update only changed player rows; defer nonessential history formatting to detail views; batch name resolution and asset downloads. Preserve expected-value checks and receipt boundaries around game writes. The present release batches production into verified bundles and keeps heartbeat work independent, but does not claim a measured overall speedup.

## Installing and testing

Extract the complete package to a fresh application folder. Close the old engine, FC27 and Live Editor before restarting with this version so the singleton Lua adapter is replaced. Preserve existing Academy Engine data; do not run RESET_ALL_ACADEMY_DATA.bat. The separate runtime Lua is identical to the bundled canonical runtime.

First retest the existing 100% queued player across settled career events and confirm an acquisition receipt/event. Then save the career into a new slot and compare settings and expanded path history. Check scrolling on settings/development and separate PS/PS+/role counts.

Offline tests and a Windows DLL cross-build pass. FC27/Live Editor execution, Windows visual rendering and the user's particular saved career were not available here. Already-lost history/settings are not automatically reconstructed. If an icon remains wrong, its exact PlayStyle name and a screenshot are needed to verify the remote asset mapping.
