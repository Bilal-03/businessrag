# P2-03 visual regression baselines

The authenticated home workspace has deterministic snapshots in
`web/tests/e2e/visual.spec.js-snapshots/`:

| Profile | Capture |
| --- | --- |
| Desktop | 1280 × 720 |
| Tablet | 768 × 1024 |
| Mobile | 390 × 664 |

Run the approval check from `web/`:

```bash
npm run test:e2e:visual
```

The warm editorial baseline was deliberately regenerated after the product-wide
redesign and passed 3/3 across desktop, tablet, and mobile. The suite disables
motion and caret rendering so snapshots represent layout and visual hierarchy,
not timing noise. Update snapshots only after a deliberate design review:

```bash
npm run test:e2e:visual -- --update-snapshots
```

A baseline update must include a reason in the commit and a visual check at all
three sizes. These are local Chromium reference captures; production-browser
differences still require a short manual review before a release.
