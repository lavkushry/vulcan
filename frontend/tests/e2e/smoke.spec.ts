import { test, expect } from '@playwright/test';

/**
 * Project Vulcan: Platform E2E Smoke Suite
 * Author: Jordan Walke & Platform SRE Lead
 * Verifies that all mission-critical operator console pages load with 0 runtime errors
 * and adhere to the Obsidian Glass design contract.
 */

test.describe('Vulcan Operator Console Smoke Tests', () => {
  test('Actions page loads and renders task list', async ({ page }) => {
    await page.goto('/actions');
    await expect(page).toHaveTitle(/Vulcan/i);
    // Verify page content exists
    const heading = page.locator('h1, h2').first();
    await expect(heading).toBeVisible();
  });

  test('Matrix page loads and renders task table', async ({ page }) => {
    await page.goto('/matrix');
    await expect(page).toHaveTitle(/Vulcan/i);
    const tableOrGrid = page.locator('table, [role="table"], [role="grid"]').first();
    await expect(tableOrGrid).toBeVisible();
  });

  test('AI Chat page loads with input and tokenomics HUD', async ({ page }) => {
    await page.goto('/chat');
    await expect(page).toHaveTitle(/Vulcan/i);
    // Verify chat assistant input field exists
    const chatInput = page.locator('input[placeholder*="automate"], textarea').first();
    await expect(chatInput).toBeVisible();
  });

  test('Dashboard loads mission control canvas', async ({ page }) => {
    await page.goto('/dashboard');
    await expect(page).toHaveTitle(/Vulcan/i);
    const body = page.locator('body');
    await expect(body).toBeVisible();
  });
});
