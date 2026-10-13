# FC27 Academy Engine v1.24.25 — Player list, details and events polish

## Player list
- New **NEXT ROLE** column: the highest-progress Role++ path among the player's current Role+ roles
  (sortable). ROLE++ PROGRESS now follows that role rather than the whole history ledger.
- **STATUS** is shown as coloured dots with a legend above the table: blue Developing PlayStyle,
  gold Developing PlayStyle+, green Developing Role++, grey Paused (no active progress, free agent or
  not observed). A hollow dot means that path has reached readiness and is waiting (queued, cooldown or
  held). Hover the dots for the full status text.
- ROLES wrap onto extra lines; the row grows to fit (PlayStyles and roles).
- Filters on two rows at natural widths; option popups size to their longest option.
- Free agents show no club (list and player details). "Not Eligible" (PlayStyle+) in red.
- Column renamed ROLE++ PROGRESS. Saved sort columns shift with the new column.

## Player details
- Current development status shown as one chip per lane (PlayStyle / PlayStyle+ / Role++), sized to the text.
- Current PlayStyles / PlayStyle+ listed as plain text (overview and Development page).
- Development page: PlayStyle, PlayStyle+ and Role++ sections can be hidden/shown from their header; while
  scrolled part-way through a section a pinned header bar lets you hide it (the view returns to its header).

## Events
- Removed the PS badge beside the player name; Event and Details use the standard text colour.

## Wording
- Statuses capitalised consistently (Developing, Queued, Cooldown, Not eligible, Ready — Queued for
  acquisition, Paused — Free agent, …); event titles "PlayStyle Acquired", "PlayStyle+ Acquired",
  "Role++ Acquired" (older recorded events are normalised on display).
