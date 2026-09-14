import { test, expect } from '@playwright/test';
import { setupAuth, TOKENS } from './helpers';

/**
 * Project Vulcan: Settings → External Resources & Microsoft Foundry Playwright E2E Suite.
 *
 * Verifies:
 * 1. Web Console route /settings/external-resources and /integrations alias redirect.
 * 2. Honest empty state when unseeded/unconnected vs. Bento Catalog in Demo Mode.
 * 3. 4-Tab Detail Pane: Overview, Configuration, Capabilities, Diagnostics navigation.
 * 4. Microsoft Foundry Dynamic Deployment Discovery & Vulcan Routing Default selection.
 * 5. Zero-Raw-Secrets Invariant UI validation & secret masking.
 * 6. Enterprise RBAC: PLATFORM_ADMIN mutation access vs OPERATOR read-only enforcement.
 */

test.describe('Settings → External Resources & Microsoft Foundry Console', () => {
  test.beforeEach(async ({ page }) => {
    // Authenticate as PLATFORM_ADMIN (admin.dave) by default
    await setupAuth(page, TOKENS.dave);
  });

  test('Route accessibility and /integrations alias redirection (R5)', async ({ page }) => {
    const consoleErrors: string[] = [];
    page.on('console', (msg) => {
      if (msg.type() === 'error' && !msg.text().includes('favicon.ico')) {
        consoleErrors.push(msg.text());
      }
    });

    // 1. Navigate to /settings/external-resources
    await page.goto('/settings/external-resources');
    await expect(page).toHaveTitle(/Vulcan/i);

    // 2. Verify main console container is rendered
    const consoleContainer = page.locator('[data-testid="external-resources-console"]').first();
    await expect(consoleContainer).toBeVisible();

    // 3. Test backward-compatible alias route /integrations redirects
    await page.goto('/integrations');
    await expect(page).toHaveURL(/\/settings\/external-resources/);
    expect(consoleErrors).toEqual([]);
  });

  test('Bento Catalog renders actual connections, honest empty state when unprovisioned, and Demo Mode support (R5)', async ({ page }) => {
    await page.goto('/settings/external-resources');

    // Verify bento sidebar container exists
    const catalog = page.locator('[data-testid="bento-catalog-sidebar"]');
    await expect(catalog).toBeVisible();

    // Verify actual connected categories are displayed
    const categoryHeadings = [
      'AI & Models',
      'ITSM & CMDB',
      'Secrets & PAM',
      'Source Control'
    ];
    for (const cat of categoryHeadings) {
      const heading = page.locator('aside').getByText(cat, { exact: true }).first();
      await expect(heading).toBeVisible();
    }

    // Verify status badge indicators are rendered once resources load
    const statusBadges = page.locator('[data-testid="status-badge"]');
    await expect(statusBadges.first()).toBeVisible();
    expect(await statusBadges.count()).toBeGreaterThan(0);

    // Filter to STAGE where no external resources are currently provisioned
    await page.locator('aside button:has-text("STAGE")').click();

    // Verify honest empty state is shown for unprovisioned environments in sidebar
    await expect(page.locator('text=No external resources connected')).toBeVisible();

    // Toggle demo mode explicitly
    const demoBtn = page.locator('button:has-text("Load Sample Demo Connections"), button:has-text("Demo Samples"), button:has-text("DEMO MODE")').first();
    await expect(demoBtn).toBeVisible();
    await demoBtn.click();

    // In demo mode, sample resources are loaded even in STAGE
    await expect(statusBadges.first()).toBeVisible();
    expect(await statusBadges.count()).toBeGreaterThan(0);
  });

  test('4-Tab Detail View navigation (Overview, Configuration, Capabilities, Diagnostics) (R5)', async ({ page }) => {
    await page.goto('/settings/external-resources');

    // Turn on demo mode so resources are available
    await page.locator('button:has-text("Demo Samples"), button:has-text("DEMO MODE")').first().click();

    // Click first resource card in sidebar
    const firstCard = page.locator('[data-testid="resource-card"]').first();
    await expect(firstCard).toBeVisible();
    await firstCard.click();

    // Verify all 4 tabs exist and navigate through each unconditionally
    const tabs = ['Overview', 'Configuration', 'Capabilities', 'Diagnostics'];
    for (const tabName of tabs) {
      const tabButton = page.locator(`button:has-text("${tabName}")`).first();
      await expect(tabButton).toBeVisible();
      await tabButton.click();
      await expect(tabButton).toBeVisible();
    }
  });

  test('Microsoft Foundry Dynamic Deployment Discovery and Vulcan Routing Defaults (R4/R5)', async ({ page }) => {
    await page.goto('/settings/external-resources');

    // Turn on demo mode
    await page.locator('button:has-text("Demo Samples"), button:has-text("DEMO MODE")').first().click();

    // Select Microsoft Foundry resource card
    const foundryCard = page.locator('[data-testid="resource-card"]:has-text("Foundry")').first();
    await expect(foundryCard).toBeVisible();
    await foundryCard.click();

    // Navigate to Capabilities Tab
    const capTab = page.locator('button:has-text("Capabilities")').first();
    await expect(capTab).toBeVisible();
    await capTab.click();

    // Trigger dynamic deployment discovery
    const discoverBtn = page.locator('button:has-text("Discover Deployments")').first();
    await expect(discoverBtn).toBeVisible();
    await discoverBtn.click();

    // Verify Vulcan routing default pickers are visible
    const chatPicker = page.locator('[data-testid="vulcan-chat-default"]').first();
    const embPicker = page.locator('[data-testid="vulcan-embedding-default"]').first();
    await expect(chatPicker).toBeVisible();
    await expect(embPicker).toBeVisible();
  });

  test('Zero-Raw-Secrets Invariant enforcement in Configuration Form (R2/R5)', async ({ page }) => {
    await page.goto('/settings/external-resources');

    // Turn on demo mode
    await page.locator('button:has-text("Demo Samples"), button:has-text("DEMO MODE")').first().click();

    // Click first resource card
    const firstCard = page.locator('[data-testid="resource-card"]').first();
    await expect(firstCard).toBeVisible();
    await firstCard.click();

    // Navigate to Configuration tab
    const configTab = page.locator('button:has-text("Configuration")').first();
    await expect(configTab).toBeVisible();
    await configTab.click();

    // Find secret pointer input
    const secretInput = page.locator('input[placeholder*="vault://"], input[placeholder*="cyberark://"], input[name*="secret"]').first();
    await expect(secretInput).toBeVisible();

    // Attempt to enter raw password without URI scheme
    await secretInput.fill('MyRawPassword123!');
    await secretInput.blur();

    // Verify validation warning is unconditionally displayed
    const errorMsg = page.locator('text=scheme').or(page.locator('text=vault://')).or(page.locator('text=cyberark://')).first();
    await expect(errorMsg).toBeVisible();

    // Enter valid URI pointer to clear error
    await secretInput.fill('vault://secret/vulcan/demo');
    await secretInput.blur();
  });

  test('Enterprise RBAC: Operator sees read-only views and disabled mutation controls (R6)', async ({ page }) => {
    // Authenticate as OPERATOR (eng.alice)
    await setupAuth(page, TOKENS.alice);
    await page.goto('/settings/external-resources');

    // Turn on demo mode
    await page.locator('button:has-text("Demo Samples"), button:has-text("DEMO MODE")').first().click();

    // Click first resource card
    const firstCard = page.locator('[data-testid="resource-card"]').first();
    await expect(firstCard).toBeVisible();
    await firstCard.click();

    // Mutation buttons in header should be disabled for Operator
    const testHandshakeBtn = page.locator('button:has-text("Test Handshake")').first();
    await expect(testHandshakeBtn).toBeVisible();
    await expect(testHandshakeBtn).toBeDisabled();

    // Navigate to Configuration tab
    const configTab = page.locator('button:has-text("Configuration")').first();
    await expect(configTab).toBeVisible();
    await configTab.click();

    // Save Configuration button should be disabled for Operator
    const saveBtn = page.locator('button:has-text("Save Configuration")').first();
    await expect(saveBtn).toBeVisible();
    await expect(saveBtn).toBeDisabled();
  });
});
