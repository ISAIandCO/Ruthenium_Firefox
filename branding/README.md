# RFirefox Android branding

RFirefox preserves the standard Firefox release launcher artwork and adds a
small white `R` in its lower-left corner.

The WebP files under `android/` are based on the corresponding standard and
round Firefox assets from Mozilla tag `FIREFOX-ANDROID_153_0_4_RELEASE`. They
cover every density shipped by the Fenix release source set:

- `rfirefox-<density>.webp` replaces `ic_launcher.webp`;
- `rfirefox-round-<density>.webp` replaces `ic_launcher_round.webp`.

The `R` overlay uses DejaVu Sans Bold, a white fill and a dark outline. The
normal icon places it at approximately `(11.5%, 7.3%)` from the lower-left edge;
the round variant moves it farther inside the circular safe area.

Adaptive and themed icons are not rasterized here. `scripts/patch_firefox.py`
keeps Mozilla's foreground vectors intact and appends an equivalent `R` path to
both the release/main foreground and monochrome VectorDrawables. This prevents
the badge from disappearing when Android applies an adaptive mask or themed
icon tint.

Firefox and its logo are trademarks of Mozilla Foundation. See `NOTICE.md` and
Mozilla's trademark policy before distributing the modified assets.
