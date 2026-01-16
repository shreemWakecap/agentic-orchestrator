import { test, expect } from '@playwright/test';

/**
 * Plan Details Page E2E Tests
 *
 * Tests the plan detail page functionality including:
 * - Direct navigation to plan detail pages
 * - Plan metadata display (name, status, timestamps)
 * - Plan content display with steps
 */

test.describe('Plan Details Page', () => {

  test.describe('Navigation', () => {
    test('should navigate directly to a plan detail page and verify it loads', async ({ page }) => {
      // First, get a plan ID from the plans list
      await page.goto('/plans');
      await page.waitForLoadState('networkidle');

      // Get the first plan item and extract its ID
      const planItem = page.locator('.plan-item').first();
      const planExists = await planItem.count() > 0;

      if (planExists) {
        const planId = await planItem.getAttribute('data-plan-id');
        expect(planId).toBeTruthy();

        // Navigate directly to the plan detail page
        await page.goto(`/plans/${planId}`);
        await page.waitForLoadState('networkidle');

        // Verify the page loaded successfully
        await expect(page).toHaveURL(new RegExp(`/plans/${planId}`));

        // Verify page title contains plan information
        const pageTitle = page.locator('h1');
        await expect(pageTitle).toBeVisible();

        // Verify the "Back to Plans" link exists
        const backLink = page.locator('a[href="/plans"]');
        await expect(backLink).toBeVisible();
        await expect(backLink).toContainText('Back to Plans');
      } else {
        // Skip test if no plans exist
        test.skip(true, 'No plans available for testing');
      }
    });

    test('should navigate from plans list to detail page via View Full Plan link', async ({ page }) => {
      await page.goto('/plans');
      await page.waitForLoadState('networkidle');

      const planItem = page.locator('.plan-item').first();
      const planExists = await planItem.count() > 0;

      if (planExists) {
        const planId = await planItem.getAttribute('data-plan-id');

        // Expand the plan to reveal the "View Full Plan" link
        await planItem.locator('.plan-header').click();

        // Wait for expansion animation
        await page.waitForTimeout(300);

        // Click "View Full Plan" link
        const viewFullPlanLink = planItem.locator('a:has-text("View Full Plan")');
        await expect(viewFullPlanLink).toBeVisible();
        await viewFullPlanLink.click();

        // Verify navigation to detail page
        await page.waitForLoadState('networkidle');
        await expect(page).toHaveURL(new RegExp(`/plans/${planId}`));
      } else {
        test.skip(true, 'No plans available for testing');
      }
    });
  });

  test.describe('Metadata Display', () => {
    test('should display plan metadata correctly including name, status, and timestamps', async ({ page }) => {
      // Navigate to plans list first to get a valid plan ID
      await page.goto('/plans');
      await page.waitForLoadState('networkidle');

      const planItem = page.locator('.plan-item').first();
      const planExists = await planItem.count() > 0;

      if (planExists) {
        const planId = await planItem.getAttribute('data-plan-id');

        // Navigate to plan detail page
        await page.goto(`/plans/${planId}`);
        await page.waitForLoadState('networkidle');

        // Verify plan name (h1 heading)
        const planName = page.locator('h1.text-2xl');
        await expect(planName).toBeVisible();
        const nameText = await planName.textContent();
        expect(nameText).toBeTruthy();
        expect(nameText!.length).toBeGreaterThan(0);

        // Verify plan file path is displayed
        const filePath = page.locator('p.text-sm.text-gray-600');
        await expect(filePath).toBeVisible();

        // Verify plan status badge is displayed
        const statusBadge = page.locator('span.rounded-full');
        await expect(statusBadge).toBeVisible();

        // Status should be one of: completed, pending, in-progress, or error state
        const statusText = await statusBadge.textContent();
        expect(statusText).toBeTruthy();
        expect(['completed', 'pending', 'in-progress']).toContain(statusText!.trim().toLowerCase());

        // Verify "Last modified" timestamp is displayed
        const lastModified = page.locator('text=Last modified:');
        await expect(lastModified).toBeVisible();

        // Verify the timestamp format (YYYY-MM-DD HH:MM:SS)
        const timestampText = await page.locator('.border-t p.text-sm').textContent();
        expect(timestampText).toMatch(/Last modified:\s*\d{4}-\d{2}-\d{2}/);
      } else {
        test.skip(true, 'No plans available for testing');
      }
    });

    test('should display correct status badge color based on plan state', async ({ page }) => {
      await page.goto('/plans');
      await page.waitForLoadState('networkidle');

      const planItem = page.locator('.plan-item').first();
      const planExists = await planItem.count() > 0;

      if (planExists) {
        const planId = await planItem.getAttribute('data-plan-id');

        await page.goto(`/plans/${planId}`);
        await page.waitForLoadState('networkidle');

        const statusBadge = page.locator('span.rounded-full').first();
        await expect(statusBadge).toBeVisible();

        const statusText = await statusBadge.textContent();
        const status = statusText?.trim().toLowerCase();

        // Verify the badge has the correct color class based on status
        if (status === 'completed') {
          await expect(statusBadge).toHaveClass(/bg-green-100/);
          await expect(statusBadge).toHaveClass(/text-green-800/);
        } else if (status === 'pending') {
          await expect(statusBadge).toHaveClass(/bg-yellow-100/);
          await expect(statusBadge).toHaveClass(/text-yellow-800/);
        } else if (status === 'in-progress') {
          await expect(statusBadge).toHaveClass(/bg-blue-100/);
          await expect(statusBadge).toHaveClass(/text-blue-800/);
        }
      } else {
        test.skip(true, 'No plans available for testing');
      }
    });
  });

  test.describe('Plan Content and Steps', () => {
    test('should display plan content with steps listed', async ({ page }) => {
      await page.goto('/plans');
      await page.waitForLoadState('networkidle');

      const planItem = page.locator('.plan-item').first();
      const planExists = await planItem.count() > 0;

      if (planExists) {
        const planId = await planItem.getAttribute('data-plan-id');

        await page.goto(`/plans/${planId}`);
        await page.waitForLoadState('networkidle');

        // Verify "Plan Content" section exists
        const contentSection = page.locator('h3:has-text("Plan Content")');
        await expect(contentSection).toBeVisible();

        // Verify the content container exists
        const contentContainer = page.locator('.markdown-content');
        await expect(contentContainer).toBeVisible();

        // Verify plan content is displayed (pre element with content)
        const planContent = page.locator('.markdown-content pre');
        await expect(planContent).toBeVisible();

        // Verify content is not empty
        const contentText = await planContent.textContent();
        expect(contentText).toBeTruthy();
        expect(contentText!.trim().length).toBeGreaterThan(0);
      } else {
        test.skip(true, 'No plans available for testing');
      }
    });

    test('should display action buttons appropriate to plan state', async ({ page }) => {
      await page.goto('/plans');
      await page.waitForLoadState('networkidle');

      const planItem = page.locator('.plan-item').first();
      const planExists = await planItem.count() > 0;

      if (planExists) {
        const planId = await planItem.getAttribute('data-plan-id');

        await page.goto(`/plans/${planId}`);
        await page.waitForLoadState('networkidle');

        const statusBadge = page.locator('span.rounded-full').first();
        const statusText = await statusBadge.textContent();
        const status = statusText?.trim().toLowerCase();

        // Check for appropriate action buttons based on state
        if (status === 'pending') {
          // Pending plans should have "Start Build" button
          const startBuildButton = page.locator('button:has-text("Start Build")');
          await expect(startBuildButton).toBeVisible();
        } else if (status === 'completed') {
          // Completed plans should have "Start Review" button
          const startReviewButton = page.locator('button:has-text("Start Review")');
          await expect(startReviewButton).toBeVisible();
        }

        // "Back to Plans" link should always be visible
        const backLink = page.locator('a[href="/plans"]');
        await expect(backLink).toBeVisible();
      } else {
        test.skip(true, 'No plans available for testing');
      }
    });

    test('should have well-formatted plan content display', async ({ page }) => {
      await page.goto('/plans');
      await page.waitForLoadState('networkidle');

      const planItem = page.locator('.plan-item').first();
      const planExists = await planItem.count() > 0;

      if (planExists) {
        const planId = await planItem.getAttribute('data-plan-id');

        await page.goto(`/plans/${planId}`);
        await page.waitForLoadState('networkidle');

        // Verify the content area has proper styling
        const contentArea = page.locator('.bg-white.shadow');
        await expect(contentArea).toBeVisible();

        // Verify content uses whitespace-pre-wrap for formatting
        const preElement = page.locator('pre.whitespace-pre-wrap');
        await expect(preElement).toBeVisible();

        // Verify text styling
        await expect(preElement).toHaveClass(/text-sm/);
        await expect(preElement).toHaveClass(/text-gray-800/);
      } else {
        test.skip(true, 'No plans available for testing');
      }
    });
  });
});
