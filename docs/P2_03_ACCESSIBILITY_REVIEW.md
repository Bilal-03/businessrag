# P2-03 final accessibility and contrast review

## Automated result

`npm run test:e2e:accessibility` passes 12/12 checks across the desktop,
iPhone-sized, Pixel-sized, and iPad-sized profiles. The gate covers:

- Landmarks and accessible names for visible controls.
- Keyboard skip-link navigation and main-content focus.
- Mobile drawer navigation.
- No horizontal overflow.
- 44px minimum visible interactive target size.
- Reduced-motion behavior.
- Visible focus treatment.

## Token contrast checks

Contrast ratios use the WCAG relative-luminance formula against the canonical
canvas/accent tokens:

| Foreground | Background | Ratio | AA result |
| --- | --- | ---: | --- |
| `#f8fafc` content primary | `#080b14` canvas | 18.79:1 | Pass |
| `#b4c0d4` content secondary | `#080b14` canvas | 10.70:1 | Pass |
| `#8d9ab1` content muted | `#080b14` canvas | 6.92:1 | Pass |
| `#7168f6` accent | `#080b14` canvas | 4.69:1 | Pass for large text/UI |
| `#8875ff` accent strong | `#080b14` canvas | 5.65:1 | Pass |
| `#ffffff` on `#7168f6` | primary accent surface | 4.19:1 | Pass for large text/UI |
| `#ffffff` on `#8875ff` | strong accent surface | 3.48:1 | Pass for large text/UI |

The final two accent-surface pairs are intentionally reserved for buttons and
large labels. Do not use white small body text on those surfaces; use the
content-primary/secondary tokens on dark surfaces instead.

## Code-owned fixes

- Added the missing `--accent-strong` alias so the global focus ring resolves
  to a real color instead of an invalid custom property.
- Mapped legacy background/text/accent/glass aliases to canonical tokens to
  stop tertiary screens from drifting.
- Removed chat-composer autofocus so keyboard users reach the skip link first.
- Standardized the collapse control and skip link to 44px minimum height.

Physical VoiceOver, TalkBack, and Safari verification remains an external
release gate and is listed in `docs/P2_03_WCAG.md`.
