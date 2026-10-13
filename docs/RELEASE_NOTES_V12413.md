# FC27 Academy Engine v1.24.13: crash hardening, crash forensics, faster publication

Builds on v1.24.12; no data reset needed.

## The SAVE 1 → SAVE 2 → SAVE 1 crash

The 08-10 logs don't prove the cause, and nothing shows Academy Engine running when the game
died. Academy Engine's last calls into the game were two read-only checks ("in Career Mode?",
"which save?"). They ran on a "screen loaded" event (68) that fired while FC27 was already loading
SAVE 1. The log ends 8 seconds later, after "post-load prepare" (29), where the runtime only
logs.

v1.24.13 removes that exposure and records enough to settle it next time:

- **No game calls on menu/loading events.** Events 68 and 27 also fire on menus and during
  loads. They now touch the game only when a day capture is waiting. Pending PlayStyle writes
  are applied on the next day or save event instead of the next screen change.
- **Crash trace.** For 5 minutes around any load, save, exit or save switch, every Career Mode
  event is logged (`FC27AE_EVENT ev=… phase=…`). A `phase=NATIVE` line is written
  *before* each call into the game, and `FC27AE_WRITE_BEGIN` before any database write. If the
  game crashes, the last lines of the Live Editor log show whether Academy Engine was in the
  middle of something.

## Player details stuck on "Loading player details" (match days)

- **Cause:** after a click, the bridge rebuilds the overlay data. If nothing in the career had
  changed, the rebuilt file was byte-for-byte identical to the previous one, because identical
  content reuses the same data version. The overlay skips files it has already read, so it kept
  waiting until the career data next changed. On a match day that is after the match.
- **Seen in the 08-10 logs:** one rebuild at 20:10:13, then nothing until the match ended at
  20:35:47.
- **Fix:** every processed overlay click or setting now adds a changing `COMMAND_SEQ` line to
  the file. It is added after the version check, so no extra data versions are stored, and the
  overlay always re-reads the file after a click.
- **Cost:** one short line per rebuild. The bridge already rebuilt the file on every click; the
  overlay now re-reads it (about 30 KB at 7,231 players).

## Bridge lease (no idle timeout)

There is no idle timeout: staying on one day for hours never disconnects the engine. The
runtime only pauses while the bridge is not running; the bridge renews its lease every 2 s and
the runtime's existing 8 s check is unchanged.

- New: while paused, load boundaries and exits are still handled (without touching the game)
  and days are still counted, so progress evidence stays correct when the bridge returns.
- New: lapses are logged on both sides, so we can tell whether one ever happens while the bridge
  is running:
  - Live Editor log: `FC27AE_LEASE_LAPSED reason=MISSING|UNREADABLE|STALE age=…` once when the
    script first sees a lapse, and `FC27AE_LEASE_RESTORED lapsed_s=… events_while_lapsed=…`
    when it recovers.
  - bridge.log: `FC27AE_LEASE_WRITE_FAILED` when the bridge can't renew the lease, and
    `FC27AE_LEASE_RENEWED gap_s=…` when a renewal arrives 5 s or more after the previous one.

## Faster overlay publication

After a large snapshot, publishing the overlay data took 3.8 s plus a 1.3 s follow-up for
7,231 players.

- The 30 MB world file is now parsed once per revision instead of 2–3 times.
- The overlay's player cache no longer stores each player's full engine record (about 85 MB
  per refresh at 7,231 players). The selected player's record is read from the world.
- Synthetic 7,231 players on Linux: 5.1 s → 3.5 s for the main publication; 1.66 s → 0.08 s
  for the follow-up. Windows timings will differ.

## Validation

- All regression scripts pass, plus the new `test_detail_reload_v12413` and `test_v12413`.
  - `test_detail_reload_v12413` feeds files published by the real exporter (Back, then the same
    player again) to the real overlay C code built natively. It also confirms that the old
    identical file reproduces the stuck screen.
  - `test_v12413` covers:
  - the crash-log event sequence;
  - the trace lines;
  - behaviour and logging while the lease has lapsed;
  - world caching;
  - the slimmer cache.
- `test_history_retention_v12408` was updated, because cached rows no longer carry the full
  player record.
- DLL and host rebuilt (version only).

Not performed: in-game, Windows, or controller testing.
