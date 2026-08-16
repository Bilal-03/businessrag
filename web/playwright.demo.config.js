import { defineConfig, devices } from '@playwright/test';

/**
 * Portfolio capture configuration. The demo uses the same local fixture
 * routes as the functional suite, but records a single paced walkthrough.
 */
export default defineConfig({
  testDir: './tests/e2e',
  testMatch: /portfolio-demo\.spec\.js/,
  fullyParallel: false,
  workers: 1,
  timeout: 180_000,
  forbidOnly: true,
  retries: 0,
  reporter: [['list']],
  outputDir: '../artifacts/portfolio-demo-raw',
  use: {
    baseURL: 'http://127.0.0.1:4173',
    viewport: { width: 1280, height: 720 },
    video: { mode: 'on', size: { width: 1280, height: 720 } },
    trace: 'off',
    screenshot: 'off',
  },
  projects: [
    {
      name: 'portfolio-demo',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
  webServer: {
    command: 'npm run dev -- --host 127.0.0.1 --port 4173 --mode e2e',
    url: 'http://127.0.0.1:4173',
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
  },
});
