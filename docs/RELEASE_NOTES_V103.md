# FC27 Academy Engine v1.0.3 — Deleting engine data, and leaving a career

- **"Delete current career engine data" now deletes everything for that career.** It used to
  remove only the current branch's files: the overlay kept showing the career from its cache, and
  the stored checkpoints and save anchors stayed, so loading an older save could bring the data
  back. It now removes every branch of the loaded career, its stored checkpoints, save anchors,
  game snapshots and overlay cache. Other careers and the career's settings are kept.
- **Straight after deleting**, the overlay shows the career as loading ("rebuilt from FC27 at the
  next in-game day or save") instead of the old data.
- **No second round of starting PlayStyles.** When the career is rebuilt, its players are treated
  as already known; only players who are genuinely new later get starting PlayStyles.
- **Returning to the main menu with Live Editor running as administrator.** Leaving a career is
  detected from Live Editor's log, which was only looked for in Live Editor's program folder. That
  folder is found from the running Live Editor process, which Windows hides when Live Editor runs
  as administrator and Academy Engine does not, so leaving a career went unnoticed and the overlay
  kept showing it. The log is now also looked for in Live Editor's data folders and remembered once
  found, and the launcher says when it cannot be found.
