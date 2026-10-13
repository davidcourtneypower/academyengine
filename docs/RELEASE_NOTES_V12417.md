# FC27 Academy Engine v1.24.17: decoding compressed base player names

Builds on v1.24.16; no data reset needed.

## What the v1.24.16 dumps showed

- The table header's pointer at +0x38 (`0xF8463338`) leads to a blob. The blob starts with a
  Huffman tree:
  - each node is two 16-bit children, e.g. `0200 0100 0400 0300 …`;
  - a leaf is stored as `00 <character>`, e.g. `00 39` is the character "9".
- The tree is 552 bytes, which matches the smallest name offset.
- The names follow straight after it. For example, name ID 1 at offset 552 is
  `07 | 47 0A AB EC C0 00`: a character count (7) followed by the compressed bits, which fill
  exactly the 7 bytes before the next name.
- That explains `not_found` in v1.24.16: it only looked for uncompressed text.

## Change

- The runtime reads the tree from the header's pointer and decodes names on demand.
- Two details aren't documented: which child is bit 0, and whether bits are read from the
  high or low end of each byte. All four combinations are tested against 30 consecutive names.
  A combination is accepted only if decoding exactly the stored number of characters ends in
  that name's last byte and produces printable text.
- On success the Live Editor log shows:
  `FC27AE_STATIC_NAMES_POOL found … mode=HUFF variant=… validated=…/… examples=Name|Name|…`
- On failure nothing is guessed, and the log adds dumps of the tree and of the first string.

## Validation

- All regression scripts pass, plus the new `test_names_huffman_v12417`. It builds Huffman
  blobs in this exact layout, in all four variants and including UTF-8 accented names. The
  runtime picks the right variant each time and resolves all 35 test names by ID. A corrupted
  pool is rejected without guessing.
- The format is inferred from about 100 logged bytes. It is not a documented specification,
  and decoding has not yet been seen working on real game data.
