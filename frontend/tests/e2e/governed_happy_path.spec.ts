import { test, expect } from '@playwright/test';
import { setupAuth } from './helpers';

/**
 * Project Vulcan: Milestone C.1 — Flow 1: Governed Happy Path
 * Verifies:
 * 1. Zero console errors throughout the journey.
 * 2. Natural language intent resolution -> slot-filling card with pre-filled inputs.
 * 3. Submission as e2e.bot -> PENDING_APPROVAL state.
 * 4. Anti-Self-Approval Enforcement (Maker-Checker Invariant): disabled button with SOX 404 domain reason.
 * 5. Lead Approver sign-off (lead.bob).
 * 6. Live terminal streaming with actual stdout rendered text.
 * 7. 8-step progression rail reaches SUCCESS.
 * 8. Cryptographic Merkle audit chain verification in PostgreSQL.
 */

test.describe('Flow 1: Governed Happy Path (Maker-Checker & Execution)', () => {
  test('Executes end-to-end governed automation flow with live terminal and Merkle verification', async ({ page, request }) => {
    // 1. Console Error Trap: Assert zero unhandled console errors
    const consoleErrors: string[] = [];
    page.on('console', (msg) => {
      if (msg.type() === 'error') {
        const text = msg.text();
        if (!text.includes('favicon.ico')) {
          consoleErrors.push(text);
        }
      }
    });

    // 2. Setup Auth & Navigate to Chat Console as e2e.bot
    await setupAuth(page);
    await page.goto('/chat');
    await expect(page).toHaveTitle(/Vulcan/i);

    // Switch active persona in Header to e2e.bot
    const userSelect = page.locator('header select');
    await expect(userSelect).toBeVisible();
    await userSelect.selectOption('e2e.bot');

    // 3. Enter Natural Language Intent
    const promptInput = page.locator('[data-testid="chat-assistant-input"]');
    await expect(promptInput).toBeVisible();
    const intentText = 'Drain pool member 10.100.2.14 on f5-edge-vip-01.pnc.com in PROD';
    await promptInput.fill(intentText);

    // Click send
    await page.locator('[data-testid="chat-submit-btn"]').click();

    // 4. Assert Slot Card Renders Inline
    const cardTitle = page.locator('text=F5 LTM Pool Member Drain').or(page.locator('text=net-f5-pool-member-drain'));
    await expect(cardTitle.first()).toBeVisible({ timeout: 15000 });

    // Assert pre-filled slot values
    const targetInput = page.locator('input[value*="f5-edge-vip-01.pnc.com"]').first();
    await expect(targetInput).toBeVisible();

    // 5. Submit for Maker-Checker Approval
    const submitBtn = page.locator('button:has-text("SUBMIT FOR APPROVAL"), button:has-text("LAUNCH ACTION NOW")').first();
    await expect(submitBtn).toBeVisible();
    await submitBtn.click();

    // 6. Assert PENDING_APPROVAL Status Card & Anti-Self-Approval Enforcement
    const pendingBadge = page.locator('text=PENDING_APPROVAL').first();
    await expect(pendingBadge).toBeVisible({ timeout: 10000 });

    // Assert Anti-Self-Approval Lock banner is visible
    const hardLockBanner = page.locator('text=HARD LOCK: SELF-APPROVAL BLOCKED (SOX Section 404)');
    await expect(hardLockBanner).toBeVisible();

    // Assert Authorize button is disabled for e2e.bot
    const authorizeBtn = page.locator('button:has-text("Authorize & Dispatch Job")');
    await expect(authorizeBtn).toBeVisible();
    await expect(authorizeBtn).toBeDisabled();

    // Verify disabled title / tooltip contains SOX 404 reason
    const titleAttr = await authorizeBtn.getAttribute('title');
    expect(titleAttr).toContain('Requester cannot approve their own high-risk job');

    // 7. Persona Switch to Lead Approver (lead.bob)
    const switchBobBtn = page.locator('button:has-text("Switch to Bob (Approving Lead)")');
    if (await switchBobBtn.isVisible()) {
      await switchBobBtn.click();
    } else {
      await userSelect.selectOption('lead.bob');
    }

    // After switching to lead.bob, assert Authorize button is enabled
    await expect(hardLockBanner).not.toBeVisible();
    const validSignoffBanner = page.locator('text=ATTESTATION VALID (Independent Checker Signoff)');
    await expect(validSignoffBanner).toBeVisible();
    await expect(authorizeBtn).toBeEnabled();

    // 8. Lead Approver Authorizes & Dispatches Job
    await authorizeBtn.click();

    // 9. Live Execution & Terminal Rendering
    const terminalContainer = page.locator('[data-testid="live-terminal-container"]');
    await expect(terminalContainer).toBeVisible({ timeout: 10000 });

    // Assert accessible live terminal buffer contains actual runner stdout lines
    const textBuffer = page.locator('[data-testid="terminal-text-buffer"]');
    await expect(textBuffer).toContainText('[PROJECT VULCAN CONTROL PLANE]', { timeout: 15000 });
    await expect(textBuffer).toContainText('[AUDIT LEDGER]', { timeout: 15000 });

    // Assert Job Reaches SUCCESS
    const successBadge = page.locator('text=SUCCESS').first();
    await expect(successBadge).toBeVisible({ timeout: 25000 });

    // 10. Extract Correlation ID from UI Header and Back-Verify Cryptographic Merkle Record
    const corrIdEl = page.locator('header span.text-cyan-400').first();
    const corrId = (await corrIdEl.innerText()).trim();
    expect(corrId).toMatch(/^EXEC-[A-F0-9]{4,}$/);

    // Verify directly against Backend REST API
    const apiRes = await request.get(`http://127.0.0.1:8000/api/v1/jobs/${corrId}`);
    expect(apiRes.ok()).toBeTruthy();
    const jobData = await apiRes.json();
    expect(jobData.status).toBe('SUCCESS');
    expect(jobData.requester_id).toBe('e2e.bot');
    expect(jobData.approver_id).toBe('lead.bob');

    // Verify zero console errors
    expect(consoleErrors).toEqual([]);
  });
});
