# P2-03 WCAG and device verification

## Automated preflight (completed)

Run from `web/`:

```bash
npm run test:e2e:accessibility
```

The suite runs 12 checks across four repeatable Playwright profiles:

| Profile | Coverage |
| --- | --- |
| Desktop Chrome | Keyboard navigation, landmarks, accessible names, focus, overflow, touch target sizing, reduced motion |
| iPhone 13 viewport | Mobile drawer navigation, the same WCAG preflight checks, 44px targets |
| Pixel 7 viewport | Android-sized layout and the same WCAG preflight checks |
| iPad Mini viewport | Tablet layout and the same WCAG preflight checks |

The current result is **12/12 passing**. These are Chromium device profiles. They are a repeatable regression gate, not proof of behavior in physical Safari, VoiceOver, TalkBack, or a hardware keyboard.

## Physical-device gate (still required)

Before declaring P2-03 accessibility complete, test the production URL on:

1. iPhone Safari with VoiceOver enabled.
2. Android Chrome with TalkBack enabled.
3. iPad Safari in portrait and landscape.
4. A keyboard-only desktop session (Tab, Shift+Tab, Enter, Escape, arrow keys).

For each device, verify: opening/closing navigation, changing business context, uploading and deleting a document, adding/deleting a compliance task, switching Settings tabs, focusing the chat composer, reading status/error announcements, and honoring reduced motion. Record the browser/OS and pass/fail result in the release checklist.

## Fixes made by this gate

- Removed chat-composer `autoFocus`, which hijacked the first keyboard stop and hid the skip link.
- Increased the sidebar collapse control and skip link to the 44px minimum target.
- Added mobile-aware navigation assertions so the drawer is opened before testing its landmarks.
- Added a separate accessibility Playwright config so device coverage does not multiply the full functional suite.
