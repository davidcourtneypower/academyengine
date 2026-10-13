# FC27 Academy Engine v1.24.15: controller focus fix

Builds on v1.24.14 (names diagnostic, ring cursor, LT/RT sub-views); no data reset needed.

## Controller stopped working once the overlay opened, and FC27 reacted to the pad

**Cause.** Windows only lets a program take keyboard and controller focus if that program
received the last keyboard or mouse input. A controller press is neither. So when the overlay
was opened with the pad combo, it appeared on top but FC27 kept focus. The overlay only acts on
the pad while it has focus, so it ignored the pad, and FC27 went on reacting to every press.
Opening with the keyboard hotkey, or clicking the overlay with the mouse, didn't have this
problem.

**Fix.**
- When it opens, the overlay now borrows FC27's input focus to take the foreground. This is
  the standard Windows technique (`AttachThreadInput`).
- If that's refused, it sends one unused key (F24) so that Windows grants it focus.
- If the overlay is visible but still not focused, the next controller press takes focus
  instead of being acted on, and the game gets no further presses.
- The same applies when the overlay reappears after you switch back to FC27.

## Validation

- All regression scripts pass. `test_controller_v12414` now also covers:
  - focus taken through FC27's input state;
  - focus taken through the F24 fallback when that's refused;
  - the first press taking focus without clicking, and the next press clicking normally.
- DLL rebuilt. New imports: `AttachThreadInput`, `GetCurrentThreadId`, `BringWindowToTop`,
  `keybd_event`.

Not performed: Windows or physical-controller testing.
