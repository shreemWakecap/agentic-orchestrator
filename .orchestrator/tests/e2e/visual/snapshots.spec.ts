import { test, expect } from '@playwright/test';
import percySnapshot from '@percy/playwright';

/**
 * Percy Visual Regression Tests
 *
 * Captures visual snapshots of key pages for Percy.io visual regression testing.
 * These tests are designed to be run with `percy exec -- playwright test visual/`
 *
 * Pages covered:
 * - Plan list page (/plans)
 * - Plan detail page - empty state
 * - Plan detail page - with steps
 * - Build progress page (/runs/:id)
 */

test.describe('Visual Regression Tests', () => {
  test.describe('Plan List Page', () => {
    test('should capture plan list page snapshot', async ({ page }) => {
      await page.goto('/plans');
      await page.waitForLoadState('networkidle');

      // Wait for any animations to complete
      await page.waitForTimeout(500);

      // Capture Percy snapshot at configured viewport widths (1280, 768, 375)
      await percySnapshot(page, 'Plan List Page');
    });

    test('should capture plan list page with expanded plan', async ({ page }) => {
      await page.goto('/plans');
      await page.waitForLoadState('networkidle');

      // Find and expand the first plan item if available
      const planItem = page.locator('.plan-item').first();
      const planExists = await planItem.count() > 0;

      if (planExists) {
        // Click to expand the plan header
        await planItem.locator('.plan-header').click();
        await page.waitForTimeout(300); // Wait for expansion animation
      }

      await percySnapshot(page, 'Plan List Page - Expanded');
    });
  });

  test.describe('Plan Detail Page', () => {
    test('should capture plan detail page empty state', async ({ page }) => {
      // Navigate to plans list to check for available plans
      await page.goto('/plans');
      await page.waitForLoadState('networkidle');

      const planItem = page.locator('.plan-item').first();
      const planExists = await planItem.count() > 0;

      if (!planExists) {
        // Capture empty state - no plans available
        await percySnapshot(page, 'Plan Detail Page - Empty State (No Plans)');
        return;
      }

      // Get plan ID and navigate to detail page
      const planId = await planItem.getAttribute('data-plan-id');

      if (!planId) {
        test.skip(true, 'No plan ID available for testing');
        return;
      }

      await page.goto(`/plans/${planId}`);
      await page.waitForLoadState('networkidle');
      await page.waitForTimeout(500);

      // Check if this plan has minimal/no steps (empty-ish state)
      const stepElements = page.locator('.step-item, [data-testid="step"], li.step');
      const stepCount = await stepElements.count();

      if (stepCount === 0) {
        await percySnapshot(page, 'Plan Detail Page - Empty State');
      } else {
        // Capture as a regular detail page if steps exist
        await percySnapshot(page, 'Plan Detail Page - With Content');
      }
    });

    test('should capture plan detail page with steps', async ({ page }) => {
      await page.goto('/plans');
      await page.waitForLoadState('networkidle');

      // Find a plan with steps
      const planItems = page.locator('.plan-item');
      const planCount = await planItems.count();

      if (planCount === 0) {
        test.skip(true, 'No plans available for testing');
        return;
      }

      // Try to find a plan with steps by iterating through available plans
      let foundPlanWithSteps = false;

      for (let i = 0; i < Math.min(planCount, 5); i++) {
        const planItem = planItems.nth(i);
        const planId = await planItem.getAttribute('data-plan-id');

        if (!planId) continue;

        await page.goto(`/plans/${planId}`);
        await page.waitForLoadState('networkidle');

        // Check if this plan has steps/content
        const contentSection = page.locator('.markdown-content, [data-testid="plan-content"], .plan-content');
        const hasContent = await contentSection.count() > 0;

        if (hasContent) {
          const contentText = await contentSection.textContent();
          if (contentText && contentText.trim().length > 50) {
            foundPlanWithSteps = true;
            break;
          }
        }
      }

      if (!foundPlanWithSteps) {
        test.skip(true, 'No plans with steps available for testing');
        return;
      }

      await page.waitForTimeout(500);
      await percySnapshot(page, 'Plan Detail Page - With Steps');
    });

    test('should capture plan detail page action buttons', async ({ page }) => {
      await page.goto('/plans');
      await page.waitForLoadState('networkidle');

      const planItem = page.locator('.plan-item').first();
      const planExists = await planItem.count() > 0;

      if (!planExists) {
        test.skip(true, 'No plans available for testing');
        return;
      }

      const planId = await planItem.getAttribute('data-plan-id');
      if (!planId) {
        test.skip(true, 'No plan ID available');
        return;
      }

      await page.goto(`/plans/${planId}`);
      await page.waitForLoadState('networkidle');
      await page.waitForTimeout(500);

      // Capture the page with action buttons visible
      await percySnapshot(page, 'Plan Detail Page - Action Buttons');
    });
  });

  test.describe('Build Progress Page', () => {
    test('should capture build progress page', async ({ page }) => {
      // Navigate to runs list
      await page.goto('/runs');
      await page.waitForLoadState('networkidle');

      // Look for any available run
      const runLink = page.locator('a[href*="runs/"], [data-testid="run-item"] a, table tr td a').first();
      const runCount = await runLink.count();

      if (runCount === 0) {
        // Capture empty runs list instead
        await percySnapshot(page, 'Build Progress Page - No Runs Available');
        return;
      }

      // Navigate to the first run detail page
      await runLink.click();
      await page.waitForLoadState('networkidle');
      await page.waitForTimeout(500);

      await percySnapshot(page, 'Build Progress Page');
    });

    test('should capture build progress page with events', async ({ page }) => {
      await page.goto('/runs');
      await page.waitForLoadState('networkidle');

      const runLink = page.locator('a[href*="runs/"]').first();
      const runCount = await runLink.count();

      if (runCount === 0) {
        test.skip(true, 'No runs available for testing');
        return;
      }

      await runLink.click();
      await page.waitForLoadState('networkidle');

      // Check for event log entries
      const eventEntries = page.locator('[id="events-log"] > div, .events-log > div');
      const eventCount = await eventEntries.count();

      if (eventCount === 0) {
        test.skip(true, 'No events available in run');
        return;
      }

      await page.waitForTimeout(500);
      await percySnapshot(page, 'Build Progress Page - With Events');
    });

    test('should capture runs list page', async ({ page }) => {
      await page.goto('/runs');
      await page.waitForLoadState('networkidle');
      await page.waitForTimeout(500);

      await percySnapshot(page, 'Runs List Page');
    });
  });

  test.describe('Responsive Snapshots', () => {
    test('should capture mobile viewport snapshot of plan list', async ({ page }) => {
      // Set mobile viewport for this specific test
      await page.setViewportSize({ width: 375, height: 667 });

      await page.goto('/plans');
      await page.waitForLoadState('networkidle');
      await page.waitForTimeout(500);

      await percySnapshot(page, 'Plan List Page - Mobile Viewport', {
        widths: [375],
      });
    });

    test('should capture tablet viewport snapshot of plan detail', async ({ page }) => {
      await page.setViewportSize({ width: 768, height: 1024 });

      await page.goto('/plans');
      await page.waitForLoadState('networkidle');

      const planItem = page.locator('.plan-item').first();
      const planExists = await planItem.count() > 0;

      if (!planExists) {
        test.skip(true, 'No plans available for testing');
        return;
      }

      const planId = await planItem.getAttribute('data-plan-id');
      if (!planId) {
        test.skip(true, 'No plan ID available');
        return;
      }

      await page.goto(`/plans/${planId}`);
      await page.waitForLoadState('networkidle');
      await page.waitForTimeout(500);

      await percySnapshot(page, 'Plan Detail Page - Tablet Viewport', {
        widths: [768],
      });
    });
  });
});
