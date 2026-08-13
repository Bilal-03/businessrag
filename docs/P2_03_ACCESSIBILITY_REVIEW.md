# P2-03 final accessibility and contrast review

## Automated result

The warm editorial redesign passed the release-critical desktop and iPhone
preflight (6/6 checks). The broader Pixel and iPad matrix remains available
through `npm run test:e2e:accessibility`. The gate covers:

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
| `#20231f` content primary | `#f3efe6` canvas | 13.85:1 | Pass |
| `#6b665e` content secondary | `#f3efe6` canvas | 4.96:1 | Pass |
| `#716b63` content muted | `#f3efe6` canvas | 4.59:1 | Pass |
| `#9f3f29` accent | `#f3efe6` canvas | 5.69:1 | Pass |
| `#fffaf3` on `#9f3f29` | primary action | 6.29:1 | Pass |
| `#fffaf3` on `#7f321f` | strong action | 8.50:1 | Pass |
| `#394737` on `#e4eadf` | positive state | 8.04:1 | Pass |
| `#684511` on `#f3e5c8` | warning state | 6.88:1 | Pass |
| `#a33b35` on `#fff6f3` | destructive state | 6.10:1 | Pass |

## Code-owned fixes

- Replaced the former blue-violet token set with warm canvas, ink,
  terracotta, sage, ochre, and destructive-state tokens.
- Kept canonical and legacy token aliases aligned so secondary screens do not
  drift from the editorial system.
- Upgraded the composer to a labelled multiline control with Enter-to-send
  and Shift+Enter-for-newline behavior.
- Preserved skip-link order, reduced-motion handling, forced-colors support,
  and 44px minimum visible targets across desktop and mobile navigation.

Physical VoiceOver, TalkBack, and Safari verification was completed as the
external release gate on 2026-08-13, based on user confirmation.
