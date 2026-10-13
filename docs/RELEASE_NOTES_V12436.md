# FC27 Academy Engine v1.24.36 — PlayStyle decline with age, and retirement

## PlayStyle decline (Settings > Ageing & PlayStyle decline; both switches off by default)
- Each generated player gets a personal decline start age between 30 and 40. The chance of starting
  rises each birthday, and better players (by peak OVR: under 80 / 80–84 / 85+) tend to start later.
  Typical starts: 34, 35 and 36; every remaining player starts at 40.
- Once started, a PlayStyle (FC27-given or engine-awarded) builds decline progress while its key
  attributes average below 70 **and** are well below the player's own peak. Progress builds faster
  the older he is and eases back if the attributes recover (more slowly when older). It is lost at 100%.
- A PlayStyle+ first drops to the normal PlayStyle (PlayStyle+ eligibility ends); the normal one can be
  lost later on its own evidence. Several PlayStyles can be lost, at least 60 days apart, after a grace
  period when the phase starts.
- Lifetime cap: at the cap the cap shrinks with the loss (4/4 → 3/3, 1/1 → 0/0); below it only the count
  drops (2/4 → 1/4). A lost PlayStyle is not re-earned unless its attributes clearly recover.
- Goalkeepers' PlayStyles are judged on goalkeeper attributes (passing styles on kicking).
- Visible: a PLAYSTYLE DECLINE section on the Development page once the phase has started (declining,
  recovering, holding, lost, downgraded), "PlayStyle Lost" / "PlayStyle+ Downgraded" events and a
  popup (Notifications), a "Declining" status filter, and a Decline speed setting.
- Writes use two new, separately checked write types (clear exactly one known PlayStyle on a generated
  player), with the same transaction, rollback and receipt safeguards as awards.

## Retirement
- A player 33 or older whom FC27 no longer holds (missing from several trusted snapshots over at least a
  week of career time) is treated as retired and hidden completely: Players list, summaries and events.
  His face goes back to the pool. Younger missing players are not retired.
- If he is ever seen again he returns as he was (his record keeps lifetime limits and history).
- After two seasons a retired player's record is trimmed to a short summary to keep career files small.

## Fixed during review (before release)
- A PlayStyle loss could reset a player's Role++ cooldown, and Role++ upgrades no longer started theirs.
- A loss already queued could still be written after the switches were turned off.
- Retirement now ignores partial or empty snapshots and same-day saves/reloads.
