# FC27 Academy Engine v1.24.32 — Face picker

- **Change face** (Player Details header, or click the face itself) opens a picker over the page:
  - Regions on the left, most likely for the player's nationality first; women see their `WF` regions.
  - A page of faces sized to the overlay window (up to 60), with Previous / Next or the mouse wheel;
    scroll the region list with the wheel over it. Opens on the page holding the current face.
  - The current face is outlined in green; faces other players already have are marked "In use"
    (they can still be chosen).
  - **Automatic face** returns the player to the engine's own choice (the same face as before).
  - Close, Esc or controller B closes the picker.
- A pick shows straight away in the header ("Your choice (saved at the next checkpoint)"). It waits in
  `face_choices.json` beside the career's world file, because only the bridge writes the world, and the next
  checkpoint saves it with the career as `source: "user"`. The engine never replaces your choice unless FC27
  reuses that player ID for someone else.
- Picks of files that are not in your face library are refused; a pending pick for a player ID now held by
  someone else is dropped.
- Developer aid: `tests/native/snapshot_main.c` + `gdi_log.c` and `tools/render_overlay_snapshot.py` draw
  an overlay frame from a real state file without Windows.
