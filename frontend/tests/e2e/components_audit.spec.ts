import { test, expect } from '@playwright/test';
import { setupAuth, TOKENS } from './helpers';

/**
 * Project Vulcan: Defending UI-XX 100% — Component Audit Suite
 * Explicit browser-level E2E verification for:
 * 1. UI-25: Multi-Cluster Topology Radar (Header trigger, consensus indicator, 3 datacenters)
 * 2. UI-14: Topology Blast Radius Drawer (Target node, downstream VIP dependencies, automated rollback guarantee)
 * 3. UI-23: Declarative Code Diff Inspector (Monaco diff modal, side-by-side vs unified diff toggle)
 * 4. UI-27: Dual-Pane Split-Screen Terminal Replay (Golden baseline vs live stdout comparison)
 */

test.describe('Component Audits: UI-14, UI-23, UI-25, UI-27 Verification', () => {
  test('UI-25: Multi-Cluster Radar opens from Header and renders consensus telemetry', async ({ page }) => {
    const consoleErrors: string[] = [];
    page.on('console', (msg) => {
      if (msg.type() === 'error' && !msg.text().includes('favicon.ico')) {
        consoleErrors.push(msg.text());
      }
    });

    await setupAuth(page, TOKENS.bot);
    await page.goto('/actions');
    await expect(page).toHaveTitle(/Vulcan/i);

    // 1. Locate and click the Cluster Radar button in Header
    const clusterBtn = page.locator('[data-testid="header-cluster-radar-btn"]');
    await expect(clusterBtn).toBeVisible({ timeout: 10000 });
    await clusterBtn.click();

    // 2. Assert Modal is open
    const modal = page.locator('div[role="dialog"][aria-labelledby="cluster-radar-title"]');
    await expect(modal).toBeVisible({ timeout: 10000 });

    // 3. Assert Header text
    const title = modal.locator('#cluster-radar-title');
    await expect(title).toContainText('Multi-Cluster Topology Radar');
    await expect(title).toContainText('UI-25');

    // 4. Assert Datacenter cluster topology nodes are rendered within modal
    await expect(modal.getByRole('heading', { name: /Ashburn/i })).toBeVisible({ timeout: 10000 });
    await expect(modal.getByRole('heading', { name: /Oregon/i })).toBeVisible();
    await expect(modal.getByRole('heading', { name: /Dublin/i })).toBeVisible();

    // 5. Assert Quorum Consensus telemetry
    await expect(modal.locator('text=DISTRIBUTED REDLOCK QUORUM')).toBeVisible();

    // 6. Close Modal using the visible footer button
    const closeBtn = page.getByRole('button', { name: 'Close Radar' });
    await expect(closeBtn).toBeVisible({ timeout: 5000 });
    await closeBtn.click();
    await expect(modal).not.toBeVisible({ timeout: 5000 });

    expect(consoleErrors).toEqual([]);
  });

  test('UI-14 & UI-23: Pre-Execution Blast Radius Drawer and Code Diff Modal', async ({ page }) => {
    const consoleErrors: string[] = [];
    page.on('console', (msg) => {
      if (msg.type() === 'error' && !msg.text().includes('favicon.ico')) {
        consoleErrors.push(msg.text());
      }
    });

    await setupAuth(page, TOKENS.bot);
    await page.goto('/chat');
    await expect(page).toHaveTitle(/Vulcan/i);

    // Start a clean new chat session
    const newChatBtn = page.locator('button:has-text("New Chat")');
    await expect(newChatBtn).toBeVisible({ timeout: 10000 });
    await newChatBtn.click();

    // Submit intent that requires Maker-Checker approval
    const promptInput = page.locator('[data-testid="chat-assistant-input"]');
    await promptInput.fill('Expand Postgres tablespace db-main-prod by 500GB');
    await page.locator('[data-testid="chat-submit-btn"]').click();

    // Wait for slot card to appear and submit for approval
    const submitBtn = page.locator('button:has-text("SUBMIT FOR APPROVAL")').last();
    await expect(submitBtn).toBeVisible({ timeout: 15000 });
    await submitBtn.click();

    // Assert PENDING_APPROVAL state reached
    await expect(page.locator('text=PENDING_APPROVAL').first()).toBeVisible({ timeout: 20000 });

    // === UI-14: Blast Radius Drawer Verification ===
    const blastRadiusBtn = page.locator('[data-testid="approval-inspect-blast-radius-btn"]').first();
    await expect(blastRadiusBtn).toBeVisible({ timeout: 10000 });
    await blastRadiusBtn.click();

    // Assert Blast Radius Drawer opens
    const drawer = page.locator('div[role="dialog"][aria-labelledby="blast-radius-title"]');
    await expect(drawer).toBeVisible({ timeout: 10000 });

    // Assert primary sections
    await expect(drawer.locator('#blast-radius-title')).toContainText('Topology Blast Radius & Collateral Radar');
    await expect(drawer.locator('#blast-radius-title')).toContainText('UI-14');
    await expect(drawer.locator('text=PRIMARY TARGET NODE')).toBeVisible({ timeout: 10000 });
    await expect(drawer.locator('text=DOWNSTREAM DEPENDENT SERVICES')).toBeVisible();
    await expect(drawer.locator('text=AUTOMATED ROLLBACK PLAYBOOK REGISTERED')).toBeVisible();
    await expect(drawer.locator('text=RTO <')).toBeVisible();

    // Close drawer
    const closeDrawerBtn = drawer.locator('button:has-text("Close Radar"), button[aria-label="Close blast radius drawer"]').first();
    try {
      await closeDrawerBtn.click({ force: true, timeout: 3000 });
    } catch {
      await page.keyboard.press('Escape');
    }
    await expect(drawer).not.toBeVisible();

    // === UI-23: Monaco Diff Modal Verification ===
    const diffBtn = page.locator('[data-testid="approval-inspect-diff-btn"]').first();
    await expect(diffBtn).toBeVisible();
    await diffBtn.click();

    // Assert Diff Modal opens
    const diffModal = page.locator('div[role="dialog"][aria-labelledby="diff-modal-title"]');
    await expect(diffModal).toBeVisible({ timeout: 10000 });
    await expect(diffModal.locator('#diff-modal-title')).toContainText('Declarative Code Diff Inspector');
    await expect(diffModal.locator('#diff-modal-title')).toContainText('UI-23');

    // Assert Baseline vs Synthesized plan sections
    await expect(diffModal.locator('text=GIT HEAD BASELINE')).toBeVisible({ timeout: 10000 });
    await expect(diffModal.locator('text=SYNTHESIZED EXECUTION PLAN').first()).toBeVisible();

    // Toggle between Side-by-Side and Unified Diff
    const unifiedBtn = diffModal.locator('button:has-text("Unified Diff")');
    await expect(unifiedBtn).toBeVisible();
    await unifiedBtn.click();
    await expect(diffModal.locator('text=UNIFIED DIFF')).toBeVisible({ timeout: 5000 });

    const sideBySideBtn = diffModal.locator('button:has-text("Side-by-Side")');
    await sideBySideBtn.click();
    await expect(diffModal.locator('text=GIT HEAD BASELINE')).toBeVisible();

    // Close diff modal
    const closeDiffBtn = diffModal.locator('button[aria-label="Close diff modal"]');
    try {
      await closeDiffBtn.click({ force: true, timeout: 3000 });
    } catch {
      await page.keyboard.press('Escape');
    }
    await expect(diffModal).not.toBeVisible();

    expect(consoleErrors).toEqual([]);
  });

  test('UI-27: Dual-Pane Split-Screen Terminal Replay against Golden Baseline', async ({ page }) => {
    const consoleErrors: string[] = [];
    page.on('console', (msg) => {
      if (msg.type() === 'error' && !msg.text().includes('favicon.ico')) {
        consoleErrors.push(msg.text());
      }
    });

    await setupAuth(page, TOKENS.bot);
    await page.goto('/chat');
    await expect(page).toHaveTitle(/Vulcan/i);

    // Select the completed task (EXEC-ADA50A) from TaskMonitor
    const successTask = page.locator('button:has-text("EXEC-ADA50A")').first();
    await expect(successTask).toBeVisible({ timeout: 20000 });
    await successTask.click();

    // The Dual Replay button should now be visible in JobDetail
    const splitReplayBtn = page.locator('[data-testid="job-detail-split-replay-btn"]');
    await expect(splitReplayBtn).toBeVisible({ timeout: 15000 });
    await splitReplayBtn.click();

    // Assert Dual Replay Modal opens
    const dualModal = page.locator('div[role="dialog"][aria-labelledby="dual-terminal-title"]');
    await expect(dualModal).toBeVisible({ timeout: 10000 });
    await expect(dualModal.locator('#dual-terminal-title')).toContainText('Dual-Pane Split-Screen Terminal Replay');
    await expect(dualModal.locator('#dual-terminal-title')).toContainText('UI-27');

    // Assert Golden baseline pane and live run pane
    await expect(dualModal.locator('text=GOLDEN BASELINE').first()).toBeVisible({ timeout: 10000 });
    await expect(dualModal.locator('text=ACTIVE STREAM').first()).toBeVisible();

    // Assert Sync Viewports button
    const syncBtn = dualModal.locator('button:has-text("Sync Viewports")');
    await expect(syncBtn).toBeVisible();

    // Close Dual Replay Modal
    const closeBtn = page.getByRole('button', { name: 'Close Replay' });
    await expect(closeBtn).toBeVisible({ timeout: 5000 });
    await closeBtn.click();
    await expect(dualModal).not.toBeVisible({ timeout: 5000 });

    expect(consoleErrors).toEqual([]);
  });
});
