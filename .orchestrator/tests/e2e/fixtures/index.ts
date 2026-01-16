/**
 * E2E Test Fixtures Index
 *
 * Central export point for all test fixtures, utilities, and helpers.
 * This file provides a unified import interface for E2E tests.
 *
 * Usage:
 *   import { test, expect, APIClient, PageHelper } from './fixtures';
 *   import { mockApiError, OrchestratorMocks, SELECTORS } from './fixtures';
 *   import { waitForElement, waitForNetworkIdle } from './fixtures';
 */

// =============================================================================
// Core Test Fixtures (from test-fixtures.ts)
// =============================================================================

// Test runner and assertions
export { test, expect } from './test-fixtures';

// API Client for backend interactions
export { APIClient } from './test-fixtures';

// Page helper for common page interactions
export { PageHelper } from './test-fixtures';

// Wait utilities
export { waitFor, generateTestId, skipIf } from './test-fixtures';

// Type definitions for API responses and test data
export type {
  Plan,
  PlanFile,
  Run,
  RunEvent,
  CostEstimate,
  CostSummary,
  CostReport,
  BudgetStatus,
  TestData,
  TestFixtures
} from './test-fixtures';

// =============================================================================
// Error Mocking Utilities (from mock-errors.ts)
// =============================================================================

// Core mocking functions
export {
  mockApiError,
  mockNetworkFailure,
  mockTimeout,
  mockMultipleErrors,
  restoreAllMocks,
  waitForInterception
} from './mock-errors';

// Preset error configurations
export { ErrorPresets } from './mock-errors';

// Orchestrator-specific mock helpers
export { OrchestratorMocks } from './mock-errors';

// Type definitions for mock options
export type {
  MockApiErrorOptions,
  MockNetworkFailureOptions,
  MockTimeoutOptions,
  MockContext
} from './mock-errors';

// =============================================================================
// Common Selectors
// =============================================================================

/**
 * Common CSS selectors used across E2E tests.
 * Centralizing selectors makes tests more maintainable.
 */
export const SELECTORS = {
  // Navigation
  nav: {
    main: 'nav, [role="navigation"]',
    links: 'nav a, [role="navigation"] a',
    breadcrumbs: '.breadcrumbs, [aria-label="Breadcrumb"], nav[aria-label*="breadcrumb"]',
    activeLink: 'nav a[aria-current="page"], nav a.active',
  },

  // Plans
  plans: {
    list: '[data-testid="plans-list"], .plans-list, #plans-list',
    item: '[data-testid="plan-item"], .plan-item, .plan-card',
    title: '[data-testid="plan-title"], .plan-title, h1, h2',
    status: '[data-testid="plan-status"], .plan-status, .status-badge',
    content: '[data-testid="plan-content"], .plan-content, pre, code',
    createButton: '[data-testid="create-plan"], button:has-text("Create"), button:has-text("New")',
    deleteButton: '[data-testid="delete-plan"], button:has-text("Delete")',
  },

  // Build/Workflows
  build: {
    startButton: '[data-testid="start-build"], button:has-text("Build"), button:has-text("Start")',
    stopButton: '[data-testid="stop-build"], button:has-text("Stop"), button:has-text("Cancel")',
    progress: '[data-testid="build-progress"], .progress-bar, progress, [role="progressbar"]',
    status: '[data-testid="build-status"], .build-status',
    output: '[data-testid="build-output"], .build-output, .console-output, pre.output',
    logs: '[data-testid="build-logs"], .build-logs, .log-container',
  },

  // Cost Tracking
  cost: {
    estimate: '[data-testid="cost-estimate"], .cost-estimate',
    total: '[data-testid="cost-total"], .cost-total',
    breakdown: '[data-testid="cost-breakdown"], .cost-breakdown',
    budget: '[data-testid="budget-status"], .budget-status',
    warning: '[data-testid="budget-warning"], .budget-warning, .cost-warning',
  },

  // Experts
  experts: {
    list: '[data-testid="experts-list"], .experts-list',
    item: '[data-testid="expert-item"], .expert-item, .expert-card',
    name: '[data-testid="expert-name"], .expert-name',
    status: '[data-testid="expert-status"], .expert-status',
    createButton: '[data-testid="create-expert"], button:has-text("Add Expert")',
  },

  // Forms
  forms: {
    input: 'input:not([type="hidden"]), textarea',
    textInput: 'input[type="text"], input:not([type]), textarea',
    submitButton: 'button[type="submit"], input[type="submit"], button:has-text("Submit")',
    cancelButton: 'button:has-text("Cancel"), button[type="button"]:has-text("Cancel")',
    errorMessage: '.error-message, .field-error, [role="alert"], .invalid-feedback',
    requiredField: '[required], [aria-required="true"]',
  },

  // Common UI elements
  ui: {
    modal: '[role="dialog"], .modal, .dialog',
    modalClose: '[aria-label="Close"], .modal-close, button:has-text("Close")',
    toast: '[role="alert"], .toast, .notification',
    loading: '.loading, .spinner, [aria-busy="true"], [data-loading="true"]',
    error: '.error, [role="alert"][aria-live="assertive"], .error-banner',
    success: '.success, .success-message, [role="status"]',
    emptyState: '.empty-state, .no-data, .no-results',
    pagination: '.pagination, [aria-label="Pagination"]',
    table: 'table, [role="table"], [role="grid"]',
    tableRow: 'tr, [role="row"]',
  },

  // Page sections
  sections: {
    header: 'header, [role="banner"]',
    main: 'main, [role="main"]',
    footer: 'footer, [role="contentinfo"]',
    sidebar: 'aside, [role="complementary"], .sidebar',
  },

  // Accessibility
  a11y: {
    skipLink: '[href="#main"], .skip-link, .skip-to-content',
    landmark: '[role="main"], [role="navigation"], [role="banner"], [role="contentinfo"]',
    heading: 'h1, h2, h3, h4, h5, h6, [role="heading"]',
  },
} as const;

// =============================================================================
// Additional Wait Helpers
// =============================================================================

import { Page, Locator } from '@playwright/test';

/**
 * Wait for an element to be visible on the page.
 * @param page - Playwright Page object
 * @param selector - CSS selector to wait for
 * @param options - Wait options
 */
export async function waitForElement(
  page: Page,
  selector: string,
  options: { timeout?: number; state?: 'visible' | 'attached' | 'hidden' } = {}
): Promise<Locator> {
  const { timeout = 10000, state = 'visible' } = options;
  const locator = page.locator(selector).first();
  await locator.waitFor({ state, timeout });
  return locator;
}

/**
 * Wait for the page to have no pending network requests.
 * @param page - Playwright Page object
 * @param options - Wait options
 */
export async function waitForNetworkIdle(
  page: Page,
  options: { timeout?: number } = {}
): Promise<void> {
  const { timeout = 30000 } = options;
  await page.waitForLoadState('networkidle', { timeout });
}

/**
 * Wait for a specific text to appear on the page.
 * @param page - Playwright Page object
 * @param text - Text to wait for
 * @param options - Wait options
 */
export async function waitForText(
  page: Page,
  text: string,
  options: { timeout?: number; exact?: boolean } = {}
): Promise<Locator> {
  const { timeout = 10000, exact = false } = options;
  const locator = exact
    ? page.getByText(text, { exact: true })
    : page.getByText(text);
  await locator.first().waitFor({ state: 'visible', timeout });
  return locator.first();
}

/**
 * Wait for navigation to complete after clicking a link.
 * @param page - Playwright Page object
 * @param clickAction - Function that triggers navigation
 * @param options - Wait options
 */
export async function waitForNavigation(
  page: Page,
  clickAction: () => Promise<void>,
  options: { timeout?: number; waitUntil?: 'load' | 'domcontentloaded' | 'networkidle' } = {}
): Promise<void> {
  const { timeout = 30000, waitUntil = 'load' } = options;
  await Promise.all([
    page.waitForLoadState(waitUntil, { timeout }),
    clickAction(),
  ]);
}

/**
 * Wait for an API response matching a URL pattern.
 * @param page - Playwright Page object
 * @param urlPattern - URL pattern to match (string or RegExp)
 * @param options - Wait options
 */
export async function waitForApiResponse(
  page: Page,
  urlPattern: string | RegExp,
  options: { timeout?: number; status?: number } = {}
): Promise<{ status: number; body: unknown }> {
  const { timeout = 10000, status } = options;

  const response = await page.waitForResponse(
    (resp) => {
      const matches = typeof urlPattern === 'string'
        ? resp.url().includes(urlPattern)
        : urlPattern.test(resp.url());

      if (!matches) return false;
      if (status !== undefined && resp.status() !== status) return false;
      return true;
    },
    { timeout }
  );

  let body: unknown;
  try {
    body = await response.json();
  } catch {
    body = await response.text();
  }

  return { status: response.status(), body };
}

/**
 * Wait for loading indicator to disappear.
 * @param page - Playwright Page object
 * @param options - Wait options
 */
export async function waitForLoadingComplete(
  page: Page,
  options: { timeout?: number; selector?: string } = {}
): Promise<void> {
  const { timeout = 30000, selector = SELECTORS.ui.loading } = options;

  // First check if loading indicator exists
  const loadingLocator = page.locator(selector);
  const count = await loadingLocator.count();

  if (count > 0) {
    // Wait for it to disappear
    await loadingLocator.first().waitFor({ state: 'hidden', timeout });
  }
}

/**
 * Wait for a toast/notification message to appear.
 * @param page - Playwright Page object
 * @param options - Wait options
 */
export async function waitForToast(
  page: Page,
  options: { timeout?: number; text?: string; selector?: string } = {}
): Promise<Locator> {
  const { timeout = 10000, text, selector = SELECTORS.ui.toast } = options;

  const locator = text
    ? page.locator(selector).filter({ hasText: text })
    : page.locator(selector);

  await locator.first().waitFor({ state: 'visible', timeout });
  return locator.first();
}

/**
 * Retry an action until it succeeds or times out.
 * @param action - Async action to retry
 * @param options - Retry options
 */
export async function retryUntilSuccess<T>(
  action: () => Promise<T>,
  options: { maxAttempts?: number; delayMs?: number; timeout?: number } = {}
): Promise<T> {
  const { maxAttempts = 5, delayMs = 500, timeout = 30000 } = options;
  const startTime = Date.now();
  let lastError: Error | undefined;

  for (let attempt = 1; attempt <= maxAttempts; attempt++) {
    if (Date.now() - startTime > timeout) {
      throw new Error(`Timeout after ${timeout}ms. Last error: ${lastError?.message || 'unknown'}`);
    }

    try {
      return await action();
    } catch (error) {
      lastError = error instanceof Error ? error : new Error(String(error));

      if (attempt < maxAttempts) {
        await new Promise(resolve => setTimeout(resolve, delayMs));
      }
    }
  }

  throw new Error(`Failed after ${maxAttempts} attempts. Last error: ${lastError?.message || 'unknown'}`);
}

// =============================================================================
// Test Data Helpers
// =============================================================================

/**
 * Create a unique test identifier with timestamp and random suffix.
 * Re-exported from test-fixtures for convenience.
 */
export { generateTestId as createTestId } from './test-fixtures';

/**
 * Clean up test data after tests complete.
 * @param apiClient - APIClient instance
 * @param resources - Array of resource identifiers to clean up
 */
export async function cleanupTestData(
  apiClient: InstanceType<typeof import('./test-fixtures').APIClient>,
  resources: string[]
): Promise<void> {
  // Note: Cleanup is typically handled by test isolation
  // This function is a placeholder for custom cleanup logic
  for (const resource of resources) {
    try {
      // Attempt to delete or reset the resource
      // Implementation depends on available API endpoints
      console.log(`Cleanup: ${resource}`);
    } catch (error) {
      console.warn(`Failed to cleanup resource ${resource}:`, error);
    }
  }
}
