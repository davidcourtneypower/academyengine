# FC27 Academy Engine v1.0.2 — Simpler Live Editor setup

- The **Live Editor locations** section (folder pickers) is removed from the launcher. It stayed on
  screen whenever the Live Editor program folder was not detected, even though only the data folder
  is needed and that one had been found.
- Until Live Editor has been found, the bridge line now reads: "Live Editor bridge: not set up yet.
  Start FC27 through Live Editor at least once so Academy Engine can find Live Editor and connect to
  it. This is detected automatically." Detection retries every 5 seconds (it used to retry several
  times a second) and stops once Live Editor is found; the location is remembered.
- Once found, the line reads "Live Editor bridge: ready" with the folder in use.
- The player README is updated to match.
