/**
 * E2E Test Utilities
 *
 * Common test helpers for E2E tests.
 * This module provides reusable utilities that complement the fixtures.
 *
 * Usage:
 *   import { waitForPageLoad, getByTestId, assertNoConsoleErrors, retryAction } from './utils';
 *   import { clickAndNavigate, verifyUrl, verifyBreadcrumbs, NavigationHelper } from './utils';
 */

import { Page, Locator, ConsoleMessage } from '@playwright/test';
import { expect } from '@playwright/test';

// =============================================================================
// Page Load Utilities
// =============================================================================

/**
 * Options for waitForPageLoad function.
 */
export interface WaitForPageLoadOptions {
  /** Maximum time to wait in milliseconds (default: 30000) */
  timeout?: number;
  /** Wait for network idle after load (default: true) */
  waitForNetworkIdle?: boolean;
  /** Additional selectors that must be visible for page to be considered loaded */
  requiredSelectors?: string[];
}

/**
 * Wait for a page to fully load with comprehensive checks.
 * This includes waiting for DOM content, network idle, and optional selectors.
 *
 * @param page - Playwright Page object
 * @param options - Wait options
 *
 * @example
 * ```ts
 * await waitForPageLoad(page);
 * await waitForPageLoad(page, { requiredSelectors: ['[data-testid="main-content"]'] });
 * ```
 */
export async function waitForPageLoad(
  page: Page,
  options: WaitForPageLoadOptions = {}
): Promise<void> {
  const {
    timeout = 30000,
    waitForNetworkIdle = true,
    requiredSelectors = []
  } = options;

  // Wait for DOM content to be loaded
  await page.waitForLoadState('domcontentloaded', { timeout });

  // Wait for network idle if requested
  if (waitForNetworkIdle) {
    try {
      await page.waitForLoadState('networkidle', { timeout });
    } catch (error) {
      // Network idle may timeout on pages with long-polling or WebSockets
      // Continue if DOM is ready
      console.warn('Network idle timeout - continuing with DOM ready state');
    }
  }

  // Wait for required selectors to be visible
  for (const selector of requiredSelectors) {
    await page.locator(selector).first().waitFor({
      state: 'visible',
      timeout
    });
  }
}

/**
 * Wait for page to be interactive (ready for user input).
 * This is stricter than waitForPageLoad and ensures no loading spinners.
 *
 * @param page - Playwright Page object
 * @param options - Wait options
 */
export async function waitForInteractive(
  page: Page,
  options: { timeout?: number; loadingSelector?: string } = {}
): Promise<void> {
  const {
    timeout = 30000,
    loadingSelector = '.loading, .spinner, [aria-busy="true"], [data-loading="true"]'
  } = options;

  // Wait for page load
  await waitForPageLoad(page, { timeout, waitForNetworkIdle: true });

  // Wait for loading indicators to disappear
  const loadingLocator = page.locator(loadingSelector);
  const loadingCount = await loadingLocator.count();

  if (loadingCount > 0) {
    await loadingLocator.first().waitFor({ state: 'hidden', timeout });
  }

  // Ensure body is visible and interactive
  await page.locator('body').waitFor({ state: 'visible', timeout });
}

// =============================================================================
// Test ID Utilities
// =============================================================================

/**
 * Get a locator by data-testid attribute.
 * This is a convenience wrapper that provides consistent test ID selection.
 *
 * @param page - Playwright Page object
 * @param testId - The data-testid value to locate
 * @returns Playwright Locator for the element
 *
 * @example
 * ```ts
 * const submitButton = getByTestId(page, 'submit-button');
 * await submitButton.click();
 * ```
 */
export function getByTestId(page: Page, testId: string): Locator {
  return page.locator(`[data-testid="${testId}"]`);
}

/**
 * Get all elements matching a data-testid attribute.
 *
 * @param page - Playwright Page object
 * @param testId - The data-testid value to locate
 * @returns Playwright Locator matching all elements with the testid
 */
export function getAllByTestId(page: Page, testId: string): Locator {
  return page.locator(`[data-testid="${testId}"]`);
}

/**
 * Check if an element with data-testid exists on the page.
 *
 * @param page - Playwright Page object
 * @param testId - The data-testid value to check
 * @returns Promise resolving to true if element exists
 */
export async function hasTestId(page: Page, testId: string): Promise<boolean> {
  const count = await getByTestId(page, testId).count();
  return count > 0;
}

/**
 * Wait for an element with data-testid to be visible.
 *
 * @param page - Playwright Page object
 * @param testId - The data-testid value to wait for
 * @param options - Wait options
 */
export async function waitForTestId(
  page: Page,
  testId: string,
  options: { timeout?: number; state?: 'visible' | 'attached' | 'hidden' } = {}
): Promise<Locator> {
  const { timeout = 10000, state = 'visible' } = options;
  const locator = getByTestId(page, testId);
  await locator.waitFor({ state, timeout });
  return locator;
}

// =============================================================================
// Console Error Tracking
// =============================================================================

/**
 * Console message collected during test execution.
 */
export interface CollectedConsoleMessage {
  type: 'log' | 'debug' | 'info' | 'error' | 'warning' | 'trace';
  text: string;
  location?: {
    url: string;
    lineNumber: number;
    columnNumber: number;
  };
}

/**
 * Options for console error assertion.
 */
export interface AssertNoConsoleErrorsOptions {
  /** Message types to treat as errors (default: ['error']) */
  errorTypes?: Array<'error' | 'warning'>;
  /** Patterns to ignore (useful for known third-party errors) */
  ignorePatterns?: Array<string | RegExp>;
  /** Whether to include warnings as errors (default: false) */
  includeWarnings?: boolean;
}

/**
 * Console error collector for tracking errors during test execution.
 * Use this class to collect and assert on console errors.
 *
 * @example
 * ```ts
 * const collector = new ConsoleErrorCollector(page);
 * await page.goto('/some-page');
 * await doSomeActions();
 * collector.assertNoErrors(); // Throws if any console.error was logged
 * ```
 */
export class ConsoleErrorCollector {
  private messages: CollectedConsoleMessage[] = [];
  private page: Page;

  constructor(page: Page) {
    this.page = page;
    this.page.on('console', this.handleConsoleMessage.bind(this));
  }

  private handleConsoleMessage(msg: ConsoleMessage): void {
    this.messages.push({
      type: msg.type() as CollectedConsoleMessage['type'],
      text: msg.text(),
      location: msg.location()
        ? {
            url: msg.location().url,
            lineNumber: msg.location().lineNumber,
            columnNumber: msg.location().columnNumber
          }
        : undefined
    });
  }

  /**
   * Get all collected console messages.
   */
  getMessages(): CollectedConsoleMessage[] {
    return [...this.messages];
  }

  /**
   * Get only error messages.
   */
  getErrors(): CollectedConsoleMessage[] {
    return this.messages.filter(m => m.type === 'error');
  }

  /**
   * Get only warning messages.
   */
  getWarnings(): CollectedConsoleMessage[] {
    return this.messages.filter(m => m.type === 'warning');
  }

  /**
   * Clear all collected messages.
   */
  clear(): void {
    this.messages = [];
  }

  /**
   * Stop collecting console messages.
   */
  stop(): void {
    this.page.off('console', this.handleConsoleMessage.bind(this));
  }

  /**
   * Assert that no console errors were logged.
   * Throws an assertion error if errors were found.
   */
  assertNoErrors(options: AssertNoConsoleErrorsOptions = {}): void {
    const {
      errorTypes = ['error'],
      ignorePatterns = [],
      includeWarnings = false
    } = options;

    const typesToCheck = includeWarnings
      ? [...errorTypes, 'warning' as const]
      : errorTypes;

    const errors = this.messages.filter(m => {
      // Check if message type should be treated as error
      if (!typesToCheck.includes(m.type as 'error' | 'warning')) {
        return false;
      }

      // Check if message matches any ignore pattern
      for (const pattern of ignorePatterns) {
        if (typeof pattern === 'string') {
          if (m.text.includes(pattern)) return false;
        } else {
          if (pattern.test(m.text)) return false;
        }
      }

      return true;
    });

    if (errors.length > 0) {
      const errorMessages = errors
        .map(e => `[${e.type}] ${e.text}`)
        .join('\n');
      throw new Error(
        `Found ${errors.length} console error(s):\n${errorMessages}`
      );
    }
  }
}

/**
 * Assert that no console errors occurred on a page.
 * This is a simpler one-shot version that checks current state.
 *
 * @param page - Playwright Page object
 * @param options - Assertion options
 *
 * @example
 * ```ts
 * // At the end of a test:
 * await assertNoConsoleErrors(page);
 * ```
 */
export async function assertNoConsoleErrors(
  page: Page,
  options: AssertNoConsoleErrorsOptions = {}
): Promise<void> {
  const {
    ignorePatterns = [],
    includeWarnings = false
  } = options;

  // Create a collector and immediately check
  const collector = new ConsoleErrorCollector(page);

  // Wait briefly for any pending errors to be logged
  await page.waitForTimeout(100);

  collector.assertNoErrors({
    ignorePatterns,
    includeWarnings
  });

  collector.stop();
}

// =============================================================================
// Retry Utilities
// =============================================================================

/**
 * Options for retryAction function.
 */
export interface RetryActionOptions {
  /** Maximum number of retry attempts (default: 3) */
  maxAttempts?: number;
  /** Delay between retries in milliseconds (default: 1000) */
  delayMs?: number;
  /** Maximum total time to spend retrying in milliseconds (default: 30000) */
  timeout?: number;
  /** Function to determine if error is retryable (default: all errors) */
  isRetryable?: (error: Error) => boolean;
  /** Callback called before each retry attempt */
  onRetry?: (attempt: number, error: Error) => void;
}

/**
 * Retry an async action until it succeeds or exhausts retries.
 * Useful for flaky operations or waiting for eventual consistency.
 *
 * @param action - Async function to retry
 * @param options - Retry configuration options
 * @returns Promise resolving to the action result
 *
 * @example
 * ```ts
 * const result = await retryAction(async () => {
 *   const element = page.locator('[data-testid="dynamic-content"]');
 *   await expect(element).toBeVisible();
 *   return element.textContent();
 * }, { maxAttempts: 5, delayMs: 500 });
 * ```
 */
export async function retryAction<T>(
  action: () => Promise<T>,
  options: RetryActionOptions = {}
): Promise<T> {
  const {
    maxAttempts = 3,
    delayMs = 1000,
    timeout = 30000,
    isRetryable = () => true,
    onRetry
  } = options;

  const startTime = Date.now();
  let lastError: Error | undefined;
  let attempt = 0;

  while (attempt < maxAttempts) {
    attempt++;

    // Check timeout
    if (Date.now() - startTime > timeout) {
      throw new Error(
        `Timeout after ${timeout}ms on attempt ${attempt}. Last error: ${lastError?.message || 'unknown'}`
      );
    }

    try {
      return await action();
    } catch (error) {
      lastError = error instanceof Error ? error : new Error(String(error));

      // Check if error is retryable
      if (!isRetryable(lastError)) {
        throw lastError;
      }

      // Call onRetry callback if provided
      if (onRetry && attempt < maxAttempts) {
        onRetry(attempt, lastError);
      }

      // Wait before next attempt (unless this was the last attempt)
      if (attempt < maxAttempts) {
        await new Promise(resolve => setTimeout(resolve, delayMs));
      }
    }
  }

  throw new Error(
    `Failed after ${maxAttempts} attempts. Last error: ${lastError?.message || 'unknown'}`
  );
}

/**
 * Retry an action with exponential backoff.
 *
 * @param action - Async function to retry
 * @param options - Retry configuration options
 */
export async function retryWithBackoff<T>(
  action: () => Promise<T>,
  options: Omit<RetryActionOptions, 'delayMs'> & { initialDelayMs?: number; maxDelayMs?: number } = {}
): Promise<T> {
  const {
    maxAttempts = 3,
    initialDelayMs = 500,
    maxDelayMs = 10000,
    timeout = 30000,
    isRetryable = () => true,
    onRetry
  } = options;

  const startTime = Date.now();
  let lastError: Error | undefined;
  let attempt = 0;
  let currentDelay = initialDelayMs;

  while (attempt < maxAttempts) {
    attempt++;

    if (Date.now() - startTime > timeout) {
      throw new Error(
        `Timeout after ${timeout}ms on attempt ${attempt}. Last error: ${lastError?.message || 'unknown'}`
      );
    }

    try {
      return await action();
    } catch (error) {
      lastError = error instanceof Error ? error : new Error(String(error));

      if (!isRetryable(lastError)) {
        throw lastError;
      }

      if (onRetry && attempt < maxAttempts) {
        onRetry(attempt, lastError);
      }

      if (attempt < maxAttempts) {
        await new Promise(resolve => setTimeout(resolve, currentDelay));
        // Exponential backoff with max cap
        currentDelay = Math.min(currentDelay * 2, maxDelayMs);
      }
    }
  }

  throw new Error(
    `Failed after ${maxAttempts} attempts. Last error: ${lastError?.message || 'unknown'}`
  );
}

// =============================================================================
// Additional Helper Utilities
// =============================================================================

/**
 * Scroll an element into view and ensure it's visible.
 *
 * @param locator - Playwright Locator for the element
 */
export async function scrollIntoViewAndWait(locator: Locator): Promise<void> {
  await locator.scrollIntoViewIfNeeded();
  await locator.waitFor({ state: 'visible' });
}

/**
 * Take a screenshot with a descriptive name.
 *
 * @param page - Playwright Page object
 * @param name - Descriptive name for the screenshot
 * @param options - Screenshot options
 */
export async function takeDebugScreenshot(
  page: Page,
  name: string,
  options: { fullPage?: boolean } = {}
): Promise<Buffer> {
  const { fullPage = true } = options;
  const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
  const filename = `debug-${name}-${timestamp}.png`;

  return page.screenshot({
    path: `./test-results/${filename}`,
    fullPage
  });
}

/**
 * Fill a form field with retry logic (handles delayed rendering).
 *
 * @param page - Playwright Page object
 * @param selector - CSS selector for the input
 * @param value - Value to fill
 * @param options - Fill options
 */
export async function fillWithRetry(
  page: Page,
  selector: string,
  value: string,
  options: { timeout?: number; clear?: boolean } = {}
): Promise<void> {
  const { timeout = 10000, clear = true } = options;

  await retryAction(
    async () => {
      const locator = page.locator(selector).first();
      await locator.waitFor({ state: 'visible', timeout: 5000 });

      if (clear) {
        await locator.clear();
      }

      await locator.fill(value);

      // Verify the value was set
      const actualValue = await locator.inputValue();
      expect(actualValue).toBe(value);
    },
    { maxAttempts: 3, delayMs: 500, timeout }
  );
}

/**
 * Click an element with retry logic.
 *
 * @param page - Playwright Page object
 * @param selector - CSS selector for the element
 * @param options - Click options
 */
export async function clickWithRetry(
  page: Page,
  selector: string,
  options: { timeout?: number; force?: boolean } = {}
): Promise<void> {
  const { timeout = 10000, force = false } = options;

  await retryAction(
    async () => {
      const locator = page.locator(selector).first();
      await locator.waitFor({ state: 'visible', timeout: 5000 });
      await locator.click({ force });
    },
    { maxAttempts: 3, delayMs: 500, timeout }
  );
}

/**
 * Wait for a URL pattern and return when matched.
 *
 * @param page - Playwright Page object
 * @param pattern - URL pattern (string or RegExp)
 * @param options - Wait options
 */
export async function waitForUrl(
  page: Page,
  pattern: string | RegExp,
  options: { timeout?: number } = {}
): Promise<void> {
  const { timeout = 30000 } = options;
  await page.waitForURL(pattern, { timeout });
}

/**
 * Get the current page title with error handling.
 *
 * @param page - Playwright Page object
 * @returns Page title or empty string if not available
 */
export async function getPageTitle(page: Page): Promise<string> {
  try {
    return await page.title();
  } catch {
    return '';
  }
}

/**
 * Check if page has any visible error states.
 *
 * @param page - Playwright Page object
 * @param errorSelectors - Selectors that indicate error states
 */
export async function hasVisibleErrors(
  page: Page,
  errorSelectors: string[] = [
    '.error',
    '[role="alert"][aria-live="assertive"]',
    '.error-message',
    '.error-banner'
  ]
): Promise<boolean> {
  for (const selector of errorSelectors) {
    const locator = page.locator(selector);
    const count = await locator.count();

    for (let i = 0; i < count; i++) {
      const isVisible = await locator.nth(i).isVisible();
      if (isVisible) {
        return true;
      }
    }
  }

  return false;
}

// =============================================================================
// Navigation Helpers (from navigation.helpers.ts)
// =============================================================================

export {
  // Core navigation functions
  clickAndNavigate,
  clickNavLink,
  clickBreadcrumb,
  // URL verification
  verifyUrl,
  getCurrentPath,
  getUrlSegments,
  matchesRoutePattern,
  extractRouteParams,
  // Breadcrumb verification
  getBreadcrumbs,
  verifyBreadcrumbs,
  verifyCurrentBreadcrumb,
  // Active nav state
  getActiveNavItem,
  verifyActiveNavState,
  verifyNavLinkInactive,
  // Helper class
  NavigationHelper,
  // Selectors
  DEFAULT_NAV_SELECTORS,
} from './navigation.helpers';

// Re-export types from navigation helpers
export type {
  ClickNavigationOptions,
  VerifyUrlOptions,
  BreadcrumbItem,
  VerifyBreadcrumbsOptions,
  VerifyActiveNavOptions,
  NavigationRoute,
} from './navigation.helpers';

// =============================================================================
// Accessibility Helpers (from accessibility.helpers.ts)
// =============================================================================

export {
  // Core audit functions
  runAccessibilityAudit,
  runQuickAccessibilityAudit,
  runWcag21AAAudit,
  auditElement,
  // Violation filtering
  filterViolationsBySeverity,
  filterViolationsByTags,
  filterViolationsByRules,
  excludeViolationsByRules,
  groupViolationsBySeverity,
  sortViolationsBySeverity,
  getViolationCounts,
  getTotalAffectedElements,
  // Report generation
  generateAccessibilityReport,
  // Assertion helpers
  assertNoCriticalViolations,
  assertNoViolationsAboveSeverity,
  assertWcag21AACompliant,
  // Helper class
  AccessibilityHelper,
  // Rule sets
  ACCESSIBILITY_RULE_SETS,
  SEVERITY_ORDER,
} from './accessibility.helpers';

// Re-export types from accessibility helpers
export type {
  ViolationSeverity,
  ViolationNode,
  AccessibilityViolation,
  AccessibilityAuditResult,
  AccessibilityAuditOptions,
  AccessibilityReportOptions,
} from './accessibility.helpers';
