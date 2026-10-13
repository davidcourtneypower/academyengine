# FC27 Academy Engine v1.24.37 — Faces hidden for now

- The face (miniface) feature is hidden from the launcher and the overlay: no Player faces card, no
  Player faces settings section, no face or "Change face" in Player Details, no face picker.
- While hidden it is off everywhere, even if it was switched on before: no faces are assigned, shown or
  written into FC27, and any minifaces the engine had written are removed from Live Editor's folders.
- Faces already saved with your careers (including ones you picked) are kept, so they come back if the
  feature is shown again. Gender is still recorded and shown in Player Details.
- One switch controls it (`FACES_FEATURE_VISIBLE` in fc27_academy/faces.py; developers and tests can
  use the FC27AE_SHOW_FACES=1 environment variable).
