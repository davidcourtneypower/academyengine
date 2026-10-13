# FC27 Academy Engine v1.24.18: name decoding, character-count fix

Builds on v1.24.17; no data reset needed.

## What the v1.24.17 log showed

- The Huffman layout was right, but the pool still came back `not_found`:
  - with bits read from the high end and child 1 as bit 0 (`MSB`), 26 of 30 test names
    validated;
  - the other three bit/child orders managed 14, 5 and 5 of 30;
  - acceptance needs 29 of 30.
- The tree dump includes a leaf for byte `0xC3`, the first byte of UTF-8 accented letters
  (é, ü, ç and so on). So the stored count is most likely a count of **characters**, while
  v1.24.17 counted **bytes**. A count of bytes stops decoding one byte early on every accented
  name, which would explain 4 failures out of 30.

## Change

- Decoding can now count UTF-8 characters: a multi-byte letter counts once and its follow-on
  bytes are consumed.
- Validation tries both counting conventions for each of the four bit/child orders, and still
  requires 29 of 30 exact matches before anything is used.
- If a combination gets at least half right but isn't accepted, the log adds one
  `FC27AE_NAMES_DIAG huff_near_miss` line. It shows the decoded examples and up to four
  failing strings (offset, gap, stored count, bits used, partial text), so any remaining
  mismatch is visible straight away.

## Validation

- All regression scripts pass. `test_names_huffman_v12418` (renamed from v12417) now covers
  4 bit/child orders × 2 counting conventions, all identified by validation. All 35 test names,
  including accented ones, resolve by ID; corrupt pools are rejected; the near-miss line is
  exercised.
- This is still inferred from real data rather than documented. The next log will show
  `found … variant=MSB_UTF8` if the inference is right.
