# FC27 Academy Engine v1.0.4 — Overlay text, and checks on v1.0.3

- **PlayStyle and role names no longer run into each other** in the Players list. Names were
  placed at a guessed 7 pixels per letter, which is narrower than FC27's font, so longer names
  overlapped the next one ("Whipped Pass,Incisive Pass,"). Every name is now measured with the
  font it is drawn in. A name wider than its whole column (for example "CB Ball-Playing
  Defender+") breaks onto a second line instead of being cut off. Tooltips are sized the same way.
- **Deleting a career's engine data now remembers who its players were.** In v1.0.3 every player
  of a rebuilt career was treated as already known, so a new career that happened to reuse the
  same save ID would have got no starting PlayStyles at all. Now only the players the career had
  when its data was deleted come back as already known; anyone else is new as normal. A deletion
  made with v1.0.3 still works as before.
- **Less work while you play.** The launcher looks for Live Editor's log every 30 seconds. It now
  checks the remembered folder first and only searches again when that folder is gone.
- Checked, no change needed: Live Editor's heartbeats do not bring the deleted data back or end
  the "rebuilt at the next in-game day or save" state early. Until that next day or save the
  overlay shows the career as loading, so its controls are unavailable for that short time.
