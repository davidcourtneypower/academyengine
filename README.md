
About this mod
Generated players in your Career Mode develop PlayStyles, PlayStyle+ and Role++ from how they actually grow, at a realistic pace, within lifetime limits. Optionally, ageing players can lose them again. An in-game overlay shows every player's progress, history and events. Academy Engine only works on players FC27 generates during a career (youth ac

FC27 Academy Engine
Realistic PlayStyle, PlayStyle+ and Role++ development for the players your career generates.
In FC27, youth academy players and regens mostly keep the PlayStyles they were born with. Academy Engine changes that: as a generated player's attributes really grow, they work towards the PlayStyles, PlayStyle+ and Role++ that suit their game, at a realistic pace and within lifetime limits. An in-game overlay shows exactly how close every player is and why. 

Features

    Earned development: progress comes from real attribute growth across in-game days, with waiting periods between awards. Nothing is handed out at random.
    PlayStyles, PlayStyle+ and Role++, typically try match to each player's position and attributes.
    Starting PlayStyles for newly generated players are improved (not necessarily more just better suited).
    Lifetime limits, so not every prospect becomes a superstar. Random but better players are more likely to be able to develop more playstyles.
    Optional decline with age (off by default): from a personal age sometime between 30 and 40, players whose key attributes fall can lose PlayStyles, and PlayStyle+ drops back to PlayStyle first. Better players are more likely to decline later.
    In-game overlay with controller support (F8 or L3+R3 on XInput): dashboard, searchable player list with filters, each player's development paths and timeline, an events feed, and settings.
    Save-aware: loading an older save tries putting Academy Engine back where it was at that save.
    Real players are never touched. Only players FC27 generates during your career are changed.
    Verified writes: every change goes through Live Editor and is checked before it counts.
    Settings: Development speed, time between awarding and other values can be changed via the overlay.

Requirements

    EA SPORTS FC 27 (PC), Borderless or Windowed display mode (Exclusive fullscreen untested).
    FC 27 Live Editor (tested with 27.1.x)
    Nothing else: Python and all libraries are included.
    If you run Live Editor as administrator, the launcher offers to restart Academy Engine as administrator too (one click, or automatically).

Installation

    IMPORTANT - Start FC27 through Live Editor once, then close it.
    Extract the FC27_Academy_Engine folder somewhere you can write to (for example Documents, not Program Files).
    Run FC27 Academy Engine.bat and keep the launcher open while you play.
    Start FC27 through Live Editor, load your career and press F8.
    Academy Engine WILL pick up generated players in a current career.
    I recommend you make a backup of your save!

Full instructions, uninstall steps and troubleshooting are in README.txt.

Compatibility
Do not combine with other mods that change generated players' PlayStyles. With Total Career Overhaul, set [PlayStyles] ENABLED = false in its config.ini; its other features work alongside Academy Engine. Not compatible with FC 27 Dynamic PlayStyle Generator.

About the overlay program
The overlay is drawn by a separate small program (AcademyOverlayHost.exe). It never injects anything into FC27.exe. Its source code is included in the download.

Support
When reporting a problem please include your FC27 and Live Editor versions and the logs folder from %LOCALAPPDATA%\FC27AcademyEngine. See README.txt.

Credits
Built on FC 27 Live Editor. Includes Python, Qt for Python (PySide6), psutil and Pillow; see THIRD_PARTY_NOTICES.txt.
