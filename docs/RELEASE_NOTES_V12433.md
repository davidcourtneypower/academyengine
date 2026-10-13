# FC27 Academy Engine v1.24.33 — Face picker tweaks

- **Automatic face** now closes the picker as well as switching back to the engine's face.
- **Load more faces** replaces Previous / Next: the picker shows one list that grows by a batch
  (as many faces as fit the window) each time you press the button under the last row. The faces area
  scrolls with the mouse wheel. When the picker opens, enough faces are loaded to include the player's
  current one and the list scrolls to it. Choosing another region starts again from its first batch.
- **Friendly region names** in the picker: "South Asia", "West Africa", "Afro-Caribbean", "Italy",
  "Southern Cone (South America)" and so on. Your folders keep their names on disk; folders not in the
  list are spelled out from their name (e.g. "NewRegionName" → "New Region Name").
- Developer aid: the overlay snapshot tooling now honours clipping.
