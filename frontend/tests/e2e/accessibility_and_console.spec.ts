import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import { setupAuth } from './helpers';

/**
 * Project Vulcan: Automated Accessibility & Browser Console Baseline Audit
 *
 * Scope & Limitations:
 * 1. Verifies primary console views load with zero unhandled browser console errors.
 * 2. Runs automated Axe-core checks scoped to critical and serious violations under
 *    WCAG 2.0 / 2.1 AA tags (wcag2a, wcag2aa, wcag21a, wcag21aa).
 * 3. Color-contrast heuristic is disabled due to transparent backdrop-filter/glassmorphism
 *    surfaces which confuse DOM-tree contrast calculators, and .xterm canvas is excluded.
 * 4. This is an automated CI smoke gate for structural a11y (ARIA, landmarks, roles, button names),
 *    NOT an exhaustive full WCAG 2.2 manual conformance certification.
 */

const CORE_PAGES = [
  { path: '/chat', name: 'AI Chat Assistant' },
  { path: '/actions', name: 'Actions Task Monitor' },
  { path: '/matrix', name: 'Task Matrix & Policies' },
  { path: '/history', name: 'Attestation History & Audit' },
  { path: '/dashboard', name: 'Mission Control Dashboard' },
];

test.describe('Platform Quality: Zero Console Errors & Automated WCAG 2.1 AA Structural Audit', () => {
  for (const pageInfo of CORE_PAGES) {
    test(`${pageInfo.name} (${pageInfo.path}) loads cleanly with 0 console errors and 0 critical/serious a11y violations`, async ({ page }) => {
      const consoleErrors: string[] = [];
      page.on('console', (msg) => {
        if (msg.type() === 'error') {
          const text = msg.text();
          if (!text.includes('favicon.ico')) {
            consoleErrors.push(text);
          }
        }
      });

      await setupAuth(page);
      await page.goto(pageInfo.path, { waitUntil: 'domcontentloaded' });
      await page.waitForLoadState('domcontentloaded');
      await page.waitForSelector('main, header', { state: 'visible' });

      // Verify zero console errors
      expect(consoleErrors).toEqual([]);

      // Axe-core Accessibility Scan
      // Exclude xterm canvas and disable alpha/glassmorphism color-contrast heuristics
      const accessibilityScanResults = await new AxeBuilder({ page })
        .exclude('.xterm')
        .disableRules(['color-contrast'])
        .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'])
        .analyze();

      // Filter critical and serious violations
      const criticalViolations = accessibilityScanResults.violations.filter(
        (v) => v.impact === 'critical' || v.impact === 'serious'
      );

      if (criticalViolations.length > 0) {
        console.warn(
          `[A11y Violations on ${pageInfo.path}]:`,
          JSON.stringify(criticalViolations.map((v) => ({ id: v.id, impact: v.impact, description: v.description })), null, 2)
        );
      }

      expect(criticalViolations).toEqual([]);
    });
  }
});
