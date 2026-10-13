# FC27 Academy Engine storage and reset (since v1.24.07, current to v1.24.37)

All Academy Engine-owned state now lives under one root:

`%LOCALAPPDATA%\FC27AcademyEngine`

The runtime/IPC bridge is inside that root at:

`%LOCALAPPDATA%\FC27AcademyEngine\runtime\bridge`

For a complete factory reset, fully close FC27, FC Live Editor and Academy Engine, then delete `%LOCALAPPDATA%\FC27AcademyEngine` or run `RESET_ALL_ACADEMY_DATA.bat`.

The Live Editor autorun bootstrap remains in the user's selected Live Editor data folder because it is program integration code, not Academy career state. It contains no stored career progression.
