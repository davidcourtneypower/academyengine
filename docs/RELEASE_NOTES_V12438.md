# FC27 Academy Engine v1.24.38 — Cleanup before a public release

No gameplay changes. Existing careers and settings carry over; no reset is required.

- **Faster checkpoints.** Three calculations left over from earlier testing ran on every checkpoint and fed
  only log lines: a "dry run" preview, a top-progress list and a season check whose result nothing used.
  They are removed. In a 3,000-player test the engine's own work per checkpoint fell from about 550–690 ms
  to 155–225 ms, and the whole checkpoint by about 10%.
- **Less Live Editor logging.** The v1.24.13 crash tracing (every career event logged) now runs only for two
  minutes around a career load, save switch or exit. Before, every save restarted a five-minute window, so
  it could be on almost all the time. The one-off v1.24.20 squad diagnostic is removed.
- **Logs stay bounded.** `bridge.log` now also rotates at 5 MB during a session (before, only at start-up).
  `overlay_host.log` and `bridge_startup.log`, which grew forever, are capped at 2 MB (one old copy kept).
- **Debug / stress-test mode hidden.** The setting no longer appears and is treated as off. A career that had
  it switched on returns to the normal ranges (speeds up to 10×, normal throughput limits) the first time its
  settings are shown. Developers can still use it with the FC27AE_DEBUG=1 environment variable.
- **Clean release package.** `tools/make_release.py` builds the public zip from an allowlist: only the files
  the mod needs at run time (no tests, developer tools, internal documents, debug symbols or Python caches).
  Compiled Python caches are no longer stored in the project.
