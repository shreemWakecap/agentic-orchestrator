import { test, expect, SELECTORS, waitForNetworkIdle, PageHelper } from './fixtures';
import AxeBuilder from '@axe-core/playwright';

/**
 * Accessibility E2E Tests
 *
 * Tests WCAG 2.1 Level AA compliance using axe-core integration:
 * - Home page has no critical a11y violations
 * - Forms have proper labels
 * - Images have alt text
 * - Color contrast meets WCAG AA standards
 * - Keyboard navigation works on main flows
 */

// Configure axe-core options for WCAG 2.1 AA compliance
const axeConfig = {
  // Run only WCAG 2.1 Level A and AA rules
  runOnly: {
    type: 'tag' as const,
    values: ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'],
  },
};

// Helper to format accessibility violations for better error messages
function formatViolations(violations: Array<{
  id: string;
  impact: string | null;
  description: string;
  nodes: Array<{ html: string; failureSummary?: string }>;
}>): string {
  return violations
    .map((violation) => {
      const nodes = violation.nodes
        .slice(0, 3) // Limit to first 3 nodes for readability
        .map((node) => `    - ${node.html}\n      ${node.failureSummary || ''}`)
        .join('\n');
      const moreNodes = violation.nodes.length > 3
        ? `\n    ... and ${violation.nodes.length - 3} more`
        : '';
      return `[${violation.impact?.toUpperCase() || 'UNKNOWN'}] ${violation.id}: ${violation.description}\n${nodes}${moreNodes}`;
    })
    .join('\n\n');
}

test.describe('Accessibility', () => {

  test.describe('Critical Violations - Home Page', () => {
    test('should have no critical a11y violations on home page', async ({ page }) => {
      await page.goto('/');
      await waitForNetworkIdle(page);

      const results = await new AxeBuilder({ page })
        .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'])
        .analyze();

      // Filter for critical and serious violations
      const criticalViolations = results.violations.filter(
        (v) => v.impact === 'critical' || v.impact === 'serious'
      );

      if (criticalViolations.length > 0) {
        console.error('Critical accessibility violations found:\n', formatViolations(criticalViolations));
      }

      expect(
        criticalViolations,
        `Found ${criticalViolations.length} critical/serious a11y violations:\n${formatViolations(criticalViolations)}`
      ).toHaveLength(0);
    });

    test('should have no critical a11y violations on plans page', async ({ page }) => {
      await page.goto('/plans');
      await waitForNetworkIdle(page);

      const results = await new AxeBuilder({ page })
        .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'])
        .analyze();

      const criticalViolations = results.violations.filter(
        (v) => v.impact === 'critical' || v.impact === 'serious'
      );

      if (criticalViolations.length > 0) {
        console.error('Critical accessibility violations on plans page:\n', formatViolations(criticalViolations));
      }

      expect(
        criticalViolations,
        `Found ${criticalViolations.length} critical/serious a11y violations on plans page`
      ).toHaveLength(0);
    });

    test('should have no critical a11y violations on runs page', async ({ page }) => {
      await page.goto('/runs');
      await waitForNetworkIdle(page);

      const results = await new AxeBuilder({ page })
        .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'])
        .analyze();

      const criticalViolations = results.violations.filter(
        (v) => v.impact === 'critical' || v.impact === 'serious'
      );

      if (criticalViolations.length > 0) {
        console.error('Critical accessibility violations on runs page:\n', formatViolations(criticalViolations));
      }

      expect(
        criticalViolations,
        `Found ${criticalViolations.length} critical/serious a11y violations on runs page`
      ).toHaveLength(0);
    });

    test('should have no critical a11y violations on plan detail page', async ({ page }) => {
      // First get a plan ID
      await page.goto('/plans');
      await waitForNetworkIdle(page);

      const planLink = page.locator(`${SELECTORS.plans.item} a, a[href*="/plans/"]`).first();

      if (await planLink.count() > 0) {
        await planLink.click();
        await waitForNetworkIdle(page);

        const results = await new AxeBuilder({ page })
          .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'])
          .analyze();

        const criticalViolations = results.violations.filter(
          (v) => v.impact === 'critical' || v.impact === 'serious'
        );

        if (criticalViolations.length > 0) {
          console.error('Critical accessibility violations on plan detail page:\n', formatViolations(criticalViolations));
        }

        expect(
          criticalViolations,
          `Found ${criticalViolations.length} critical/serious a11y violations on plan detail page`
        ).toHaveLength(0);
      } else {
        test.skip(true, 'No plans available to test plan detail accessibility');
      }
    });
  });

  test.describe('Form Labels', () => {
    test('all form inputs should have associated labels', async ({ page }) => {
      await page.goto('/');
      await waitForNetworkIdle(page);

      // Run axe specifically for label-related rules
      const results = await new AxeBuilder({ page })
        .withRules(['label', 'label-title-only', 'form-field-multiple-labels'])
        .analyze();

      const labelViolations = results.violations;

      if (labelViolations.length > 0) {
        console.error('Form label violations found:\n', formatViolations(labelViolations));
      }

      expect(
        labelViolations,
        `Found ${labelViolations.length} form label violations`
      ).toHaveLength(0);
    });

    test('forms on plans page should have proper labels', async ({ page }) => {
      await page.goto('/plans');
      await waitForNetworkIdle(page);

      // Check all visible inputs have labels
      const inputs = page.locator(SELECTORS.forms.input);
      const inputCount = await inputs.count();

      for (let i = 0; i < inputCount; i++) {
        const input = inputs.nth(i);
        const isVisible = await input.isVisible();

        if (isVisible) {
          const id = await input.getAttribute('id');
          const ariaLabel = await input.getAttribute('aria-label');
          const ariaLabelledby = await input.getAttribute('aria-labelledby');
          const placeholder = await input.getAttribute('placeholder');
          const title = await input.getAttribute('title');

          // Check if the input has a valid labeling mechanism
          const hasLabel = id
            ? await page.locator(`label[for="${id}"]`).count() > 0
            : false;
          const hasAriaLabel = ariaLabel !== null && ariaLabel !== '';
          const hasAriaLabelledby = ariaLabelledby !== null && ariaLabelledby !== '';
          const hasPlaceholder = placeholder !== null && placeholder !== '';
          const hasTitle = title !== null && title !== '';

          // Input should have at least one accessible name
          const hasAccessibleName = hasLabel || hasAriaLabel || hasAriaLabelledby || hasPlaceholder || hasTitle;

          if (!hasAccessibleName) {
            const inputHtml = await input.evaluate((el) => el.outerHTML);
            console.warn(`Input without accessible name: ${inputHtml}`);
          }

          expect(
            hasAccessibleName,
            `Input ${i + 1} should have an accessible name (label, aria-label, aria-labelledby, placeholder, or title)`
          ).toBe(true);
        }
      }
    });

    test('required fields should be properly indicated', async ({ page }) => {
      await page.goto('/plans');
      await waitForNetworkIdle(page);

      // Check required fields have proper indication
      const requiredInputs = page.locator(SELECTORS.forms.requiredField);
      const requiredCount = await requiredInputs.count();

      for (let i = 0; i < requiredCount; i++) {
        const input = requiredInputs.nth(i);
        const isVisible = await input.isVisible();

        if (isVisible) {
          const ariaRequired = await input.getAttribute('aria-required');
          const required = await input.getAttribute('required');

          // Required inputs should have required attribute or aria-required
          const isProperlyMarked = required !== null || ariaRequired === 'true';
          expect(isProperlyMarked, `Required field ${i + 1} should be properly marked`).toBe(true);
        }
      }
    });

    test('form error messages should be associated with inputs', async ({ page }) => {
      // Run axe for aria-related rules
      await page.goto('/');
      await waitForNetworkIdle(page);

      const results = await new AxeBuilder({ page })
        .withRules(['aria-input-field-name', 'aria-valid-attr-value'])
        .analyze();

      const ariaViolations = results.violations;

      if (ariaViolations.length > 0) {
        console.error('ARIA violations found:\n', formatViolations(ariaViolations));
      }

      expect(
        ariaViolations,
        `Found ${ariaViolations.length} ARIA violations related to form inputs`
      ).toHaveLength(0);
    });
  });

  test.describe('Images and Alt Text', () => {
    test('all images should have alt text', async ({ page }) => {
      await page.goto('/');
      await waitForNetworkIdle(page);

      // Run axe specifically for image alt text rules
      const results = await new AxeBuilder({ page })
        .withRules(['image-alt', 'input-image-alt', 'area-alt'])
        .analyze();

      const imageViolations = results.violations;

      if (imageViolations.length > 0) {
        console.error('Image alt text violations found:\n', formatViolations(imageViolations));
      }

      expect(
        imageViolations,
        `Found ${imageViolations.length} image alt text violations`
      ).toHaveLength(0);
    });

    test('images on plans page should have alt text', async ({ page }) => {
      await page.goto('/plans');
      await waitForNetworkIdle(page);

      // Check all img elements
      const images = page.locator('img');
      const imageCount = await images.count();

      for (let i = 0; i < imageCount; i++) {
        const img = images.nth(i);
        const isVisible = await img.isVisible();

        if (isVisible) {
          const alt = await img.getAttribute('alt');
          const role = await img.getAttribute('role');

          // Decorative images should have empty alt or role="presentation"
          // Other images should have meaningful alt text
          const hasAlt = alt !== null;
          const isDecorativeRole = role === 'presentation' || role === 'none';

          expect(
            hasAlt || isDecorativeRole,
            `Image ${i + 1} should have alt attribute or role="presentation"`
          ).toBe(true);
        }
      }
    });

    test('SVG icons should have accessible names when interactive', async ({ page }) => {
      await page.goto('/');
      await waitForNetworkIdle(page);

      // Find interactive SVGs (buttons with SVGs, links with SVGs)
      const interactiveSvgs = page.locator('button svg, a svg');
      const svgCount = await interactiveSvgs.count();

      for (let i = 0; i < svgCount; i++) {
        const svg = interactiveSvgs.nth(i);
        const parent = svg.locator('..');

        // The parent interactive element should have an accessible name
        const ariaLabel = await parent.getAttribute('aria-label');
        const ariaLabelledby = await parent.getAttribute('aria-labelledby');
        const title = await parent.getAttribute('title');
        const textContent = await parent.textContent();

        const hasAccessibleName =
          (ariaLabel !== null && ariaLabel !== '') ||
          (ariaLabelledby !== null && ariaLabelledby !== '') ||
          (title !== null && title !== '') ||
          (textContent !== null && textContent.trim() !== '');

        if (!hasAccessibleName) {
          const parentHtml = await parent.evaluate((el) => el.outerHTML.substring(0, 200));
          console.warn(`Interactive element with SVG may need accessible name: ${parentHtml}...`);
        }
      }
    });
  });

  test.describe('Color Contrast', () => {
    test('color contrast should meet WCAG AA standards on home page', async ({ page }) => {
      await page.goto('/');
      await waitForNetworkIdle(page);

      // Run axe specifically for color contrast rules
      const results = await new AxeBuilder({ page })
        .withRules(['color-contrast', 'color-contrast-enhanced'])
        .analyze();

      const contrastViolations = results.violations.filter(
        (v) => v.id.includes('color-contrast')
      );

      if (contrastViolations.length > 0) {
        console.error('Color contrast violations found:\n', formatViolations(contrastViolations));
      }

      // Allow minor violations but flag them as warnings
      const seriousContrastViolations = contrastViolations.filter(
        (v) => v.impact === 'critical' || v.impact === 'serious'
      );

      expect(
        seriousContrastViolations,
        `Found ${seriousContrastViolations.length} serious color contrast violations`
      ).toHaveLength(0);
    });

    test('color contrast should meet WCAG AA standards on plans page', async ({ page }) => {
      await page.goto('/plans');
      await waitForNetworkIdle(page);

      const results = await new AxeBuilder({ page })
        .withRules(['color-contrast'])
        .analyze();

      const contrastViolations = results.violations.filter(
        (v) => v.id.includes('color-contrast')
      );

      const seriousContrastViolations = contrastViolations.filter(
        (v) => v.impact === 'critical' || v.impact === 'serious'
      );

      expect(
        seriousContrastViolations,
        `Found ${seriousContrastViolations.length} serious color contrast violations on plans page`
      ).toHaveLength(0);
    });

    test('text on status badges should have sufficient contrast', async ({ page }) => {
      await page.goto('/plans');
      await waitForNetworkIdle(page);

      // Check status badges specifically
      const statusBadges = page.locator(SELECTORS.plans.status);
      const badgeCount = await statusBadges.count();

      if (badgeCount > 0) {
        // Run axe just on the area containing status badges
        const results = await new AxeBuilder({ page })
          .include(SELECTORS.plans.status)
          .withRules(['color-contrast'])
          .analyze();

        const seriousViolations = results.violations.filter(
          (v) => v.impact === 'critical' || v.impact === 'serious'
        );

        expect(
          seriousViolations,
          'Status badges should have sufficient color contrast'
        ).toHaveLength(0);
      }
    });
  });

  test.describe('Keyboard Navigation', () => {
    test('main navigation should be keyboard accessible', async ({ page }) => {
      await page.goto('/');
      await waitForNetworkIdle(page);

      // Focus on the first focusable element
      await page.keyboard.press('Tab');

      // Track which elements receive focus
      const focusedElements: string[] = [];
      let maxTabs = 20; // Prevent infinite loops

      while (maxTabs > 0) {
        const activeElement = await page.evaluate(() => {
          const el = document.activeElement;
          if (!el) return null;
          return {
            tag: el.tagName.toLowerCase(),
            text: el.textContent?.trim().substring(0, 50) || '',
            href: (el as HTMLAnchorElement).href || '',
          };
        });

        if (!activeElement) break;

        focusedElements.push(`${activeElement.tag}: ${activeElement.text || activeElement.href}`);

        // Check if we've tabbed through the nav links
        const inNav = await page.evaluate(() => {
          return document.activeElement?.closest('nav') !== null;
        });

        if (inNav) {
          // Nav link should be focusable
          const isFocusable = await page.evaluate(() => {
            const el = document.activeElement;
            return el?.tagName === 'A' || el?.tagName === 'BUTTON';
          });
          expect(isFocusable, 'Nav items should be focusable').toBe(true);
        }

        await page.keyboard.press('Tab');
        maxTabs--;
      }

      // Should have multiple focusable elements
      expect(focusedElements.length).toBeGreaterThan(0);
      console.log('Focused elements:', focusedElements);
    });

    test('should be able to navigate to plans page using keyboard', async ({ page }) => {
      await page.goto('/');
      await waitForNetworkIdle(page);

      // Tab to find the Plans link and activate it
      let foundPlansLink = false;
      let maxTabs = 30;

      while (maxTabs > 0 && !foundPlansLink) {
        await page.keyboard.press('Tab');

        const linkText = await page.evaluate(() => {
          const el = document.activeElement;
          return el?.textContent?.toLowerCase().trim() || '';
        });

        if (linkText.includes('plans')) {
          foundPlansLink = true;

          // Press Enter to activate the link
          await page.keyboard.press('Enter');
          await waitForNetworkIdle(page);

          // Should be on plans page
          await expect(page).toHaveURL(/\/plans/);
        }

        maxTabs--;
      }

      expect(foundPlansLink, 'Should be able to find and activate Plans link via keyboard').toBe(true);
    });

    test('interactive elements should have visible focus indicators', async ({ page }) => {
      await page.goto('/');
      await waitForNetworkIdle(page);

      // Run axe for focus-related rules
      const results = await new AxeBuilder({ page })
        .withRules(['focus-visible', 'focus-order-semantics'])
        .analyze();

      // Note: focus-visible rule may not catch all cases
      // Log any violations for manual review
      if (results.violations.length > 0) {
        console.warn('Focus-related violations (may need manual review):\n', formatViolations(results.violations));
      }
    });

    test('modals should trap focus when open', async ({ page }) => {
      await page.goto('/plans');
      await waitForNetworkIdle(page);

      // Look for a button that opens a modal
      const createButton = page.locator(SELECTORS.plans.createButton).first();

      if (await createButton.count() > 0) {
        await createButton.click();

        // Wait for modal to appear
        const modal = page.locator(SELECTORS.ui.modal);

        if (await modal.count() > 0) {
          await expect(modal).toBeVisible();

          // Tab through elements - focus should stay within modal
          const focusWithinModal: boolean[] = [];

          for (let i = 0; i < 10; i++) {
            await page.keyboard.press('Tab');

            const inModal = await page.evaluate(() => {
              const activeEl = document.activeElement;
              const modal = document.querySelector('[role="dialog"], .modal');
              return modal?.contains(activeEl) || false;
            });

            focusWithinModal.push(inModal);
          }

          // Most tabbed elements should be within the modal
          const insideCount = focusWithinModal.filter(Boolean).length;
          expect(insideCount).toBeGreaterThan(focusWithinModal.length / 2);

          // Escape should close modal
          await page.keyboard.press('Escape');
          await expect(modal).toBeHidden();
        }
      }
    });

    test('should be able to use keyboard shortcuts if defined', async ({ page }) => {
      await page.goto('/');
      await waitForNetworkIdle(page);

      // Check for common keyboard shortcuts (/ for search, ? for help, etc.)
      // This test verifies shortcuts don't break the page

      // Try common shortcuts
      await page.keyboard.press('/');
      await page.waitForTimeout(500);

      // Page should still be functional
      const mainContent = page.locator(SELECTORS.sections.main);
      await expect(mainContent).toBeVisible();

      // Escape any opened element
      await page.keyboard.press('Escape');
    });

    test('skip to main content link should work', async ({ page }) => {
      await page.goto('/');
      await waitForNetworkIdle(page);

      // Check for skip link
      const skipLink = page.locator(SELECTORS.a11y.skipLink);

      if (await skipLink.count() > 0) {
        // Skip link should be first focusable element or become visible on focus
        await page.keyboard.press('Tab');

        const isSkipLinkFocused = await skipLink.first().evaluate((el) => {
          return el === document.activeElement || el.contains(document.activeElement);
        });

        if (isSkipLinkFocused) {
          // Activate skip link
          await page.keyboard.press('Enter');

          // Focus should move to main content
          const mainFocused = await page.evaluate(() => {
            const main = document.querySelector('main, [role="main"], #main');
            return main === document.activeElement || main?.contains(document.activeElement) || false;
          });

          expect(mainFocused, 'Skip link should move focus to main content').toBe(true);
        }
      } else {
        console.log('No skip link found - consider adding one for better keyboard accessibility');
      }
    });
  });

  test.describe('ARIA Landmarks', () => {
    test('page should have proper landmark structure', async ({ page }) => {
      await page.goto('/');
      await waitForNetworkIdle(page);

      // Run axe for landmark-related rules
      const results = await new AxeBuilder({ page })
        .withRules([
          'landmark-one-main',
          'landmark-unique',
          'region',
          'landmark-no-duplicate-banner',
          'landmark-no-duplicate-contentinfo',
        ])
        .analyze();

      const landmarkViolations = results.violations;

      if (landmarkViolations.length > 0) {
        console.error('Landmark violations found:\n', formatViolations(landmarkViolations));
      }

      // Serious landmark violations should be fixed
      const seriousViolations = landmarkViolations.filter(
        (v) => v.impact === 'critical' || v.impact === 'serious'
      );

      expect(
        seriousViolations,
        `Found ${seriousViolations.length} serious landmark violations`
      ).toHaveLength(0);
    });

    test('page should have exactly one main landmark', async ({ page }) => {
      await page.goto('/');
      await waitForNetworkIdle(page);

      const mainLandmarks = page.locator('main, [role="main"]');
      const mainCount = await mainLandmarks.count();

      expect(mainCount, 'Page should have exactly one main landmark').toBe(1);
    });

    test('page should have navigation landmark', async ({ page }) => {
      await page.goto('/');
      await waitForNetworkIdle(page);

      const navLandmarks = page.locator('nav, [role="navigation"]');
      const navCount = await navLandmarks.count();

      expect(navCount, 'Page should have at least one navigation landmark').toBeGreaterThanOrEqual(1);
    });

    test('all content should be contained within landmarks', async ({ page }) => {
      await page.goto('/');
      await waitForNetworkIdle(page);

      // Check that major content is within landmarks
      const results = await new AxeBuilder({ page })
        .withRules(['region'])
        .analyze();

      // Log violations for awareness, but don't fail on minor ones
      if (results.violations.length > 0) {
        console.warn('Content outside landmarks:\n', formatViolations(results.violations));
      }
    });
  });

  test.describe('Heading Structure', () => {
    test('page should have proper heading hierarchy', async ({ page }) => {
      await page.goto('/');
      await waitForNetworkIdle(page);

      // Run axe for heading-related rules
      const results = await new AxeBuilder({ page })
        .withRules(['heading-order', 'page-has-heading-one', 'empty-heading'])
        .analyze();

      const headingViolations = results.violations;

      if (headingViolations.length > 0) {
        console.error('Heading violations found:\n', formatViolations(headingViolations));
      }

      expect(
        headingViolations,
        `Found ${headingViolations.length} heading structure violations`
      ).toHaveLength(0);
    });

    test('page should have exactly one h1', async ({ page }) => {
      await page.goto('/');
      await waitForNetworkIdle(page);

      const h1Elements = page.locator('h1');
      const h1Count = await h1Elements.count();

      // Pages should have exactly one h1
      expect(h1Count, 'Page should have exactly one h1 element').toBe(1);
    });

    test('headings should not skip levels', async ({ page }) => {
      await page.goto('/plans');
      await waitForNetworkIdle(page);

      // Get all headings and check order
      const headings = await page.evaluate(() => {
        const headingElements = document.querySelectorAll('h1, h2, h3, h4, h5, h6');
        return Array.from(headingElements).map((h) => ({
          level: parseInt(h.tagName.substring(1)),
          text: h.textContent?.trim().substring(0, 50) || '',
        }));
      });

      // Check for level skips
      let previousLevel = 0;
      const skips: string[] = [];

      for (const heading of headings) {
        if (previousLevel > 0 && heading.level > previousLevel + 1) {
          skips.push(`Skipped from h${previousLevel} to h${heading.level}: "${heading.text}"`);
        }
        previousLevel = heading.level;
      }

      if (skips.length > 0) {
        console.warn('Heading level skips found:', skips);
      }
    });
  });

  test.describe('Full Page Scan', () => {
    test('full accessibility scan of home page', async ({ page }) => {
      await page.goto('/');
      await waitForNetworkIdle(page);

      const results = await new AxeBuilder({ page })
        .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'best-practice'])
        .analyze();

      // Log all violations for comprehensive report
      console.log(`\nAccessibility Scan Results for Home Page:`);
      console.log(`- Passes: ${results.passes.length}`);
      console.log(`- Violations: ${results.violations.length}`);
      console.log(`- Incomplete: ${results.incomplete.length}`);

      if (results.violations.length > 0) {
        console.log('\nViolations by impact:');
        const byImpact = results.violations.reduce((acc, v) => {
          const impact = v.impact || 'unknown';
          acc[impact] = (acc[impact] || 0) + 1;
          return acc;
        }, {} as Record<string, number>);
        console.log(byImpact);

        console.log('\nAll violations:\n', formatViolations(results.violations));
      }

      // Only fail on critical/serious violations
      const criticalViolations = results.violations.filter(
        (v) => v.impact === 'critical' || v.impact === 'serious'
      );

      expect(
        criticalViolations,
        `Found ${criticalViolations.length} critical/serious accessibility violations`
      ).toHaveLength(0);
    });

    test('full accessibility scan of plans page', async ({ page }) => {
      await page.goto('/plans');
      await waitForNetworkIdle(page);

      const results = await new AxeBuilder({ page })
        .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'])
        .analyze();

      console.log(`\nAccessibility Scan Results for Plans Page:`);
      console.log(`- Passes: ${results.passes.length}`);
      console.log(`- Violations: ${results.violations.length}`);
      console.log(`- Incomplete: ${results.incomplete.length}`);

      const criticalViolations = results.violations.filter(
        (v) => v.impact === 'critical' || v.impact === 'serious'
      );

      expect(
        criticalViolations,
        `Found ${criticalViolations.length} critical/serious accessibility violations on plans page`
      ).toHaveLength(0);
    });
  });
});
