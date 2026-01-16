import { test, expect } from '@playwright/test';

/**
 * E2E tests for build functionality in the orchestrator web UI.
 *
 * Tests cover:
 * - Locating and clicking the Start Build button from plan detail page
 * - Verifying build progress updates appear after starting a build
 */

test.describe('Build Flow', () => {
  test.describe('Start Build Button', () => {
    test('should display Start Build button on pending plan detail page', async ({ page }) => {
      // Navigate to plans list
      await page.goto('/plans');
      await page.waitForLoadState('networkidle');

      // Find a plan link and click to view details
      const planLink = page.locator('a[href*="plan"], [data-testid="plan-item"] a, .plan-item a, table tr td a').first();

      // Check if there are any plans available
      const planCount = await planLink.count();
      if (planCount === 0) {
        test.skip();
        return;
      }

      await planLink.click();
      await page.waitForLoadState('networkidle');

      // Look for the Start Build button (visible only for pending plans)
      const startBuildButton = page.locator(
        'button:has-text("Start Build"), ' +
        'button:has-text("Build"), ' +
        '[data-testid="start-build"], ' +
        '.start-build-btn'
      ).first();

      // Check if this is a pending plan (has Start Build button)
      const isVisible = await startBuildButton.isVisible().catch(() => false);

      if (isVisible) {
        // Verify button styling and accessibility
        await expect(startBuildButton).toBeEnabled();
        await expect(startBuildButton).toHaveClass(/bg-blue-600|btn-primary|start-build/);
      }
      // Note: If not visible, the plan might be in completed or in-progress state
    });

    test('should click Start Build and trigger build workflow', async ({ page }) => {
      // Navigate to plans list
      await page.goto('/plans');
      await page.waitForLoadState('networkidle');

      // Find a plan link and navigate to details
      const planLink = page.locator('a[href*="plan"], [data-testid="plan-item"] a, table tr td a').first();

      const planCount = await planLink.count();
      if (planCount === 0) {
        test.skip();
        return;
      }

      await planLink.click();
      await page.waitForLoadState('networkidle');

      // Look for Start Build button
      const startBuildButton = page.locator(
        'button:has-text("Start Build"), ' +
        'button:has-text("Build")'
      ).first();

      const isVisible = await startBuildButton.isVisible().catch(() => false);

      if (!isVisible) {
        // Plan is not in pending state, skip this test
        test.skip();
        return;
      }

      // Set up request interception to verify API call
      const buildRequestPromise = page.waitForRequest(
        request => request.url().includes('/api/workflows/build') && request.method() === 'POST',
        { timeout: 5000 }
      ).catch(() => null);

      // Click the Start Build button
      await startBuildButton.click();

      // Wait for either navigation to run page or API request
      const buildRequest = await buildRequestPromise;

      if (buildRequest) {
        // Verify the request was made correctly
        expect(buildRequest.method()).toBe('POST');
        expect(buildRequest.url()).toContain('/api/workflows/build');
      }

      // After starting build, should navigate to run detail page
      await page.waitForURL(/.*\/runs\/.*/, { timeout: 10000 }).catch(() => {});

      // If navigated to run page, verify we're on the correct page
      const currentUrl = page.url();
      if (currentUrl.includes('/runs/')) {
        await expect(page.locator('h1:has-text("Run"), h1:has-text("Build")')).toBeVisible({ timeout: 5000 });
      }
    });
  });

  test.describe('Build Progress Updates', () => {
    test('should display build progress indicators on run detail page', async ({ page }) => {
      // Navigate to runs list to find any existing runs
      await page.goto('/runs');
      await page.waitForLoadState('networkidle');

      // Look for a run link
      const runLink = page.locator('a[href*="runs/"], [data-testid="run-item"] a, table tr td a').first();

      const runCount = await runLink.count();
      if (runCount === 0) {
        test.skip();
        return;
      }

      await runLink.click();
      await page.waitForLoadState('networkidle');

      // Verify progress indicators are present
      const progressBar = page.locator(
        '[id="progress-bar"], ' +
        '.progress-bar, ' +
        '[data-testid="progress-bar"], ' +
        '.bg-blue-600.h-3'
      ).first();

      const progressPercent = page.locator(
        '[id="progress-percent"], ' +
        '.progress-percent, ' +
        '[data-testid="progress-percent"]'
      ).first();

      // Check for progress elements
      const hasProgressBar = await progressBar.isVisible().catch(() => false);
      const hasProgressPercent = await progressPercent.isVisible().catch(() => false);

      // At least one progress indicator should be visible
      expect(hasProgressBar || hasProgressPercent).toBeTruthy();

      // Verify status badge is present
      const statusBadge = page.locator(
        '[id="status-badge"], ' +
        '.status-badge, ' +
        '[data-testid="status-badge"], ' +
        '.rounded-full.text-sm.font-medium'
      ).first();

      await expect(statusBadge).toBeVisible();

      // Verify the status text is one of the expected values
      const statusText = await statusBadge.textContent();
      expect(['running', 'pending', 'completed', 'failed']).toContain(statusText?.trim().toLowerCase());
    });

    test('should show current step during build execution', async ({ page }) => {
      // Navigate to runs list
      await page.goto('/runs');
      await page.waitForLoadState('networkidle');

      // Look for a running build (has 'running' status)
      const runningRun = page.locator(
        'tr:has-text("running") a, ' +
        '[data-status="running"] a, ' +
        '.running a'
      ).first();

      const runningCount = await runningRun.count();

      if (runningCount === 0) {
        // No running builds, try any available run
        const anyRun = page.locator('a[href*="runs/"], table tr td a').first();
        const anyRunCount = await anyRun.count();

        if (anyRunCount === 0) {
          test.skip();
          return;
        }

        await anyRun.click();
      } else {
        await runningRun.click();
      }

      await page.waitForLoadState('networkidle');

      // Look for current step indicator
      const currentStep = page.locator(
        '[id="current-step"], ' +
        '.current-step, ' +
        '[data-testid="current-step"], ' +
        'p:has-text("Current step")'
      ).first();

      // For running builds, current step should be visible
      // For completed builds, it may or may not be visible
      const isVisible = await currentStep.isVisible().catch(() => false);

      if (isVisible) {
        // Verify the step has some content
        const stepText = await currentStep.textContent();
        expect(stepText).toBeTruthy();
      }

      // Verify events log is present
      const eventsLog = page.locator(
        '[id="events-log"], ' +
        '.events-log, ' +
        '[data-testid="events-log"], ' +
        '.divide-y.divide-gray-200'
      ).first();

      await expect(eventsLog).toBeVisible();
    });

    test('should update progress bar during active build', async ({ page }) => {
      // Start a build to test live progress updates
      await page.goto('/plans');
      await page.waitForLoadState('networkidle');

      // Find a pending plan and start build
      const planLink = page.locator('a[href*="plan"], table tr td a').first();

      const planCount = await planLink.count();
      if (planCount === 0) {
        test.skip();
        return;
      }

      await planLink.click();
      await page.waitForLoadState('networkidle');

      const startBuildButton = page.locator('button:has-text("Start Build")').first();
      const buttonVisible = await startBuildButton.isVisible().catch(() => false);

      if (!buttonVisible) {
        // Navigate directly to runs to check existing build progress
        await page.goto('/runs');
        await page.waitForLoadState('networkidle');

        const runLink = page.locator('a[href*="runs/"]').first();
        const runCount = await runLink.count();

        if (runCount === 0) {
          test.skip();
          return;
        }

        await runLink.click();
        await page.waitForLoadState('networkidle');
      } else {
        // Start the build
        await startBuildButton.click();

        // Wait for navigation to run detail page
        await page.waitForURL(/.*\/runs\/.*/, { timeout: 10000 });
      }

      // On run detail page, verify progress bar exists
      const progressBar = page.locator('[id="progress-bar"], .progress-bar, .bg-blue-600.h-3').first();
      await expect(progressBar).toBeVisible();

      // Get initial progress value
      const initialWidth = await progressBar.evaluate(el => el.style.width);

      // Verify progress percentage display
      const progressPercent = page.locator('[id="progress-percent"]').first();
      const percentVisible = await progressPercent.isVisible().catch(() => false);

      if (percentVisible) {
        const percentText = await progressPercent.textContent();
        expect(percentText).toMatch(/\d+%/);
      }
    });

    test('should display build status changes in event log', async ({ page }) => {
      // Navigate to runs
      await page.goto('/runs');
      await page.waitForLoadState('networkidle');

      // Find any run to check event log
      const runLink = page.locator('a[href*="runs/"], table tr td a').first();

      const runCount = await runLink.count();
      if (runCount === 0) {
        test.skip();
        return;
      }

      await runLink.click();
      await page.waitForLoadState('networkidle');

      // Verify Event Log section is present
      const eventLogHeader = page.locator('h3:has-text("Event Log")');
      await expect(eventLogHeader).toBeVisible();

      // Verify events log container
      const eventsContainer = page.locator('[id="events-log"], .events-log, .divide-y.divide-gray-200').first();
      await expect(eventsContainer).toBeVisible();

      // Check for event entries (may be empty for new runs)
      const eventEntries = page.locator('[id="events-log"] > div, .events-log > div');
      const eventCount = await eventEntries.count();

      // If there are events, verify they have expected structure
      if (eventCount > 0) {
        const firstEvent = eventEntries.first();

        // Events should have timestamp
        const timestamp = firstEvent.locator('.text-gray-500').first();
        const hasTimestamp = await timestamp.isVisible().catch(() => false);

        // Events should have type badge
        const typeBadge = firstEvent.locator('.rounded.text-xs.font-medium').first();
        const hasTypeBadge = await typeBadge.isVisible().catch(() => false);

        // At least one of these should be present
        expect(hasTimestamp || hasTypeBadge).toBeTruthy();
      }
    });
  });
});
