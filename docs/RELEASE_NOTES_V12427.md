# FC27 Academy Engine v1.24.27 — Player list and details simplification

- Player list: STATUS column and the status-dot legend removed (progress bars show development);
  saved sort on the old status column falls back to Player.
- Player list: POS in grey; PlayStyles and Next PS in the overview blue.
- Player details: the development status line under the player's name is removed (the Current
  Development Status section shows it).
- Development page: no "Show development history" toggle for a PlayStyle, PlayStyle+ or Role++ that FC27
  gave the player (natively, or a Role++ FC27 upgraded); those rows are shorter. Paths Academy Engine gave
  or is developing keep their history.
- Events: Event and Details text in grey; the player name stays in the standard text colour.

## Save/exit log review (09-10-2026)
- The save ID did not change across the autosave, save and save-to-new-slot: it identifies the career,
  not the slot.
- Exiting to the main menu fires event 2, then FC27 reloads the career in the background within ~2 s
  (29 POST_LOAD_PREPARE + 26 ENTERED_HUB, same save ID, IsInCM true). The engine treats that as the career
  being loaded again, which is why its data stays visible in the main menu. Not changed in this build.
