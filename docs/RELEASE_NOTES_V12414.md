# FC27 Academy Engine v1.24.14: names diagnostic, controller improvements

Builds on v1.24.13 (all its fixes included); no data reset needed.

## Names diagnostic (no behaviour change)

The v1.24.13 log showed `FC27AE_STATIC_NAMES loaded=0 rows=43066 ok=true`. All 43,066 rows
of the base name dictionary are now visited, but no names were stored, and nothing was
logged as an error.

Once per game session, the runtime now logs `FC27AE_NAMES_DIAG` lines (about 15, read-only):

- the table layout: record size, record count and the `nameid` / `name` field definitions;
- how many rows had a numeric ID, a non-empty name or no name;
- the raw values and bytes of the first five rows;
- the same for `dcplayernames`, which does resolve names, as a known-good reference;
- lookups for the name IDs from your earlier unresolved-name samples.

**Please send the Live Editor log after loading a career.** These lines should show exactly
why the names don't read.

## Controller

- **Ring cursor:** while the pad is moving the pointer, the overlay shows a console-style ring
  instead of the arrow. Moving the real mouse brings the arrow back.
- **LT / RT switch sub-views:**
  - Player details: Overview → Development → Timeline (wraps round).
  - Events tab: All → PlayStyles → PlayStyle+ → Role++.

  A trigger acts when you release a quick tap. If it's held together with another button, or
  used in the open combo (e.g. `VIEW+LT+RT`), it does nothing.
- **Launcher:** the controller toggle and open combo now sit on the same row as Hotkey and
  Theme.

## Validation

- All regression scripts pass, plus three new tests:
  - `test_controller_v12414`: the real overlay source built natively. It checks:
    - the ring mask;
    - that the ring appears with stick movement and is kept over the overlay;
    - that the arrow returns after a real mouse move;
    - LT/RT cycling on the player-details pages and event filters;
    - no switch when a trigger is held with another button or used in the combo.
  - `test_names_diag_v12414`: the diagnostic against Live Editor's own table code, reproducing
    `loaded=0`.
  - `test_detail_reload_v12413`.
- DLL and host rebuilt. New imports: `CreateCursor`, `SetCursor`.

Not performed: Windows, FC27 or physical-controller testing.
