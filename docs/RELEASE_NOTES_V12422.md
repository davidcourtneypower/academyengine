# FC27 Academy Engine v1.24.22 — Generation settings, settings never roll back

## New player generation settings (players found after the change only)
- **Starting PlayStyles** (−2 … +2, step 0.5, default 0): average extra/fewer starting PlayStyles for newly
  generated players. +0.5 gives half of them one more (deterministic per player). FC27-native styles are
  never removed; a new player still starts with at most 5 and never above his lifetime cap.
- **Lifetime PlayStyle cap** (−2 … +2, step 0.5, default 0): shifts the ceiling for newly found players,
  kept between 1 and 7 and never below what the player already has. Stored with the player's policy, so
  tracked players keep their cap. (A lower cap can also make PlayStyle+ eligibility rarer: it needs a cap of 4+.)

## Settings belong to the career
- Previously each save *branch* had its own settings file, and a branch switch (reloading after quitting
  without saving, loading an older save of the same career) could bring back that branch's older settings.
- Now every branch of one FC27 save shares one settings file, so Apply changes is final until you change it
  again. On first use the most recently changed branch file seeds it. A different save slot (Save As)
  inherits a copy once.
- Settings page explains this: settings stay even if you quit without saving; players already found keep their values.

## Overlay
- Player list header: NEXT PS (was NEXT PLAYSTYLE).
- Negative decimal settings display and step correctly (−0.5 previously showed as 0.5); typing "-" starts a negative value.
