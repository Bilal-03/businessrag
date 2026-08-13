import { defineConfig, devices } from '@playwright/test';

/**
 * The accessibility suite intentionally runs separately from the functional
 * suite so device coverage does not multiply every end-to-end test. These are
 * browser device profiles (a repeatable preflight gate), not a substitute for
 * the final physical iOS/Android check documented in docs/P2_03_WCAG.md.
 */
export default defineConfig({
  testDir: './tests/e2e',
  testMatch: /accessibility\.spec\.js/,
  fullyParallel: true,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: [
    ['list'],
    ['html', { open: 'never', outputFolder: 'playwright-report/accessibility' }],
  ],
  use: {
    baseURL: 'http://127.0.0.1:4173',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
  },
  projects: [
    { name: 'desktop-chrome', use: { ...devices['Desktop Chrome'] } },
    // WebKit is not guaranteed to be installed in CI or a fresh checkout.
    // Keep the iPhone/iPad viewport and touch characteristics deterministic
    // while using the Chromium binary already required by the main suite.
    { name: 'iphone-13', use: { ...devices['iPhone 13'], browserName: 'chromium' } },
    { name: 'pixel-7', use: { ...devices['Pixel 7'] } },
    { name: 'ipad-mini', use: { ...devices['iPad Mini'], browserName: 'chromium' } },
  ],
  webServer: {
    command: 'npm run dev -- --host 127.0.0.1 --port 4173 --mode e2e',
    url: 'http://127.0.0.1:4173',
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
  },
});
