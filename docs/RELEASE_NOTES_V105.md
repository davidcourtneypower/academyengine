# FC27 Academy Engine v1.0.5 — Antivirus false positives

Nexus Mods quarantined the download after VirusTotal reported 5 of 67 engines (Bkav, DeepInstinct,
MaxSecure, Sangfor, SentinelOne's static ML) and labelled it a "trojan". No functional change.

- **VirusTotal identified the whole download as the "pillow" Python package.** The bundled Python
  packages kept their install records (`*.dist-info` folders); VirusTotal read Pillow's and judged
  the zip a Pillow package that "secretly" bundled a game mod. Those records are now removed at
  build time (nothing in Academy Engine reads them). Their licence texts are kept in
  `runtime\licenses`, now together with the LGPL v3 and GPL v3 texts that PySide6's package does
  not carry. The release packager refuses a runtime that still has the records.
- **The overlay files now say what they are.** AcademyOverlay.dll and AcademyOverlayHost.exe carry
  Windows file details (Properties > Details: name, description, version), and the host has a
  manifest that asks for no extra rights. The host is no longer built stripped of its symbols.
  Unlabelled, stripped programs are what antivirus "ML" engines tend to flag.
- The overlay host's source moved to `native_overlay\source\host` (its own Go module, so its file
  details are built in). `tools/build_overlay.sh` is the single recipe for both files.

Not code-signed: a small engine may still flag it. Check a new build on VirusTotal before uploading.
