# FC27 Academy Engine v1.24.06 code audit

This release is the post-v1.24 clean architecture. The shipping tree was audited from the active entry points (`run_manager.py`, `run_bridge_service.py`) and the v1.24 regression tools.

## Removed in this pass

- Pre-v1.24 migration/import and old-storage discovery paths.
- Obsolete youth-generator, potential, attribute, ageing, miniface, portrait and appearance-generation modules.
- Old adapter/contracts and standalone sync/test handoff code.
- Test-only write/restore transaction helpers.
- Unused backup/export helpers.
- Obsolete settings presets and generation/miniface/safety settings that had no active production consumer.
- Unused Pillow/OpenAI dependencies from removed portrait/miniface features.
- Generated native import libraries and Python bytecode caches from the shipping package.
- Hard-coded Live Editor data-folder guesses; arbitrary locations are now handled by saved user selection, Live Editor registry data, a self-contained install when valid, or the launcher's Browse controls.

## Intentionally retained

- Current JSON IPC between Lua, Python and the external overlay.
- Current per-branch world/event/settings JSON files.
- SQLite transactional snapshots/checkpoints/read generations.
- Save-aligned rollback/reconciliation logic.
- Current diagnostics/audit modules used by the production bridge.
- PlayStyle/PlayStyle+/Role progression, acquisition and verified-write logic.

## Storage

All Academy Engine-owned runtime and persistent state is below:

`%LOCALAPPDATA%\\FC27AcademyEngine\\`

The Lua/Python/overlay bridge is:

`%LOCALAPPDATA%\\FC27AcademyEngine\\runtime\\bridge\\`

No Academy Engine runtime data is stored in `%TEMP%`.
