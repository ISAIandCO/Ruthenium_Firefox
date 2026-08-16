# RFirefox Android branding

RFirefox preserves the standard Firefox release launcher artwork and adds a
compact lower-left identity medallion. The split geometric `R`, inset panel,
violet rim and highlight are designed as one mark rather than a font glyph
placed over the Firefox artwork.

The WebP files under `android/` are based on the corresponding standard and
round Firefox assets from Mozilla tag `FIREFOX-ANDROID_153_0_4_RELEASE`. They
cover every density shipped by the Fenix release source set:

- `rfirefox-<density>.webp` replaces `ic_launcher.webp`;
- `rfirefox-round-<density>.webp` replaces `ic_launcher_round.webp`.

The editable overlay masters are `rfirefox-badge-square.svg` and
`rfirefox-badge-round.svg`. The normal icon uses an inset rounded-square
medallion; the round icon uses a smaller circular version placed within its safe
area. Neither changes the original launcher silhouette. Both use a two-part
custom vector monogram which remains legible at the 48 px mdpi size.

Adaptive and themed icons are not rasterized here. `scripts/patch_firefox.py`
keeps Mozilla's foreground vectors intact and appends an equivalent disc and
split monogram to the release/main foreground. The monochrome VectorDrawable
uses a ring plus the same split monogram, so the identity remains visible when
Android applies an adaptive mask or themed-icon tint.

Firefox and its logo are trademarks of Mozilla Foundation. See `NOTICE.md` and
Mozilla's trademark policy before distributing the modified assets.
