# FC27 Academy Engine v1.24.24 — Starting-PlayStyle queue and settings timing

- **One starting plan per player.** The starting-PlayStyle queue is kept per save slot and is not rolled back
  with the save. When a player is found afresh (reload after quitting without saving, rewind, deleted engine
  data) his unwritten queued entries that are not in the new plan are marked `SUPERSEDED_REPLANNED` instead of
  being stacked with the new plan. Entries already being written (STAGED) and other players are untouched; the
  lifetime cap is still enforced at write time.
- **Settings re-read every checkpoint** for the career that is now active, before any player is found, so a
  save switch can't apply the previous save's PS+ eligibility rate during the 1 s settings cache window.
