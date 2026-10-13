# FC27 Academy Engine v1.24.16: reading base player names

Builds on v1.24.15 (controller focus fix, LT/RT, ring cursor); no data reset needed.

## What the v1.24.14 diagnostic showed

- `playernames` records are 12 bytes:
  - a 32-bit `name` value (`FFFFFFFF` = no name);
  - the 16-bit `nameid`;
  - the 16-bit `commentaryid`.
- The `name` field is t3db type 13. Live Editor's Lua table code only reads types 0 (text),
  3 (integer) and 4 (decimal), and returns nothing for type 13. That is why all 43,066 rows
  were visited but no name was stored.
- The `name` values increase in small steps (552, 559, 569, 578 for IDs 1–4). That suggests
  they are offsets into a separate pool where the text is stored.

## Change

- The runtime reads each row's 32-bit offset itself.
- It then looks for the pool. Two candidate locations are tested: just after the record array,
  and the pointers in the table's own header. A candidate is only accepted if the text at
  consecutive offsets is well-formed and each string's length exactly matches the gap to the
  next offset. Both NUL-terminated and length-prefixed text are tried.
- If a pool is found, names are read only for the IDs that generated players use, and cached.
  The Live Editor log shows:
  `FC27AE_STATIC_NAMES_POOL found source=… mode=… validated=…/…`
- If none validates, nothing is guessed. The log shows `FC27AE_STATIC_NAMES_POOL not_found`
  plus byte dumps of the table header and of the pool candidates. The text may be compressed;
  in-game Huffman compression is possible. Those dumps are what's needed for the next step.
- The base dictionary is now scanned once per game session, not on every full snapshot (about
  0.12 s each time).

All memory reads are small and fixed-size: the table header, the area just past the records,
and addresses the table header itself points to. They are only reads.

## Validation

- All regression scripts pass, plus the new `test_names_pool_v12416`. It runs Live Editor's own
  table iterator over a simulated memory image laid out like the logged one, and checks:
  - NUL-terminated pool: found and validated, and every name resolves by ID;
  - length-prefixed pool: found and resolved;
  - unrecognised pool: reported as `not_found` with dumps, and no names invented.

Not performed: running in FC27. Whether the real pool is plain text is exactly what the next
log will show.
