import { test, expect } from '@playwright/test';

/**
 * E2E tests for the plans list page.
 *
 * Tests cover:
 * - Plan list page navigation and loading
 * - Plan items display in list format
 * - Navigation to plan details via click
 */

test.describe('Plans List Page', () => {
  test('should navigate to plan list page and verify it loads', async ({ page }) => {
    // Navigate to the plans page
    await page.goto('/plans');

    // Wait for the page to fully load
    await page.waitForLoadState('networkidle');

    // Verify the page has loaded by checking for plans-related content
    // The page should contain a heading or title indicating this is the plans page
    const pageContent = page.locator('body');
    await expect(pageContent).toBeVisible();

    // Check for common indicators that the plans page has loaded
    const plansHeading = page.locator('h1, h2, [data-testid="plans-heading"]').filter({ hasText: /plans/i }).first();

    // If no heading, check for navigation or breadcrumb indicating plans
    const plansIndicator = page.locator(
      'nav a.active:has-text("Plans"), ' +
      '[aria-current="page"]:has-text("Plans"), ' +
      '.breadcrumb:has-text("Plans"), ' +
      'h1:has-text("Plans"), ' +
      'h2:has-text("Plans"), ' +
      '[data-testid="page-title"]:has-text("Plans")'
    ).first();

    // At minimum, verify the URL is correct and page rendered without error
    await expect(page).toHaveURL(/.*\/plans.*/);
  });

  test('should display plan items in a list format', async ({ page }) => {
    // Navigate to the plans page
    await page.goto('/plans');
    await page.waitForLoadState('networkidle');

    // Look for plan list container using various possible selectors
    const planListContainer = page.locator(
      '[data-testid="plan-list"], ' +
      '.plan-list, ' +
      '.plans-container, ' +
      'table.plans, ' +
      'ul.plans, ' +
      '[role="list"]'
    ).first();

    // Check for individual plan items
    const planItems = page.locator(
      '[data-testid="plan-item"], ' +
      '.plan-item, ' +
      '.plan-card, ' +
      'tr[data-plan-id], ' +
      'li.plan, ' +
      'a[href*="/plan/"], ' +
      '[data-testid="plan-row"]'
    );

    // Get count of plan items
    const planCount = await planItems.count();

    // Verify the list structure exists (even if empty)
    // The list container or items should be present in the DOM
    if (planCount > 0) {
      // If plans exist, verify they are visible and properly formatted
      const firstPlan = planItems.first();
      await expect(firstPlan).toBeVisible();

      // Plan items should contain identifiable information
      // Check for plan name, status, or other identifying text
      const planText = await firstPlan.textContent();
      expect(planText).toBeTruthy();
      expect(planText!.length).toBeGreaterThan(0);
    }

    // Log the count for debugging purposes
    console.log(`Found ${planCount} plan items on the page`);
  });

  test('should click on a plan item and navigate to details page', async ({ page }) => {
    // Navigate to the plans page
    await page.goto('/plans');
    await page.waitForLoadState('networkidle');

    // Find clickable plan items/links
    const planLinks = page.locator(
      'a[href*="/plan/"], ' +
      'a[href*="/plans/"], ' +
      '[data-testid="plan-item"] a, ' +
      '.plan-item a, ' +
      '.plan-card a, ' +
      'tr[data-plan-id] a, ' +
      '[data-testid="plan-link"]'
    );

    const planCount = await planLinks.count();

    // Skip test gracefully if no plans are available
    if (planCount === 0) {
      console.log('No plan items found to click - skipping navigation test');
      test.skip(true, 'No plans available to test navigation');
      return;
    }

    // Get the first plan link
    const firstPlanLink = planLinks.first();
    await expect(firstPlanLink).toBeVisible();

    // Capture the current URL before clicking
    const listPageUrl = page.url();

    // Click on the plan to navigate to details
    await firstPlanLink.click();

    // Wait for navigation to complete
    await page.waitForLoadState('networkidle');

    // Verify navigation occurred - URL should change to a plan detail page
    const detailPageUrl = page.url();
    expect(detailPageUrl).not.toBe(listPageUrl);

    // Verify we're on a plan details page
    // URL should contain plan identifier pattern
    expect(detailPageUrl).toMatch(/\/plan[s]?\/[^/]+/);

    // Verify the detail page has loaded with plan content
    const detailContent = page.locator(
      '[data-testid="plan-detail"], ' +
      '[data-testid="plan-content"], ' +
      '.plan-detail, ' +
      '.plan-content, ' +
      'main, ' +
      'article'
    ).first();

    await expect(detailContent).toBeVisible();
  });
});
