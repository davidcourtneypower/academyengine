# FC27 Academy Engine v1.24.12: player names, controller support, install fix

Builds on v1.24.11; no data reset needed.

## Player names for generated players

The v1.24.11 diagnostic found the base name dictionary:
`FC27AE_NAME_TABLES playernames=-22470`.

Live Editor 27.1.0 reads every table's record count with `ReadShort` (signed 16-bit). Any table
with more than 32,767 rows gets a negative count, and Live Editor's iterator then stops after one
record. `playernames` has 65536 − 22470 = 43,066 rows, so almost every generated player fell
back to "Generated Player #id".

The runtime now corrects counts to their unsigned value before iterating any table, and reads
the base dictionary once per game session (`FC27AE_STATIC_NAMES loaded=…` in the Live Editor
log). This is verified against Live Editor's own `table.lua`; a copy is in `tests/le_reference`.

## Autorun installed where Live Editor never loads it

Today's logs still showed the v1.24.02 bootstrap. Live Editor's program folder also contains
`lua/`, so it was accepted as the data folder.

The launcher now:
- reads Live Editor's own log (`Load Config From …\le_config.json`) to find the real data
  folder;
- prefers folders that contain `le_config.json`;
- installs the bootstrap in every valid candidate folder. Only one copy ever runs.

It asks you to restart Live Editor if the bootstrap was updated while Live Editor was running.

## Controller support (XInput / Xbox-style)

| Input | Action |
|---|---|
| Open combo (default **L3+R3**) | Show or hide the overlay while FC27 or the overlay is focused |
| Left stick | Moves the mouse cursor |
| D-pad | Moves the cursor in fine steps |
| A | Click (hold to drag column edges) |
| B | Back (closes player details or a popup; at top level, closes the overlay) |
| Right stick | Scroll |
| LB / RB | Previous / next tab |

- Enable/disable and the combo are set in the launcher (any 2–4 buttons, e.g. `VIEW+RB`,
  `LB+RB+Y`, `VIEW+LT+RT`) or in the overlay's Settings tab (presets).
- XInput is shared, so FC27 also receives every press. The combo presets avoid common menu
  buttons. While the overlay is open it has focus, but whether FC27 ignores pad input while
  unfocused can't be verified here.
- PlayStation controllers work only through an XInput layer such as Steam Input or DS4Windows.

## Other fixes

- **Starting PlayStyles:** PlayStyles that Academy Engine assigns to a player it sees for the
  first time now create an event ("Starting PlayStyles assigned"). Player Details updates as
  soon as the write is confirmed. A youth player promoted into a club squad counts as seen for
  the first time. Set "newgen enrichment per checkpoint" to 0 to turn this off.
- **Dashboard:** the Developing PS+ and Developing Roles cards use the same blue as the others.
- **Icon downloads:** downloaded artwork is staged and moved into the watched folder in one
  batch, ending the per-icon overlay republishes (~50 ms every ~1.3 s in bridge.log).

## Validation

- All previous regression scripts pass. New tests:
  - `test_names_v12412`: Live Editor's real iterator; 43,066/43,066 rows after the fix;
    sample IDs from your log resolve.
  - `test_v12412`: controller settings, autorun discovery from Live Editor's log, the
    starting-PlayStyles event.
  - `test_controller_native_v12412`: compiles the real overlay C natively with Win32 stubbed
    and drives it with simulated pad input.
- DLL and host rebuilt; the DLL's XInput layout is checked at compile time.

Not performed: in-game runs, Windows runs, testing with a physical controller.
