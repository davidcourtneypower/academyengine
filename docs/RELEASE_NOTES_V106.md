# FC27 Academy Engine v1.0.6 — The overlay is one program

The v1.0.5 rescan (via Nexus Mods) no longer took the download for the Pillow package, but
AcademyOverlayHost.exe was still flagged by 7 of 71 engines (the zip by 4 of 57: Bkav, DeepInstinct,
Elastic, SentinelOne's static ML). Every other file in the download was clean.

Until now the overlay was two files: a small Go program whose only job was to load
AcademyOverlay.dll from its folder and keep it running. That shape (a tiny program that loads a
DLL and waits) is what malware loaders look like, and it is what these engines judge by.

- **AcademyOverlayHost.exe is now built straight from the overlay's C source.** There is no
  AcademyOverlay.dll and no Go program any more. The program creates its own window and draws the
  overlay, exactly as before.
- **Nothing that looks like loading code.** The controller is now read through Windows' XInput
  directly, instead of loading the XInput library at run time, so the program uses no
  LoadLibrary/GetProcAddress at all. It imports only kernel32, user32, gdi32 and xinput1_4.
- Windows file details and the "no extra rights" manifest are kept.
- If you update by copying over an older folder, the old AcademyOverlay.dll is left behind and
  simply ignored; you can delete it.

Not code-signed: a small engine may still flag it. Check the new build on VirusTotal before uploading.
