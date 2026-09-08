import { defineConfig, devices } from '@playwright/test';

/**
 * Project Vulcan: Playwright E2E Smoke Test Configuration
 * Author: Jordan Walke (Frontend Lead) & Platform SRE Lead
 */
export default defineConfig({
  testDir: './tests/e2e',
  timeout: 60000,
  expect: {
    timeout: 10000,
  },
  outputDir: '../docs/e2e/evidence',
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: 0,
  workers: 1,
  reporter: [
    ['list'],
    ['html', { outputFolder: '../docs/e2e/report', open: 'never' }]
  ],
  use: {
    baseURL: process.env.PLAYWRIGHT_BASE_URL || 'http://localhost:3000',
    trace: 'on',
    video: 'on',
    screenshot: 'on',
    viewport: { width: 1440, height: 900 },
    ignoreHTTPSErrors: true,
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
});
