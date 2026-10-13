# FC27 Academy Engine v1.0.1 — FC27 running as administrator

- **Fix for Live Editor running as administrator.** When FC27 runs as administrator and Academy
  Engine does not, Windows blocks the overlay over the game. The launcher used to only warn about
  it. It now shows **Restart Academy Engine as administrator**: one click, accept the Windows
  prompt, and the launcher, engine and overlay come back at the same level as the game.
- **Always do this when FC27 runs as administrator** (off by default) makes the restart automatic,
  including when the launcher is opened after the game. It is tried once per launcher session, so
  saying No at the Windows prompt never causes a loop; the button stays available.
- The restarted launcher waits for the old one to close before taking over, so the two never run
  side by side.
- Academy Engine still does not need administrator rights for anything else; run normally if
  Live Editor runs normally.
