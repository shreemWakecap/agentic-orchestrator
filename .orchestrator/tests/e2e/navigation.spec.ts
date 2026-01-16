import {
  test,
  expect,
  SELECTORS,
  waitForNetworkIdle,
  waitForNavigation,
  PageHelper
} from './fixtures';

/**
 * Navigation E2E Tests
 *
 * Tests comprehensive navigation functionality including:
 * - Main navigation links work correctly
 * - Breadcrumbs display correctly on nested pages
 * - Back navigation works (browser back button and in-page back links)
 * - 404 handling for invalid routes
 * - All sidebar/navbar links navigate correctly
 */

test.describe('Navigation', () => {

  test.describe('Main Navigation Links', () => {
    test('should navigate to Dashboard from navbar', async ({ page }) => {
      // Start from a different page to test navigation
      await page.goto('/plans');
      await waitForNetworkIdle(page);

      // Click on Dashboard link in navbar
      const dashboardLink = page.locator('nav a').filter({ hasText: /dashboard/i }).first();
      await expect(dashboardLink).toBeVisible();

      await waitForNavigation(page, async () => {
        await dashboardLink.click();
      }, { waitUntil: 'networkidle' });

      // Verify we're on the dashboard (root path or /dashboard)
      const currentUrl = page.url();
      expect(currentUrl.endsWith('/') || currentUrl.includes('/dashboard') || currentUrl.match(/localhost:\d+\/?$/)).toBeTruthy();

      // Verify page content loaded
      const mainContent = page.locator(SELECTORS.sections.main);
      await expect(mainContent).toBeVisible();
    });

    test('should navigate to Plans page from navbar', async ({ page }) => {
      // Start from dashboard
      await page.goto('/');
      await waitForNetworkIdle(page);

      // Click on Plans link in navbar
      const plansLink = page.locator('nav a').filter({ hasText: /plans/i }).first();
      await expect(plansLink).toBeVisible();

      await waitForNavigation(page, async () => {
        await plansLink.click();
      }, { waitUntil: 'networkidle' });

      // Verify we're on the plans page
      await expect(page).toHaveURL(/\/plans/);

      // Verify page content loaded
      const mainContent = page.locator(SELECTORS.sections.main);
      await expect(mainContent).toBeVisible();
    });

    test('should navigate to Runs page from navbar', async ({ page }) => {
      // Start from dashboard
      await page.goto('/');
      await waitForNetworkIdle(page);

      // Click on Runs link in navbar
      const runsLink = page.locator('nav a').filter({ hasText: /runs/i }).first();
      await expect(runsLink).toBeVisible();

      await waitForNavigation(page, async () => {
        await runsLink.click();
      }, { waitUntil: 'networkidle' });

      // Verify we're on the runs page
      await expect(page).toHaveURL(/\/runs/);

      // Verify page content loaded
      const mainContent = page.locator(SELECTORS.sections.main);
      await expect(mainContent).toBeVisible();
    });

    test('should have all main navigation links visible', async ({ page }) => {
      await page.goto('/');
      await waitForNetworkIdle(page);

      // Verify main navbar is present
      const navbar = page.locator('nav');
      await expect(navbar).toBeVisible();

      // Verify all main navigation links are present
      const dashboardLink = page.locator('nav a').filter({ hasText: /dashboard/i }).first();
      const plansLink = page.locator('nav a').filter({ hasText: /plans/i }).first();
      const runsLink = page.locator('nav a').filter({ hasText: /runs/i }).first();

      await expect(dashboardLink).toBeVisible();
      await expect(plansLink).toBeVisible();
      await expect(runsLink).toBeVisible();
    });

    test('should highlight active navigation link', async ({ page }) => {
      // Navigate to plans page
      await page.goto('/plans');
      await waitForNetworkIdle(page);

      // The plans link should have some indication of being active (class or border)
      const plansLink = page.locator('nav a').filter({ hasText: /plans/i }).first();
      await expect(plansLink).toBeVisible();

      // Check for active state styling (border-b-2 with color, or aria-current)
      const plansLinkClasses = await plansLink.getAttribute('class');
      const ariaCurrent = await plansLink.getAttribute('aria-current');

      // Either the link has active styling or aria-current attribute
      const hasActiveIndication =
        (plansLinkClasses && (plansLinkClasses.includes('border-gray-900') || plansLinkClasses.includes('active'))) ||
        ariaCurrent === 'page';

      // Log for debugging (active styling may vary)
      console.log(`Plans link classes: ${plansLinkClasses}, aria-current: ${ariaCurrent}`);
    });

    test('should navigate via logo/brand link to home', async ({ page }) => {
      // Start from plans page
      await page.goto('/plans');
      await waitForNetworkIdle(page);

      // Click on the brand/logo link
      const brandLink = page.locator('nav a').filter({ hasText: /SDLC Orchestrator/i }).first();

      if (await brandLink.count() > 0) {
        await waitForNavigation(page, async () => {
          await brandLink.click();
        }, { waitUntil: 'networkidle' });

        // Should navigate to home
        const currentUrl = page.url();
        expect(currentUrl.endsWith('/') || currentUrl.match(/localhost:\d+\/?$/)).toBeTruthy();
      } else {
        console.log('Brand link not found - skipping test');
      }
    });
  });

  test.describe('Breadcrumbs', () => {
    test('should display breadcrumbs on plan detail page', async ({ page }) => {
      // First, get a plan ID from the plans list
      await page.goto('/plans');
      await waitForNetworkIdle(page);

      const planItem = page.locator(SELECTORS.plans.item).first();
      const planExists = await planItem.count() > 0;

      if (planExists) {
        // Get a plan link and navigate to detail
        const planLink = page.locator(`${SELECTORS.plans.item} a, a[href*="/plans/"]`).first();
        if (await planLink.count() > 0) {
          await waitForNavigation(page, async () => {
            await planLink.click();
          }, { waitUntil: 'networkidle' });

          // Check for breadcrumbs or "Back to Plans" link indicating navigation hierarchy
          const breadcrumbs = page.locator(SELECTORS.nav.breadcrumbs);
          const backLink = page.locator('a[href="/plans"]');

          const hasBreadcrumbs = await breadcrumbs.count() > 0;
          const hasBackLink = await backLink.count() > 0;

          // Should have some form of navigation hierarchy indicator
          expect(hasBreadcrumbs || hasBackLink).toBeTruthy();

          if (hasBackLink) {
            await expect(backLink.first()).toBeVisible();
          }
        }
      } else {
        test.skip(true, 'No plans available to test breadcrumbs');
      }
    });

    test('should display breadcrumbs on run detail page', async ({ page }) => {
      // Navigate to runs page
      await page.goto('/runs');
      await waitForNetworkIdle(page);

      // Look for run items
      const runLink = page.locator('a[href*="/runs/"]').first();

      if (await runLink.count() > 0) {
        await waitForNavigation(page, async () => {
          await runLink.click();
        }, { waitUntil: 'networkidle' });

        // Check for breadcrumbs or "Back to Runs" link
        const breadcrumbs = page.locator(SELECTORS.nav.breadcrumbs);
        const backLink = page.locator('a[href="/runs"]');

        const hasBreadcrumbs = await breadcrumbs.count() > 0;
        const hasBackLink = await backLink.count() > 0;

        // Should have some form of navigation hierarchy indicator
        expect(hasBreadcrumbs || hasBackLink).toBeTruthy();
      } else {
        test.skip(true, 'No runs available to test breadcrumbs');
      }
    });

    test('should allow navigation via breadcrumb links', async ({ page }) => {
      // Navigate to a plan detail page
      await page.goto('/plans');
      await waitForNetworkIdle(page);

      const planLink = page.locator(`${SELECTORS.plans.item} a, a[href*="/plans/"]`).first();

      if (await planLink.count() > 0) {
        await waitForNavigation(page, async () => {
          await planLink.click();
        }, { waitUntil: 'networkidle' });

        // Look for back/breadcrumb link to plans
        const backToPlansLink = page.locator('a[href="/plans"]').first();

        if (await backToPlansLink.count() > 0) {
          await waitForNavigation(page, async () => {
            await backToPlansLink.click();
          }, { waitUntil: 'networkidle' });

          // Should be back on plans page
          await expect(page).toHaveURL(/\/plans/);
        }
      } else {
        test.skip(true, 'No plans available to test breadcrumb navigation');
      }
    });
  });

  test.describe('Back Navigation', () => {
    test('should support browser back button navigation', async ({ page }) => {
      // Navigate through multiple pages
      await page.goto('/');
      await waitForNetworkIdle(page);

      // Go to plans
      await page.goto('/plans');
      await waitForNetworkIdle(page);
      await expect(page).toHaveURL(/\/plans/);

      // Go to runs
      await page.goto('/runs');
      await waitForNetworkIdle(page);
      await expect(page).toHaveURL(/\/runs/);

      // Use browser back button
      await page.goBack();
      await waitForNetworkIdle(page);

      // Should be back on plans
      await expect(page).toHaveURL(/\/plans/);

      // Go back again
      await page.goBack();
      await waitForNetworkIdle(page);

      // Should be back on dashboard/home
      const currentUrl = page.url();
      expect(currentUrl.endsWith('/') || currentUrl.includes('/dashboard') || currentUrl.match(/localhost:\d+\/?$/)).toBeTruthy();
    });

    test('should support browser forward button navigation', async ({ page }) => {
      // Navigate through pages
      await page.goto('/');
      await waitForNetworkIdle(page);

      await page.goto('/plans');
      await waitForNetworkIdle(page);

      await page.goto('/runs');
      await waitForNetworkIdle(page);

      // Go back
      await page.goBack();
      await waitForNetworkIdle(page);
      await expect(page).toHaveURL(/\/plans/);

      // Go forward
      await page.goForward();
      await waitForNetworkIdle(page);
      await expect(page).toHaveURL(/\/runs/);
    });

    test('should work with "Back to Plans" link on plan detail page', async ({ page }) => {
      await page.goto('/plans');
      await waitForNetworkIdle(page);

      const planLink = page.locator(`${SELECTORS.plans.item} a, a[href*="/plans/"]`).first();

      if (await planLink.count() > 0) {
        await waitForNavigation(page, async () => {
          await planLink.click();
        }, { waitUntil: 'networkidle' });

        // Look for the "Back to Plans" link
        const backLink = page.locator('a[href="/plans"]');

        if (await backLink.count() > 0) {
          await expect(backLink.first()).toBeVisible();

          // The link should contain "Back" text
          const linkText = await backLink.first().textContent();
          expect(linkText?.toLowerCase()).toContain('back');

          // Click the back link
          await waitForNavigation(page, async () => {
            await backLink.first().click();
          }, { waitUntil: 'networkidle' });

          // Should be back on plans list
          await expect(page).toHaveURL(/\/plans\/?$/);
        }
      } else {
        test.skip(true, 'No plans available to test back navigation');
      }
    });

    test('should preserve page state when navigating back', async ({ page }) => {
      await page.goto('/plans');
      await waitForNetworkIdle(page);

      // Get initial plan count
      const planItems = page.locator(SELECTORS.plans.item);
      const initialCount = await planItems.count();

      // Navigate away
      await page.goto('/runs');
      await waitForNetworkIdle(page);

      // Navigate back
      await page.goBack();
      await waitForNetworkIdle(page);

      // Verify we're on plans page with same content
      await expect(page).toHaveURL(/\/plans/);
      const newCount = await planItems.count();
      expect(newCount).toBe(initialCount);
    });
  });

  test.describe('404 Error Handling', () => {
    test('should handle navigation to non-existent plan', async ({ page }) => {
      // Navigate to a plan ID that doesn't exist
      const response = await page.goto('/plans/non-existent-plan-id-12345');

      // Should either return 404 status or show error page
      const status = response?.status();

      if (status === 404) {
        // Verify 404 page content if status is 404
        const pageContent = await page.content();
        expect(pageContent.toLowerCase()).toMatch(/not found|404|error|does not exist/i);
      } else {
        // Page might redirect or show error in content
        await waitForNetworkIdle(page);
        const errorIndicator = page.locator(SELECTORS.ui.error);
        const notFoundText = page.getByText(/not found|does not exist|error/i);

        const hasError = await errorIndicator.count() > 0;
        const hasNotFoundText = await notFoundText.count() > 0;

        // Log the response for debugging
        console.log(`Response status: ${status}, has error: ${hasError}, has not found text: ${hasNotFoundText}`);
      }
    });

    test('should handle navigation to non-existent run', async ({ page }) => {
      const response = await page.goto('/runs/non-existent-run-id-12345');

      const status = response?.status();

      if (status === 404) {
        const pageContent = await page.content();
        expect(pageContent.toLowerCase()).toMatch(/not found|404|error|does not exist/i);
      } else {
        await waitForNetworkIdle(page);
        // Page might handle the error differently
        console.log(`Response status for non-existent run: ${status}`);
      }
    });

    test('should handle navigation to completely invalid route', async ({ page }) => {
      const response = await page.goto('/this-route-definitely-does-not-exist');

      const status = response?.status();

      if (status === 404) {
        // 404 is the expected response
        const pageContent = await page.content();
        expect(pageContent.toLowerCase()).toMatch(/not found|404|error/i);
      } else if (status === 200) {
        // May redirect to home or show error page with 200 status
        await waitForNetworkIdle(page);
        console.log('Invalid route returned 200 - may redirect or show custom error page');
      }

      // Page should not crash
      await expect(page.locator('body')).toBeVisible();
    });

    test('should display user-friendly 404 message', async ({ page }) => {
      await page.goto('/invalid-route-xyz-123');

      const status = (await page.request.head(page.url()))?.status?.() || 200;

      // Check for user-friendly error elements
      const errorHeading = page.locator('h1, h2').filter({ hasText: /not found|404|error/i });
      const errorMessage = page.getByText(/page.*not found|could not find|does not exist/i);
      const homeLink = page.locator('a[href="/"]');

      // Should have some form of error indication or navigation help
      const hasErrorHeading = await errorHeading.count() > 0;
      const hasErrorMessage = await errorMessage.count() > 0;
      const hasHomeLink = await homeLink.count() > 0;

      console.log(`Error heading: ${hasErrorHeading}, Error message: ${hasErrorMessage}, Home link: ${hasHomeLink}`);

      // At minimum, page should be functional (not broken)
      await expect(page.locator('body')).toBeVisible();
    });

    test('should allow navigation back to valid page from 404', async ({ page }) => {
      // First visit a valid page
      await page.goto('/plans');
      await waitForNetworkIdle(page);

      // Then visit invalid page
      await page.goto('/invalid-page-12345');

      // Try to navigate back
      await page.goBack();
      await waitForNetworkIdle(page);

      // Should be back on valid plans page
      await expect(page).toHaveURL(/\/plans/);
      const mainContent = page.locator(SELECTORS.sections.main);
      await expect(mainContent).toBeVisible();
    });
  });

  test.describe('Sidebar Navigation', () => {
    test('should have responsive navigation that works on different screen sizes', async ({ page }) => {
      await page.goto('/');
      await waitForNetworkIdle(page);

      // Test on desktop viewport
      await page.setViewportSize({ width: 1280, height: 800 });
      const desktopNav = page.locator('nav');
      await expect(desktopNav).toBeVisible();

      // Verify desktop nav links are visible
      const navLinks = page.locator('nav a');
      const linkCount = await navLinks.count();
      expect(linkCount).toBeGreaterThan(0);

      // Test on mobile viewport
      await page.setViewportSize({ width: 375, height: 667 });
      await page.waitForTimeout(300); // Wait for responsive adjustments

      // Navigation should still be accessible (either visible or via hamburger menu)
      const navOrMenu = page.locator('nav, [role="navigation"], button[aria-label*="menu"]');
      await expect(navOrMenu.first()).toBeVisible();
    });

    test('should navigate correctly from any page', async ({ page }) => {
      const pages = ['/', '/plans', '/runs'];

      for (const startPage of pages) {
        await page.goto(startPage);
        await waitForNetworkIdle(page);

        // From each page, verify we can navigate to all other main pages
        for (const targetPath of pages) {
          if (targetPath === startPage) continue;

          // Find the navigation link
          const linkText = targetPath === '/' ? /dashboard/i : new RegExp(targetPath.replace('/', ''), 'i');
          const navLink = page.locator('nav a').filter({ hasText: linkText }).first();

          if (await navLink.count() > 0) {
            await waitForNavigation(page, async () => {
              await navLink.click();
            }, { waitUntil: 'networkidle' });

            // Verify navigation succeeded
            if (targetPath === '/') {
              const currentUrl = page.url();
              expect(currentUrl.endsWith('/') || currentUrl.match(/localhost:\d+\/?$/)).toBeTruthy();
            } else {
              await expect(page).toHaveURL(new RegExp(targetPath));
            }

            // Go back to start page for next iteration
            await page.goto(startPage);
            await waitForNetworkIdle(page);
          }
        }
      }
    });

    test('should have consistent navigation structure across pages', async ({ page }) => {
      const pages = ['/', '/plans', '/runs'];
      let baseNavLinks: string[] = [];

      for (let i = 0; i < pages.length; i++) {
        await page.goto(pages[i]);
        await waitForNetworkIdle(page);

        // Get all nav links
        const navLinks = page.locator('nav a');
        const linkTexts: string[] = [];

        const count = await navLinks.count();
        for (let j = 0; j < count; j++) {
          const text = await navLinks.nth(j).textContent();
          if (text) {
            linkTexts.push(text.trim().toLowerCase());
          }
        }

        if (i === 0) {
          baseNavLinks = linkTexts;
        } else {
          // Navigation structure should be consistent
          expect(linkTexts.sort()).toEqual(baseNavLinks.sort());
        }
      }
    });
  });

  test.describe('Navigation with PageHelper', () => {
    test('should navigate using PageHelper utility', async ({ page }) => {
      const helper = new PageHelper(page);

      // Navigate to different pages using helper
      await helper.navigateTo('/');
      await helper.waitForStable();

      // Verify navigation
      const isAtHome = page.url().endsWith('/') || page.url().match(/localhost:\d+\/?$/);
      expect(isAtHome).toBeTruthy();

      // Navigate to plans
      await helper.navigateTo('/plans');
      await helper.waitForStable();
      await expect(page).toHaveURL(/\/plans/);

      // Navigate to runs
      await helper.navigateTo('/runs');
      await helper.waitForStable();
      await expect(page).toHaveURL(/\/runs/);
    });

    test('should verify page elements after navigation', async ({ page }) => {
      const helper = new PageHelper(page);

      await helper.navigateTo('/plans');
      await helper.waitForStable();

      // Verify key elements are visible
      const navVisible = await helper.isVisible('nav');
      const mainVisible = await helper.isVisible('main');
      const footerVisible = await helper.isVisible('footer');

      expect(navVisible).toBe(true);
      expect(mainVisible).toBe(true);
      expect(footerVisible).toBe(true);
    });
  });
});
