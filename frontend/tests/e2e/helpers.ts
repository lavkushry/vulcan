import { Page } from '@playwright/test';
import fs from 'fs';
import path from 'path';

// Dynamically load .env.test.local if present locally (never committed to git)
const envLocalPath = path.resolve(__dirname, '../../.env.test.local');
if (fs.existsSync(envLocalPath)) {
  const content = fs.readFileSync(envLocalPath, 'utf8');
  for (const line of content.split('\n')) {
    const trimmed = line.trim();
    if (trimmed && !trimmed.startsWith('#') && trimmed.includes('=')) {
      const idx = trimmed.indexOf('=');
      const k = trimmed.slice(0, idx).trim();
      const v = trimmed.slice(idx + 1).trim();
      if (!process.env[k]) {
        process.env[k] = v;
      }
    }
  }
}

/**
 * Test authentication credentials for Playwright E2E suites.
 * Injected dynamically via environment variables (e.g. .env.test.local in local runs,
 * or GitHub Action secrets in CI). Never committed as raw literals.
 */
export const TOKENS = {
  bot: process.env.E2E_BOT_TOKEN || process.env.VULCAN_API_TOKEN || 'vlc_test_bot_ci_token',
  alice: process.env.E2E_ALICE_TOKEN || process.env.E2E_BOT_TOKEN || process.env.VULCAN_API_TOKEN || 'vlc_test_alice_ci_token',
  bob: process.env.E2E_BOB_TOKEN || 'vlc_test_bob_ci_token',
  dave: process.env.E2E_DAVE_TOKEN || 'vlc_test_dave_ci_token',
  carol: process.env.E2E_CAROL_TOKEN || 'vlc_test_carol_ci_token',
};

/**
 * Injects the specified API token into localStorage before page load.
 */
export async function setupAuth(page: Page, token: string = TOKENS.bot) {
  await page.addInitScript((tok) => {
    window.localStorage.setItem('vulcan_api_token', tok);
  }, token);
}
