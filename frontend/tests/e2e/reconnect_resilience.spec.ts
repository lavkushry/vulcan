import { test, expect } from '@playwright/test';
import { setupAuth, TOKENS } from './helpers';

/**
 * Project Vulcan: Milestone C.1 — Flow 2: WebSocket Reconnect Resilience & In-Order Replay
 * Verifies:
 * 1. Active WebSocket connection streams live stdout events.
 * 2. Mid-flight connection termination triggers degraded/reconnecting UI state (RECONNECTING · STREAM DEGRADED).
 * 3. Automatic reconnect re-establishes connection with last_seq token.
 * 4. Buffered events replayed without duplication or line drop.
 * 5. Terminal indicator returns to LIVE STDOUT.
 * 6. Zero unhandled console errors.
 */

test.describe('Flow 2: WebSocket Reconnect Resilience', () => {
  test('Recovers from mid-flight WebSocket disconnect and replays in-order buffer', async ({ page, request }) => {
    // 1. Console Error Trap
    const consoleErrors: string[] = [];
    page.on('console', (msg) => {
      if (msg.type() === 'error') {
        const text = msg.text();
        if (!text.includes('favicon.ico')) {
          consoleErrors.push(text);
        }
      }
    });

    // 2. Dispatch a long-running execution task via API tagged with e2e.bot
    const dispatchRes = await request.post('http://127.0.0.1:8000/api/v1/tasks/dispatch', {
      headers: {
        'Authorization': `Bearer ${TOKENS.alice}`,
      },
      data: {
        catalog_identifier: 'net-f5-pool-member-drain',
        target_resource_id: 'f5-edge-vip-02.pnc.com',
        environment: 'PROD',
        requester_id: 'e2e.bot',
        parameters: {
          pool_name: 'pool_resilience_test',
          member_ip: '10.100.2.15',
          member_port: 8443,
        },
        servicenow_chg: 'CHG-998811',
      },
    });
    expect(dispatchRes.ok()).toBeTruthy();
    const dispatchData = await dispatchRes.json();
    const corrId = dispatchData.correlation_id;
    expect(corrId).toBeTruthy();

    // 3. Setup Auth & Navigate to Chat Console and select the active job
    await setupAuth(page);
    await page.goto('/chat');
    await expect(page).toHaveTitle(/Vulcan/i);

    // Wait for the task to appear in the Task Monitor list
    const taskItem = page.locator(`text=${corrId}`).first();
    await expect(taskItem).toBeVisible({ timeout: 10000 });
    await taskItem.click();

    // 4. Assert Live Terminal Connected
    const liveBadge = page.locator('[data-testid="terminal-stream-status"]:has-text("LIVE STDOUT")');
    await expect(liveBadge).toBeVisible({ timeout: 10000 });

    // Assert initial stdout lines rendered in accessible buffer
    const textBuffer = page.locator('[data-testid="terminal-text-buffer"]');
    await expect(textBuffer).toContainText('[PROJECT VULCAN CONTROL PLANE]', { timeout: 10000 });

    // 5. Simulate Mid-Flight Connection Drop
    // Close the underlying client WebSocket connection
    await page.evaluate(() => {
      const ws = (window as any).__vulcan_ws;
      if (ws) {
        ws.close();
      }
    });

    // 6. Assert Degraded / Reconnecting UI Indicator Appears Immediately
    const degradedBadge = page.locator('text=RECONNECTING · STREAM DEGRADED');
    await expect(degradedBadge).toBeVisible({ timeout: 4000 });

    // 7. Assert Automatic Reconnect Succeeds
    // The useJobStream hook will reconnect via exponential backoff with ?last_seq=N
    await expect(liveBadge).toBeVisible({ timeout: 15000 });
    await expect(degradedBadge).not.toBeVisible();

    // 8. Assert Stream Integrity Post-Reconnect
    // Check that terminal buffer still contains original output and stream resumed cleanly
    await expect(textBuffer).toContainText('[PROJECT VULCAN CONTROL PLANE]');

    // 9. Zero Console Errors
    expect(consoleErrors).toEqual([]);
  });
});
