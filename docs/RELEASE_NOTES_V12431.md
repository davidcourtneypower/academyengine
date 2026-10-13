# FC27 Academy Engine v1.24.31 — Player faces and gender

- **Gender** is read from FC27 for every tracked player (players.gender, read defensively) and shown in
  Player Details.
- **Player faces** (Settings > Player faces, off by default; folder chosen in the launcher):
  - Point the launcher at your regen-face folder: one folder per region for men, `WF\<region>` for women.
    PNG, JPG, WEBP, BMP and DDS are read; nothing is copied or changed. The folder index is cached and
    refreshed when a region folder changes.
  - Each tracked player gets a face matched to nationality and gender using a weighted nationality→region
    table for every FC27 nationality (e.g. Republic of Ireland: mostly Irish faces, some Anglosphere, a small
    Afro-Caribbean/West African share), plus a 3% share spread over all regions for mixed heritage.
    Missing regions fall back along a chain (e.g. Japan → Korea → China), then to the region's family
    (e.g. women's `WF\European`).
  - Choices are deterministic per career, avoid repeats within a career, are saved with the career's world
    file, and are redone when FC27 reuses a player ID for someone else. A face picked by the user (picker
    comes next build) is kept.
  - `face_regions.json` in the Academy Engine data folder can override weights per nationality.
- **Overlay**: the selected player's face appears in the Player Details header (cached 96 px copy).
- **Experimental in-game faces** (off): writes DXT5 256 px minifaces to Live Editor's
  `mods\legacy\data\ui\imgAssets\heads` and `youthheads` as `p<playerid>.dds`, mirroring the loaded career.
  Only files the engine wrote (tracked by content hash) are ever replaced or removed; your own minifaces are
  left alone. Live Editor 27.1.x does not yet show minifaces for generated players in-game.
- Pillow is now a requirement (installed automatically on the next launch).
