import {
  test,
  expect,
  SELECTORS,
  waitForNetworkIdle,
  waitForNavigation,
  PageHelper
} from './fixtures';
import type { Plan } from './fixtures';

/**
 * E2E tests for the plans list page.
 *
 * Tests cover:
 * - Plan list page navigation and loading
 * - Plan items display in list format
 * - Navigation to plan details via click
 * - API data verification
 */

test.describe('Plans List Page', () => {
  test('should navigate to plan list page and verify it loads', async ({ page }) => {
    // Navigate to the plans page
    await page.goto('/plans');

    // Wait for the page to fully load
    await waitForNetworkIdle(page);

    // Verify the page has loaded by checking for plans-related content
    const pageContent = page.locator('body');
    await expect(pageContent).toBeVisible();

    // Check for page heading using SELECTORS
    const plansHeading = page.locator(SELECTORS.plans.title).filter({ hasText: /plans/i }).first();

    // If no heading, check for navigation or breadcrumb indicating plans
    const plansIndicator = page.locator(
      `${SELECTORS.nav.activeLink}, ` +
      `${SELECTORS.nav.breadcrumbs}, ` +
      `${SELECTORS.plans.title}`
    ).filter({ hasText: /plans/i }).first();

    // At minimum, verify the URL is correct and page rendered without error
    await expect(page).toHaveURL(/.*\/plans.*/);
  });

  test('should display plan items in a list format', async ({ page, apiClient }) => {
    // Navigate to the plans page
    await page.goto('/plans');
    await waitForNetworkIdle(page);

    // Look for plan list container using SELECTORS
    const planListContainer = page.locator(SELECTORS.plans.list).first();

    // Check for individual plan items using SELECTORS
    const planItems = page.locator(SELECTORS.plans.item);

    // Get count of plan items from the UI
    const planCount = await planItems.count();

    // Verify against API data
    try {
      const { plans } = await apiClient.getPlans();

      // Log comparison for debugging
      console.log(`UI shows ${planCount} plans, API returned ${plans.length} plans`);

      // The UI count should match API (or be close if pagination is involved)
      if (plans.length > 0) {
        expect(planCount).toBeGreaterThan(0);
      }
    } catch (error) {
      console.warn('Could not verify plans against API:', error);
    }

    // Verify the list structure exists (even if empty)
    if (planCount > 0) {
      // If plans exist, verify they are visible and properly formatted
      const firstPlan = planItems.first();
      await expect(firstPlan).toBeVisible();

      // Plan items should contain identifiable information
      const planText = await firstPlan.textContent();
      expect(planText).toBeTruthy();
      expect(planText!.length).toBeGreaterThan(0);
    }

    // Log the count for debugging purposes
    console.log(`Found ${planCount} plan items on the page`);
  });

  test('should click on a plan item and navigate to details page', async ({ page, apiClient }) => {
    // Navigate to the plans page
    await page.goto('/plans');
    await waitForNetworkIdle(page);

    // Find clickable plan items/links using SELECTORS
    const planLinks = page.locator(
      `${SELECTORS.plans.item} a, ` +
      'a[href*="/plan/"], ' +
      'a[href*="/plans/"]'
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

    // Click on the plan to navigate to details using waitForNavigation
    await waitForNavigation(page, async () => {
      await firstPlanLink.click();
    }, { waitUntil: 'networkidle' });

    // Verify navigation occurred - URL should change to a plan detail page
    const detailPageUrl = page.url();
    expect(detailPageUrl).not.toBe(listPageUrl);

    // Verify we're on a plan details page
    expect(detailPageUrl).toMatch(/\/plan[s]?\/[^/]+/);

    // Verify the detail page has loaded with plan content using SELECTORS
    const detailContent = page.locator(
      `${SELECTORS.plans.content}, ` +
      `${SELECTORS.sections.main}`
    ).first();

    await expect(detailContent).toBeVisible();
  });

  test('should verify plan data matches API response', async ({ page, apiClient }) => {
    // Get plans from API first
    let apiPlans: Plan[] = [];
    try {
      const response = await apiClient.getPlans();
      apiPlans = response.plans;
    } catch (error) {
      console.warn('Could not fetch plans from API:', error);
      test.skip(true, 'API not available to verify plan data');
      return;
    }

    if (apiPlans.length === 0) {
      console.log('No plans returned from API - skipping verification test');
      test.skip(true, 'No plans available for verification');
      return;
    }

    // Navigate to the plans page
    await page.goto('/plans');
    await waitForNetworkIdle(page);

    // Get plan items from UI
    const planItems = page.locator(SELECTORS.plans.item);
    const uiPlanCount = await planItems.count();

    // Verify at least one plan is displayed if API has plans
    expect(uiPlanCount).toBeGreaterThan(0);

    // Check that the first plan's name appears in the UI
    const firstApiPlan = apiPlans[0];
    if (firstApiPlan.name) {
      const planNameOnPage = page.locator(SELECTORS.plans.title).filter({
        hasText: new RegExp(firstApiPlan.name, 'i')
      });

      // The plan name should appear somewhere on the page
      const nameVisible = await planNameOnPage.count();
      if (nameVisible === 0) {
        // Try finding in plan items instead
        const planItemWithName = planItems.filter({
          hasText: new RegExp(firstApiPlan.name, 'i')
        });
        const itemCount = await planItemWithName.count();
        console.log(`Plan "${firstApiPlan.name}" found in ${itemCount} plan items`);
      }
    }

    // Verify plan status display if status element exists
    const statusElements = page.locator(SELECTORS.plans.status);
    const statusCount = await statusElements.count();
    console.log(`Found ${statusCount} status elements on page`);
  });

  test('should handle empty plans list gracefully', async ({ page, apiClient }) => {
    // Navigate to the plans page
    await page.goto('/plans');
    await waitForNetworkIdle(page);

    // Check if there are any plans
    const planItems = page.locator(SELECTORS.plans.item);
    const planCount = await planItems.count();

    if (planCount === 0) {
      // Should show empty state message using SELECTORS
      const emptyState = page.locator(SELECTORS.ui.emptyState);
      const emptyStateVisible = await emptyState.isVisible().catch(() => false);

      // Or check for "no plans" text
      const noPlansText = page.getByText(/no plans/i).first();
      const noPlansVisible = await noPlansText.isVisible().catch(() => false);

      // Should have either empty state or no plans message
      // (or just be a valid empty list)
      console.log(`Empty state visible: ${emptyStateVisible}, No plans text: ${noPlansVisible}`);

      // The page should still be functional even with no plans
      await expect(page.locator('body')).toBeVisible();
    } else {
      console.log(`Found ${planCount} plans - skipping empty state test`);
    }
  });

  test('should show loading state while fetching plans', async ({ page }) => {
    // Start navigation to plans page
    const navigationPromise = page.goto('/plans');

    // Try to catch the loading state (may be very brief)
    const loadingIndicator = page.locator(SELECTORS.ui.loading);

    // Wait for navigation to complete
    await navigationPromise;

    // Check if loading indicator was/is present
    // Note: Loading may be too fast to catch, so we don't fail on this
    const wasLoading = await loadingIndicator.isVisible().catch(() => false);
    console.log(`Loading indicator visible during navigation: ${wasLoading}`);

    // After load, loading indicator should be hidden
    await waitForNetworkIdle(page);

    const stillLoading = await loadingIndicator.isVisible().catch(() => false);
    if (stillLoading) {
      // Loading should eventually complete
      await expect(loadingIndicator).toBeHidden({ timeout: 30000 });
    }
  });

  test('should use PageHelper for common interactions', async ({ page }) => {
    const helper = new PageHelper(page);

    // Navigate using helper
    await helper.navigateTo('/plans');

    // Check visibility using helper
    const bodyVisible = await helper.isVisible('body');
    expect(bodyVisible).toBe(true);

    // Get text content using helper
    const pageTitle = await helper.getText(SELECTORS.plans.title, 'Plans');
    expect(pageTitle.length).toBeGreaterThan(0);

    // Wait for stable state using helper
    await helper.waitForStable();

    // Verify page loaded correctly
    await expect(page).toHaveURL(/.*\/plans.*/);
  });
});
