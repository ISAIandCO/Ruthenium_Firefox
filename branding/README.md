# RFirefox Android branding

The RFirefox mark is a custom fox whose body and tail form the outline of an
`R`. Orange, gold and magenta surfaces retain the visual language of Firefox,
while the violet centre and dark ink background keep the result distinct and
legible at launcher size. The letter is part of the illustration rather than a
font glyph or a badge placed over another logo.

The WebP files under `android/` cover every launcher form used by the Fenix
release source set:

- `rfirefox-<density>.webp` replaces the square legacy `ic_launcher.webp`;
- `rfirefox-round-<density>.webp` replaces the round legacy
  `ic_launcher_round.webp`;
- `rfirefox-adaptive-foreground.webp` is the transparent colour foreground for
  adaptive icons;
- `rfirefox-adaptive-monochrome.webp` is its alpha-preserving silhouette for
  Android themed icons.

The legacy outputs retain the upstream pixel dimensions: 48, 76, 96, 144 and
192 px for mdpi through xxxhdpi. Lossless 512 px source renders are stored as
`rfirefox-square-master.webp` and `rfirefox-round-master.webp`.

The adaptive assets are 432 px in `drawable-xxxhdpi`, which maps to the 108 dp
launcher canvas. Their transparent padding keeps the fox-R inside the adaptive
safe zone while Android supplies the existing release background and applies
the user's circle, squircle or other launcher mask. `scripts/patch_firefox.py`
installs small bitmap-drawable wrappers for both the colour and monochrome
layers; the latter is tinted by Android instead of baking in a theme colour.

Firefox and its logo are trademarks of Mozilla Foundation. See `NOTICE.md` and
Mozilla's trademark policy before distributing the modified assets.
