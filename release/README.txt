FC27 ACADEMY ENGINE
===================

Generated players in your Career Mode develop PlayStyles, PlayStyle+ and Role++ from how
they actually grow, at a realistic pace, within lifetime limits. Optionally, ageing players
can lose them again. An in-game overlay shows every player's progress, history and events.

Academy Engine only works on players FC27 generates during a career (youth academy players
and regens). Real players are never changed.


REQUIREMENTS
------------
- Windows 10 or 11 (64-bit)
- EA SPORTS FC 27 on PC
- FC 27 Live Editor (tested with 27.1.x)
- FC27 set to Borderless or Windowed display mode, so the overlay can show above the game

Nothing else. Python and everything the mod needs are included in the "runtime" folder.


INSTALL
-------
1. Start FC27 through Live Editor once, then close it. This creates Live Editor's folders.
2. Extract the "FC27_Academy_Engine" folder somewhere you can write to, for example
   Documents. Do not put it in Program Files.
3. Double-click "FC27 Academy Engine.bat". The launcher opens, finds Live Editor and
   installs a small autorun file into it. If the launcher says Live Editor is not set up
   yet, start FC27 through Live Editor once with the launcher open; it is found
   automatically.


PLAYING
-------
1. Start "FC27 Academy Engine.bat" and keep the launcher open while you play.
   Closing it stops the engine.
2. Start FC27 through Live Editor and load your career.
3. Press F8 (or L3+R3 on a controller) to open or close the overlay. Both can be changed
   in the launcher.

What happens:
- As in-game days pass, Academy Engine watches how each generated player's attributes
  grow and builds progress towards PlayStyles, PlayStyle+ and Role++ that suit him.
- When a player is ready, the change is written into your career through Live Editor and
  checked. It becomes permanent when you save your career, like any other change.
- New generated players can receive a few starting PlayStyles.
- Each player has a lifetime limit on PlayStyles. Once he reaches it, the engine adds no
  more (it never removes any to make room).
- PlayStyle decline with age is OFF by default. Turn it on in Settings > Ageing &
  PlayStyle Decline if you want older players to lose PlayStyles as they slow down.

The overlay has four pages: Dashboard, Players (search, filters and each player's
Overview, Development and Timeline), Events, and Settings. Settings belong to the career
you have loaded.


YOUR SAVES
----------
Academy Engine keeps its own data in %LOCALAPPDATA%\FC27AcademyEngine and matches it to your
saves: if you load an older save, the engine goes back to what it knew at that point.
It never edits your save files directly.


OTHER MODS
----------
Do not use another mod that changes generated players' PlayStyles at the same time. For
example, switch off the PlayStyles feature of Total Career Overhaul ([PlayStyles]
ENABLED = false in its config.ini), and do not use FC 27 Dynamic PlayStyle Generator
alongside Academy Engine.


ANTIVIRUS
---------
The overlay is drawn by AcademyOverlayHost.exe, a separate small program with its own
window. It never injects anything into FC27.exe or reads its memory. Its source code is
included in native_overlay\source. It is not code-signed, so a few antivirus programs that
judge unknown programs by their shape may warn about it.


UPDATING
--------
Close the launcher, replace the folder with the new version, and start it again. Your
career data is kept.


UNINSTALL
---------
1. Close FC27, Live Editor and the launcher.
2. Double-click "UNINSTALL.bat". It removes Academy Engine's autorun file from Live Editor
   and asks whether to delete the engine's data as well.
3. Delete the FC27_Academy_Engine folder.
PlayStyles that were already given to players stay in your saves.

To start completely fresh without uninstalling, use RESET_ALL_ACADEMY_DATA.bat.


PROBLEMS AND SUPPORT
--------------------
- The launcher says "Live Editor bridge: not set up yet": start FC27 through Live Editor
  with the launcher open. Live Editor is found within a few seconds and remembered.
- The overlay does not appear: check FC27 is in Borderless or Windowed mode, the launcher
  is open, and a career is loaded. Then press F8.
- The launcher says "Needs administrator": Live Editor started FC27 as administrator, and
  Windows then blocks the overlay unless Academy Engine runs as administrator too. Click
  "Restart Academy Engine as administrator" and accept the Windows prompt. Tick "Always do
  this..." to have it happen automatically whenever FC27 runs as administrator.

When reporting a problem, please include:
- your FC27 and Live Editor versions
- the "logs" folder from %LOCALAPPDATA%\FC27AcademyEngine (paste that path into the
  File Explorer address bar)
- Live Editor's latest log file
- what you did just before the problem


Third-party software included in this download is listed in THIRD_PARTY_NOTICES.txt.
