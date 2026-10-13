# FC27 Academy Engine v1.24.26 — Role++ upgrades made by FC27

- When FC27 itself upgrades one of a tracked player's Role+ roles to Role++ (seen between two snapshots on a
  continuous career timeline), Academy Engine now records it:
  - player history entry `FC27_NATIVE_ROLE_UPGRADE`;
  - a Role++ event titled "Upgraded by FC27" (Events page, player timeline, notification), one per upgrade;
  - the Development page shows "Upgraded to Role++ by FC27 during the career" with the date.
- FC27 upgrades do **not** start the engine's Role++ cooldown.
- Upgrades written by Academy Engine are never mistaken for FC27 ones, and loads/rewinds (which compare
  different points of the career) never produce them.
- Roles a player already had at Role++ when tracking began now read "…when Academy Engine began tracking him".
- PlayStyles / PlayStyle+ are not covered: FC27 does not add them during a career.
