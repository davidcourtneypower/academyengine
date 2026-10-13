# FC27 Academy Engine v1.24.19: base player names, acquired development paths

Builds on v1.24.18; no data reset needed.

## Base player names

The v1.24.18 `huff_near_miss` line showed the decoder works on real data. It decoded
"A. Abdallah", "A. Abqar", "A. Al Ganehi", "Aćimović", "A. Alarcón" and "A. Alaadin". Two
details remained:

- The stored count is **bytes**, not characters ("Aćimović" has count 10).
- When a name's bits end exactly on a byte boundary, the game stores one extra empty byte:
  "A. Alaadin" uses 48 bits but has a gap of 8 bytes, not 7. v1.24.18's check rejected those.

v1.24.19 accepts that extra byte. It now scores every decoding combination and picks the best,
still requiring 29 of 30 exact matches. Expected log line:
`FC27AE_STATIC_NAMES_POOL found … variant=MSB_BYTES … examples=…`.

## Development stops at the lifetime caps (already the case; now tested)

- The planner already skips:
  - normal PlayStyle paths once a player has reached their lifetime cap;
  - PlayStyle+ paths for players who aren't eligible or already have a PS+;
  - normal progress on PlayStyles the player already owns;
  - finished (100%) Role++ paths.
- A skipped path costs only a dictionary lookup, so it isn't a performance concern.
- New `test_v12419` checks each case.
- The "3.4% after promotion" case: the starting PlayStyle is staged on the first snapshot but
  only written into FC27 at the next day or save event. That day's development ran before the
  write landed, while the style wasn't owned yet, so it added progress. After the write, no
  further progress was added. The display fix below covers it.

## Player details → Development

- Acquired PlayStyles, PlayStyle+ and Role++ now show **100%**, keep the "Acquired" badge,
  and their names use the section's own colour instead of green.
- The description says how and when the path was obtained, taken from the player's events:
  - "Starting PlayStyle assigned by Academy Engine when the player was first tracked (new
    generation or promotion to a club squad)", with the date;
  - "Developed by Academy Engine", with the date;
  - "Already owned in FC27 when Academy Engine began tracking this player".
  Starting PlayStyles assigned before v1.24.12 created no event, so they show as already owned
  in FC27.
- PlayStyles the player owns with no Academy Engine path (from FC27 itself) are now listed
  too. Developing paths come first and acquired ones after.
- The development history of an acquired path ends with an "Acquired" entry giving the source
  and date.

## Validation

- All regression scripts pass, plus:
  - `test_v12419`: the cap behaviour, and the Development rows and history built from a real
    exporter run;
  - `test_names_huffman_v12419`: adds the extra byte at a byte boundary, and the real cases from
    the log.
- DLL rebuilt: acquired names are no longer green; history shows "Acquired".
