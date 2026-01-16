/**
 * Navigation Helpers for E2E Tests
 *
 * Provides utilities for navigation testing including:
 * - Click navigation with verification
 * - URL validation and matching
 * - Breadcrumb trail verification
 * - Active navigation state checking
 * - Route matching and path utilities
 *
 * Usage:
 *   import {
 *     clickAndNavigate,
 *     verifyUrl,
 *     verifyBreadcrumbs,
 *     verifyActiveNavState,
 *     NavigationHelper
 *   } from './utils/navigation.helpers';
 */

import { Page, Locator, expect } from '@playwright/test';

// =============================================================================
// Types and Interfaces
// =============================================================================

/**
 * Options for click navigation operations.
 */
export interface ClickNavigationOptions {
  /** Timeout for navigation in milliseconds (default: 30000) */
  timeout?: number;
  /** Wait condition after navigation (default: 'networkidle') */
  waitUntil?: 'load' | 'domcontentloaded' | 'networkidle' | 'commit';
  /** Expected URL pattern after navigation (string or RegExp) */
  expectedUrl?: string | RegExp;
  /** Force click even if element is covered (default: false) */
  force?: boolean;
}

/**
 * Options for URL verification.
 */
export interface VerifyUrlOptions {
  /** Timeout for URL to match (default: 10000) */
  timeout?: number;
  /** Whether to check for exact match vs contains (default: false for exact) */
  exact?: boolean;
  /** URL should not match (for negative assertions) */
  shouldNotMatch?: boolean;
}

/**
 * Breadcrumb item representation.
 */
export interface BreadcrumbItem {
  /** Display text of the breadcrumb */
  text: string;
  /** URL/href of the breadcrumb link (undefined for current page) */
  href?: string;
  /** Whether this is the current/active breadcrumb */
  isCurrent?: boolean;
}

/**
 * Options for breadcrumb verification.
 */
export interface VerifyBreadcrumbsOptions {
  /** Timeout for breadcrumbs to appear (default: 10000) */
  timeout?: number;
  /** Custom selector for breadcrumb container */
  containerSelector?: string;
  /** Custom selector for breadcrumb items */
  itemSelector?: string;
  /** Whether to check order strictly (default: true) */
  strictOrder?: boolean;
}

/**
 * Options for active nav state verification.
 */
export interface VerifyActiveNavOptions {
  /** Timeout for navigation to update (default: 10000) */
  timeout?: number;
  /** Custom selector for navigation container */
  navSelector?: string;
  /** Custom selector for active state indicator */
  activeSelector?: string;
  /** Attribute indicating active state (default: 'aria-current') */
  activeAttribute?: string;
}

/**
 * Navigation route definition for testing.
 */
export interface NavigationRoute {
  /** Route path (e.g., '/plans', '/plans/:id') */
  path: string;
  /** Expected page title or title pattern */
  title?: string | RegExp;
  /** Expected breadcrumb trail */
  breadcrumbs?: string[];
  /** Expected active nav item text */
  activeNav?: string;
  /** Required selectors that should be visible on this route */
  requiredSelectors?: string[];
}

// =============================================================================
// Default Selectors
// =============================================================================

/**
 * Default CSS selectors for navigation elements.
 */
const DEFAULT_NAV_SELECTORS = {
  navigation: 'nav, [role="navigation"]',
  navLink: 'nav a, [role="navigation"] a',
  activeLink: 'nav a[aria-current="page"], nav a.active, [role="navigation"] a[aria-current="page"]',
  breadcrumbContainer: '.breadcrumbs, [aria-label="Breadcrumb"], nav[aria-label*="breadcrumb"], [aria-label="breadcrumb"]',
  breadcrumbItem: '.breadcrumb-item, [role="listitem"], li',
  breadcrumbLink: 'a, [role="link"]',
  breadcrumbCurrent: '[aria-current="page"], .active, .current',
};

// =============================================================================
// Core Navigation Functions
// =============================================================================

/**
 * Click an element and wait for navigation to complete.
 * Handles various navigation patterns including SPA and traditional navigation.
 *
 * @param page - Playwright Page object
 * @param locator - Element to click (Locator or selector string)
 * @param options - Navigation options
 * @returns Promise resolving when navigation completes
 *
 * @example
 * ```ts
 * // Click a link and wait for navigation
 * await clickAndNavigate(page, page.locator('a[href="/plans"]'));
 *
 * // Click with expected URL verification
 * await clickAndNavigate(page, 'nav a.plans-link', {
 *   expectedUrl: /\/plans$/,
 *   waitUntil: 'networkidle'
 * });
 * ```
 */
export async function clickAndNavigate(
  page: Page,
  locator: Locator | string,
  options: ClickNavigationOptions = {}
): Promise<void> {
  const {
    timeout = 30000,
    waitUntil = 'networkidle',
    expectedUrl,
    force = false,
  } = options;

  // Convert string selector to locator
  const element = typeof locator === 'string' ? page.locator(locator).first() : locator;

  // Wait for element to be visible and clickable
  await element.waitFor({ state: 'visible', timeout });

  // Store current URL for comparison
  const currentUrl = page.url();

  // Perform click with navigation wait
  await Promise.all([
    page.waitForLoadState(waitUntil, { timeout }),
    element.click({ force }),
  ]);

  // Verify navigation occurred (URL should change)
  if (page.url() === currentUrl) {
    // SPA might not change URL immediately, wait a bit
    await page.waitForTimeout(100);
  }

  // Verify expected URL if provided
  if (expectedUrl) {
    await verifyUrl(page, expectedUrl, { timeout });
  }
}

/**
 * Click a navigation link by its text content.
 *
 * @param page - Playwright Page object
 * @param linkText - Text of the link to click
 * @param options - Navigation options
 *
 * @example
 * ```ts
 * await clickNavLink(page, 'Plans');
 * await clickNavLink(page, 'Settings', { expectedUrl: '/settings' });
 * ```
 */
export async function clickNavLink(
  page: Page,
  linkText: string,
  options: ClickNavigationOptions = {}
): Promise<void> {
  const navLinks = page.locator(DEFAULT_NAV_SELECTORS.navLink);
  const link = navLinks.filter({ hasText: linkText }).first();

  await clickAndNavigate(page, link, options);
}

/**
 * Click a breadcrumb link to navigate back in the trail.
 *
 * @param page - Playwright Page object
 * @param breadcrumbText - Text of the breadcrumb to click
 * @param options - Navigation options
 *
 * @example
 * ```ts
 * await clickBreadcrumb(page, 'Home');
 * await clickBreadcrumb(page, 'Plans', { expectedUrl: '/plans' });
 * ```
 */
export async function clickBreadcrumb(
  page: Page,
  breadcrumbText: string,
  options: ClickNavigationOptions = {}
): Promise<void> {
  const breadcrumbContainer = page.locator(DEFAULT_NAV_SELECTORS.breadcrumbContainer).first();
  const breadcrumbLinks = breadcrumbContainer.locator('a');
  const targetLink = breadcrumbLinks.filter({ hasText: breadcrumbText }).first();

  await clickAndNavigate(page, targetLink, options);
}

// =============================================================================
// URL Verification Functions
// =============================================================================

/**
 * Verify the current URL matches an expected pattern.
 *
 * @param page - Playwright Page object
 * @param expected - Expected URL (string, RegExp, or partial match)
 * @param options - Verification options
 *
 * @example
 * ```ts
 * // Exact URL match
 * await verifyUrl(page, '/plans');
 *
 * // RegExp pattern
 * await verifyUrl(page, /\/plans\/[\w-]+$/);
 *
 * // Partial match (contains)
 * await verifyUrl(page, 'plans', { exact: false });
 * ```
 */
export async function verifyUrl(
  page: Page,
  expected: string | RegExp,
  options: VerifyUrlOptions = {}
): Promise<void> {
  const { timeout = 10000, exact = true, shouldNotMatch = false } = options;

  if (expected instanceof RegExp) {
    if (shouldNotMatch) {
      await expect(page).not.toHaveURL(expected, { timeout });
    } else {
      await expect(page).toHaveURL(expected, { timeout });
    }
  } else if (exact) {
    // For exact string match, check full path
    const expectedPattern = expected.startsWith('/')
      ? new RegExp(`${expected.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}$`)
      : new RegExp(expected.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'));

    if (shouldNotMatch) {
      await expect(page).not.toHaveURL(expectedPattern, { timeout });
    } else {
      await expect(page).toHaveURL(expectedPattern, { timeout });
    }
  } else {
    // Contains check
    if (shouldNotMatch) {
      const url = page.url();
      expect(url).not.toContain(expected);
    } else {
      await page.waitForURL(`**/*${expected}*`, { timeout });
    }
  }
}

/**
 * Get the current URL path (without origin).
 *
 * @param page - Playwright Page object
 * @returns Current URL path
 *
 * @example
 * ```ts
 * const path = getCurrentPath(page);
 * expect(path).toBe('/plans/my-plan');
 * ```
 */
export function getCurrentPath(page: Page): string {
  const url = new URL(page.url());
  return url.pathname + url.search + url.hash;
}

/**
 * Get URL segments from the current path.
 *
 * @param page - Playwright Page object
 * @returns Array of path segments
 *
 * @example
 * ```ts
 * // On URL /plans/my-plan/edit
 * const segments = getUrlSegments(page);
 * // Returns ['plans', 'my-plan', 'edit']
 * ```
 */
export function getUrlSegments(page: Page): string[] {
  const url = new URL(page.url());
  return url.pathname.split('/').filter(segment => segment.length > 0);
}

/**
 * Check if the current URL matches a route pattern.
 *
 * @param page - Playwright Page object
 * @param pattern - Route pattern with optional params (e.g., '/plans/:id')
 * @returns True if URL matches pattern
 *
 * @example
 * ```ts
 * // On URL /plans/123
 * const matches = matchesRoutePattern(page, '/plans/:id');
 * // Returns true
 * ```
 */
export function matchesRoutePattern(page: Page, pattern: string): boolean {
  const currentPath = getCurrentPath(page).split('?')[0]; // Remove query string
  const patternParts = pattern.split('/').filter(p => p.length > 0);
  const pathParts = currentPath.split('/').filter(p => p.length > 0);

  if (patternParts.length !== pathParts.length) {
    return false;
  }

  return patternParts.every((part, index) => {
    // :param matches any value
    if (part.startsWith(':')) {
      return true;
    }
    // * matches any remaining path
    if (part === '*') {
      return true;
    }
    return part === pathParts[index];
  });
}

/**
 * Extract route parameters from the current URL.
 *
 * @param page - Playwright Page object
 * @param pattern - Route pattern with params (e.g., '/plans/:planId/edit')
 * @returns Object with extracted param values
 *
 * @example
 * ```ts
 * // On URL /plans/my-plan-123/edit
 * const params = extractRouteParams(page, '/plans/:planId/edit');
 * // Returns { planId: 'my-plan-123' }
 * ```
 */
export function extractRouteParams(
  page: Page,
  pattern: string
): Record<string, string> {
  const currentPath = getCurrentPath(page).split('?')[0];
  const patternParts = pattern.split('/').filter(p => p.length > 0);
  const pathParts = currentPath.split('/').filter(p => p.length > 0);

  const params: Record<string, string> = {};

  patternParts.forEach((part, index) => {
    if (part.startsWith(':') && pathParts[index]) {
      const paramName = part.slice(1);
      params[paramName] = pathParts[index];
    }
  });

  return params;
}

// =============================================================================
// Breadcrumb Verification Functions
// =============================================================================

/**
 * Get all breadcrumb items from the page.
 *
 * @param page - Playwright Page object
 * @param options - Options with custom selectors
 * @returns Array of breadcrumb items
 *
 * @example
 * ```ts
 * const breadcrumbs = await getBreadcrumbs(page);
 * // Returns [{ text: 'Home', href: '/' }, { text: 'Plans', href: '/plans' }, { text: 'My Plan', isCurrent: true }]
 * ```
 */
export async function getBreadcrumbs(
  page: Page,
  options: { containerSelector?: string; itemSelector?: string } = {}
): Promise<BreadcrumbItem[]> {
  const {
    containerSelector = DEFAULT_NAV_SELECTORS.breadcrumbContainer,
    itemSelector = DEFAULT_NAV_SELECTORS.breadcrumbItem,
  } = options;

  const container = page.locator(containerSelector).first();
  const containerExists = await container.count() > 0;

  if (!containerExists) {
    return [];
  }

  const items = container.locator(itemSelector);
  const count = await items.count();
  const breadcrumbs: BreadcrumbItem[] = [];

  for (let i = 0; i < count; i++) {
    const item = items.nth(i);
    const link = item.locator('a').first();
    const hasLink = await link.count() > 0;

    const text = await item.textContent() || '';
    const cleanText = text.trim().replace(/[>\/]+/g, '').trim();

    if (cleanText.length === 0) {
      continue;
    }

    const breadcrumb: BreadcrumbItem = {
      text: cleanText,
      isCurrent: !hasLink || await item.locator('[aria-current="page"]').count() > 0,
    };

    if (hasLink) {
      breadcrumb.href = await link.getAttribute('href') || undefined;
    }

    breadcrumbs.push(breadcrumb);
  }

  return breadcrumbs;
}

/**
 * Verify the breadcrumb trail matches expected values.
 *
 * @param page - Playwright Page object
 * @param expectedTrail - Array of expected breadcrumb texts in order
 * @param options - Verification options
 *
 * @example
 * ```ts
 * await verifyBreadcrumbs(page, ['Home', 'Plans', 'My Plan']);
 * ```
 */
export async function verifyBreadcrumbs(
  page: Page,
  expectedTrail: string[],
  options: VerifyBreadcrumbsOptions = {}
): Promise<void> {
  const {
    timeout = 10000,
    containerSelector,
    itemSelector,
    strictOrder = true,
  } = options;

  // Wait for breadcrumbs to appear
  const container = page.locator(containerSelector || DEFAULT_NAV_SELECTORS.breadcrumbContainer).first();
  await container.waitFor({ state: 'visible', timeout });

  const breadcrumbs = await getBreadcrumbs(page, { containerSelector, itemSelector });
  const breadcrumbTexts = breadcrumbs.map(b => b.text);

  if (strictOrder) {
    expect(breadcrumbTexts).toEqual(expectedTrail);
  } else {
    // Check all expected items exist, regardless of order
    for (const expected of expectedTrail) {
      expect(breadcrumbTexts).toContain(expected);
    }
  }
}

/**
 * Verify the last breadcrumb (current page) matches expected text.
 *
 * @param page - Playwright Page object
 * @param expectedText - Expected text of current breadcrumb
 * @param options - Verification options
 *
 * @example
 * ```ts
 * await verifyCurrentBreadcrumb(page, 'Plan Details');
 * ```
 */
export async function verifyCurrentBreadcrumb(
  page: Page,
  expectedText: string,
  options: { timeout?: number } = {}
): Promise<void> {
  const { timeout = 10000 } = options;

  const breadcrumbs = await getBreadcrumbs(page);

  // Find the current breadcrumb (last one or one marked as current)
  const currentBreadcrumb = breadcrumbs.find(b => b.isCurrent) || breadcrumbs[breadcrumbs.length - 1];

  if (!currentBreadcrumb) {
    throw new Error('No breadcrumbs found on page');
  }

  expect(currentBreadcrumb.text).toBe(expectedText);
}

// =============================================================================
// Active Navigation State Functions
// =============================================================================

/**
 * Get the currently active navigation item.
 *
 * @param page - Playwright Page object
 * @param options - Options with custom selectors
 * @returns Active nav item text or null if none found
 *
 * @example
 * ```ts
 * const activeNav = await getActiveNavItem(page);
 * expect(activeNav).toBe('Plans');
 * ```
 */
export async function getActiveNavItem(
  page: Page,
  options: { activeSelector?: string } = {}
): Promise<string | null> {
  const { activeSelector = DEFAULT_NAV_SELECTORS.activeLink } = options;

  const activeLink = page.locator(activeSelector).first();
  const exists = await activeLink.count() > 0;

  if (!exists) {
    return null;
  }

  return await activeLink.textContent();
}

/**
 * Verify the active navigation state matches expected value.
 *
 * @param page - Playwright Page object
 * @param expectedActiveText - Expected text of active nav item
 * @param options - Verification options
 *
 * @example
 * ```ts
 * await verifyActiveNavState(page, 'Plans');
 * ```
 */
export async function verifyActiveNavState(
  page: Page,
  expectedActiveText: string,
  options: VerifyActiveNavOptions = {}
): Promise<void> {
  const {
    timeout = 10000,
    navSelector = DEFAULT_NAV_SELECTORS.navigation,
    activeSelector = DEFAULT_NAV_SELECTORS.activeLink,
    activeAttribute = 'aria-current',
  } = options;

  // Wait for navigation to be visible
  const nav = page.locator(navSelector).first();
  await nav.waitFor({ state: 'visible', timeout });

  // Find the active link
  const activeLink = page.locator(activeSelector).first();

  // Wait for active state to be set
  await expect(activeLink).toBeVisible({ timeout });

  // Verify text matches
  const activeText = await activeLink.textContent();
  expect(activeText?.trim()).toBe(expectedActiveText);

  // Optionally verify the active attribute
  const ariaCurrent = await activeLink.getAttribute(activeAttribute);
  expect(ariaCurrent).toBeTruthy();
}

/**
 * Verify a specific nav link is NOT active.
 *
 * @param page - Playwright Page object
 * @param linkText - Text of the link to check
 * @param options - Verification options
 *
 * @example
 * ```ts
 * await verifyNavLinkInactive(page, 'Settings');
 * ```
 */
export async function verifyNavLinkInactive(
  page: Page,
  linkText: string,
  options: { navSelector?: string; activeAttribute?: string } = {}
): Promise<void> {
  const {
    navSelector = DEFAULT_NAV_SELECTORS.navigation,
    activeAttribute = 'aria-current',
  } = options;

  const nav = page.locator(navSelector).first();
  const link = nav.locator('a').filter({ hasText: linkText }).first();

  const ariaCurrent = await link.getAttribute(activeAttribute);
  expect(ariaCurrent).toBeNull();

  // Also check for .active class
  const hasActiveClass = await link.evaluate(el => el.classList.contains('active'));
  expect(hasActiveClass).toBe(false);
}

// =============================================================================
// Navigation Helper Class
// =============================================================================

/**
 * Navigation helper class for comprehensive navigation testing.
 * Provides a fluent interface for navigation operations.
 *
 * @example
 * ```ts
 * const nav = new NavigationHelper(page);
 *
 * // Navigate and verify
 * await nav.navigateTo('/plans');
 * await nav.verifyOnPage('/plans');
 * await nav.verifyActiveNav('Plans');
 *
 * // Click navigation with verification
 * await nav.clickLink('Settings').then(nav => nav.verifyOnPage('/settings'));
 * ```
 */
export class NavigationHelper {
  constructor(private page: Page) {}

  /**
   * Navigate to a specific path.
   */
  async navigateTo(path: string, options: { waitUntil?: 'load' | 'networkidle' } = {}): Promise<this> {
    const { waitUntil = 'networkidle' } = options;
    await this.page.goto(path);
    await this.page.waitForLoadState(waitUntil);
    return this;
  }

  /**
   * Click a navigation link by text.
   */
  async clickLink(linkText: string, options?: ClickNavigationOptions): Promise<this> {
    await clickNavLink(this.page, linkText, options);
    return this;
  }

  /**
   * Click a breadcrumb to navigate.
   */
  async clickBreadcrumb(text: string, options?: ClickNavigationOptions): Promise<this> {
    await clickBreadcrumb(this.page, text, options);
    return this;
  }

  /**
   * Verify currently on expected page.
   */
  async verifyOnPage(urlPattern: string | RegExp, options?: VerifyUrlOptions): Promise<this> {
    await verifyUrl(this.page, urlPattern, options);
    return this;
  }

  /**
   * Verify not on a specific page.
   */
  async verifyNotOnPage(urlPattern: string | RegExp, options?: VerifyUrlOptions): Promise<this> {
    await verifyUrl(this.page, urlPattern, { ...options, shouldNotMatch: true });
    return this;
  }

  /**
   * Verify breadcrumb trail.
   */
  async verifyBreadcrumbs(expectedTrail: string[], options?: VerifyBreadcrumbsOptions): Promise<this> {
    await verifyBreadcrumbs(this.page, expectedTrail, options);
    return this;
  }

  /**
   * Verify active navigation item.
   */
  async verifyActiveNav(expectedText: string, options?: VerifyActiveNavOptions): Promise<this> {
    await verifyActiveNavState(this.page, expectedText, options);
    return this;
  }

  /**
   * Get current path.
   */
  getPath(): string {
    return getCurrentPath(this.page);
  }

  /**
   * Get URL segments.
   */
  getSegments(): string[] {
    return getUrlSegments(this.page);
  }

  /**
   * Check if on a route pattern.
   */
  matchesRoute(pattern: string): boolean {
    return matchesRoutePattern(this.page, pattern);
  }

  /**
   * Extract route params.
   */
  getRouteParams(pattern: string): Record<string, string> {
    return extractRouteParams(this.page, pattern);
  }

  /**
   * Wait for navigation to complete after an action.
   */
  async waitForNavigation(
    action: () => Promise<void>,
    options: { waitUntil?: 'load' | 'networkidle'; timeout?: number } = {}
  ): Promise<this> {
    const { waitUntil = 'networkidle', timeout = 30000 } = options;
    await Promise.all([
      this.page.waitForLoadState(waitUntil, { timeout }),
      action(),
    ]);
    return this;
  }

  /**
   * Go back in browser history.
   */
  async goBack(options: { waitUntil?: 'load' | 'networkidle' } = {}): Promise<this> {
    const { waitUntil = 'networkidle' } = options;
    await this.page.goBack({ waitUntil });
    return this;
  }

  /**
   * Go forward in browser history.
   */
  async goForward(options: { waitUntil?: 'load' | 'networkidle' } = {}): Promise<this> {
    const { waitUntil = 'networkidle' } = options;
    await this.page.goForward({ waitUntil });
    return this;
  }

  /**
   * Verify a full route definition.
   */
  async verifyRoute(route: NavigationRoute, options: { timeout?: number } = {}): Promise<this> {
    const { timeout = 10000 } = options;

    // Verify URL
    await verifyUrl(this.page, route.path, { timeout });

    // Verify title if provided
    if (route.title) {
      await expect(this.page).toHaveTitle(route.title, { timeout });
    }

    // Verify breadcrumbs if provided
    if (route.breadcrumbs) {
      await verifyBreadcrumbs(this.page, route.breadcrumbs, { timeout });
    }

    // Verify active nav if provided
    if (route.activeNav) {
      await verifyActiveNavState(this.page, route.activeNav, { timeout });
    }

    // Verify required selectors
    if (route.requiredSelectors) {
      for (const selector of route.requiredSelectors) {
        await expect(this.page.locator(selector).first()).toBeVisible({ timeout });
      }
    }

    return this;
  }
}

// =============================================================================
// Exports
// =============================================================================

export { DEFAULT_NAV_SELECTORS };
