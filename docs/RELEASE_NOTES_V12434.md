# FC27 Academy Engine v1.24.34 — Face assignment speed-up

- Region weights for each nationality and gender are now worked out once per face library instead of
  once per player. Giving faces to a 2,000-player career for the first time drops from about 13 s to
  about 0.2 s when the library's folder names are not recognised (about 0.3 s to 0.1 s with the usual
  region names). Later checkpoints stay at about 5 ms. The picker's region list uses the same cache.
