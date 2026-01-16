/**
 * Accessibility Helpers for E2E Tests
 *
 * Provides utilities for accessibility testing using axe-core:
 * - Running accessibility audits on pages
 * - Filtering violations by severity
 * - Generating accessibility reports
 * - Custom rule configuration
 *
 * Usage:
 *   import {
 *     runAccessibilityAudit,
 *     filterViolationsBySeverity,
 *     generateAccessibilityReport,
 *     AccessibilityHelper
 *   } from './utils/accessibility.helpers';
 */

import { Page, Locator } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

// =============================================================================
// Types and Interfaces
// =============================================================================

/**
 * Severity levels for accessibility violations.
 * - critical: Must fix - blocks users from accessing content
 * - serious: Should fix - significantly impacts user experience
 * - moderate: Should fix - impacts user experience
 * - minor: May fix - causes minor inconvenience
 */
export type ViolationSeverity = 'critical' | 'serious' | 'moderate' | 'minor';

/**
 * Axe violation node (affected element).
 */
export interface ViolationNode {
  /** HTML snippet of the affected element */
  html: string;
  /** Target selector for the element */
  target: string[];
  /** Failure summary */
  failureSummary?: string;
  /** Impact level */
  impact?: ViolationSeverity;
}

/**
 * Single accessibility violation from axe-core.
 */
export interface AccessibilityViolation {
  /** Rule ID (e.g., 'color-contrast', 'button-name') */
  id: string;
  /** Impact severity */
  impact?: ViolationSeverity;
  /** Human-readable description */
  description: string;
  /** Help text with remediation guidance */
  help: string;
  /** URL to learn more about this rule */
  helpUrl: string;
  /** WCAG tags (e.g., 'wcag2a', 'wcag21aa') */
  tags: string[];
  /** Affected elements */
  nodes: ViolationNode[];
}

/**
 * Result of an accessibility audit.
 */
export interface AccessibilityAuditResult {
  /** All violations found */
  violations: AccessibilityViolation[];
  /** Rules that passed */
  passes: Array<{ id: string; description: string }>;
  /** Rules that were incomplete (need manual review) */
  incomplete: Array<{ id: string; description: string; nodes: ViolationNode[] }>;
  /** Rules that were inapplicable to this page */
  inapplicable: Array<{ id: string; description: string }>;
  /** Timestamp of the audit */
  timestamp: string;
  /** URL that was audited */
  url: string;
  /** Total counts by category */
  summary: {
    violations: number;
    passes: number;
    incomplete: number;
    inapplicable: number;
  };
}

/**
 * Options for running an accessibility audit.
 */
export interface AccessibilityAuditOptions {
  /** Include specific axe rules (by ID) */
  includeRules?: string[];
  /** Exclude specific axe rules (by ID) */
  excludeRules?: string[];
  /** Run only rules with specific WCAG tags */
  wcagTags?: string[];
  /** Limit audit to specific CSS selector */
  selector?: string;
  /** Exclude elements matching these selectors */
  excludeSelectors?: string[];
  /** Minimum severity to include in results */
  minSeverity?: ViolationSeverity;
  /** Custom axe-core options */
  axeOptions?: object;
}

/**
 * Options for generating accessibility reports.
 */
export interface AccessibilityReportOptions {
  /** Include passing rules in report (default: false) */
  includePasses?: boolean;
  /** Include incomplete rules in report (default: true) */
  includeIncomplete?: boolean;
  /** Include inapplicable rules in report (default: false) */
  includeInapplicable?: boolean;
  /** Format for the report output */
  format?: 'text' | 'markdown' | 'json';
  /** Include detailed remediation suggestions (default: true) */
  includeRemediation?: boolean;
  /** Group violations by rule or by impact (default: 'impact') */
  groupBy?: 'impact' | 'rule' | 'element';
}

/**
 * Severity level order for sorting and filtering.
 */
const SEVERITY_ORDER: Record<ViolationSeverity, number> = {
  critical: 4,
  serious: 3,
  moderate: 2,
  minor: 1,
};

// =============================================================================
// Core Audit Functions
// =============================================================================

/**
 * Run an accessibility audit on a page using axe-core.
 *
 * @param page - Playwright Page object
 * @param options - Audit configuration options
 * @returns Promise resolving to audit results
 *
 * @example
 * ```ts
 * // Basic audit
 * const results = await runAccessibilityAudit(page);
 *
 * // Audit with WCAG 2.1 AA rules only
 * const results = await runAccessibilityAudit(page, {
 *   wcagTags: ['wcag21aa']
 * });
 *
 * // Audit specific section
 * const results = await runAccessibilityAudit(page, {
 *   selector: '[data-testid="main-content"]'
 * });
 * ```
 */
export async function runAccessibilityAudit(
  page: Page,
  options: AccessibilityAuditOptions = {}
): Promise<AccessibilityAuditResult> {
  const {
    includeRules,
    excludeRules,
    wcagTags,
    selector,
    excludeSelectors,
    minSeverity,
    axeOptions,
  } = options;

  // Build axe configuration
  let builder = new AxeBuilder({ page });

  // Apply rule filters
  if (includeRules && includeRules.length > 0) {
    builder = builder.withRules(includeRules);
  }

  if (excludeRules && excludeRules.length > 0) {
    builder = builder.disableRules(excludeRules);
  }

  // Apply WCAG tag filters
  if (wcagTags && wcagTags.length > 0) {
    builder = builder.withTags(wcagTags);
  }

  // Apply selector scope
  if (selector) {
    builder = builder.include(selector);
  }

  // Apply exclusions
  if (excludeSelectors && excludeSelectors.length > 0) {
    for (const excludeSelector of excludeSelectors) {
      builder = builder.exclude(excludeSelector);
    }
  }

  // Apply custom options
  if (axeOptions) {
    builder = builder.options(axeOptions);
  }

  // Run the audit
  const axeResults = await builder.analyze();

  // Transform results to our interface
  const violations = axeResults.violations.map(v => ({
    id: v.id,
    impact: v.impact as ViolationSeverity | undefined,
    description: v.description,
    help: v.help,
    helpUrl: v.helpUrl,
    tags: v.tags,
    nodes: v.nodes.map(n => ({
      html: n.html,
      target: n.target as string[],
      failureSummary: n.failureSummary,
      impact: n.impact as ViolationSeverity | undefined,
    })),
  }));

  // Filter by minimum severity if specified
  const filteredViolations = minSeverity
    ? filterViolationsBySeverity(violations, minSeverity)
    : violations;

  return {
    violations: filteredViolations,
    passes: axeResults.passes.map(p => ({
      id: p.id,
      description: p.description,
    })),
    incomplete: axeResults.incomplete.map(i => ({
      id: i.id,
      description: i.description,
      nodes: i.nodes.map(n => ({
        html: n.html,
        target: n.target as string[],
        failureSummary: n.failureSummary,
        impact: n.impact as ViolationSeverity | undefined,
      })),
    })),
    inapplicable: axeResults.inapplicable.map(i => ({
      id: i.id,
      description: i.description,
    })),
    timestamp: new Date().toISOString(),
    url: page.url(),
    summary: {
      violations: filteredViolations.length,
      passes: axeResults.passes.length,
      incomplete: axeResults.incomplete.length,
      inapplicable: axeResults.inapplicable.length,
    },
  };
}

/**
 * Run a quick accessibility audit focused on critical issues.
 * This is faster than a full audit and useful for smoke tests.
 *
 * @param page - Playwright Page object
 * @returns Promise resolving to critical/serious violations only
 */
export async function runQuickAccessibilityAudit(
  page: Page
): Promise<AccessibilityViolation[]> {
  const results = await runAccessibilityAudit(page, {
    minSeverity: 'serious',
  });
  return results.violations;
}

/**
 * Run a WCAG 2.1 Level AA compliance audit.
 *
 * @param page - Playwright Page object
 * @param options - Additional options
 * @returns Promise resolving to audit results
 */
export async function runWcag21AAAudit(
  page: Page,
  options: Omit<AccessibilityAuditOptions, 'wcagTags'> = {}
): Promise<AccessibilityAuditResult> {
  return runAccessibilityAudit(page, {
    ...options,
    wcagTags: ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'],
  });
}

/**
 * Audit a specific element on the page.
 *
 * @param page - Playwright Page object
 * @param locator - Playwright Locator for the element
 * @param options - Audit options
 * @returns Promise resolving to audit results
 *
 * @example
 * ```ts
 * const modal = page.locator('[role="dialog"]');
 * const results = await auditElement(page, modal);
 * ```
 */
export async function auditElement(
  page: Page,
  locator: Locator,
  options: Omit<AccessibilityAuditOptions, 'selector'> = {}
): Promise<AccessibilityAuditResult> {
  // Get the selector from the locator
  const selector = await locator.evaluate(el => {
    // Build a unique selector for the element
    if (el.id) return `#${el.id}`;
    if (el.getAttribute('data-testid')) {
      return `[data-testid="${el.getAttribute('data-testid')}"]`;
    }
    // Fallback to tag with index
    const tagName = el.tagName.toLowerCase();
    const siblings = el.parentElement?.children || [];
    const index = Array.from(siblings).indexOf(el);
    return `${tagName}:nth-child(${index + 1})`;
  });

  return runAccessibilityAudit(page, {
    ...options,
    selector,
  });
}

// =============================================================================
// Violation Filtering Functions
// =============================================================================

/**
 * Filter violations by minimum severity level.
 *
 * @param violations - Array of violations to filter
 * @param minSeverity - Minimum severity to include
 * @returns Filtered violations with severity >= minSeverity
 *
 * @example
 * ```ts
 * // Get only critical and serious violations
 * const severeIssues = filterViolationsBySeverity(violations, 'serious');
 * ```
 */
export function filterViolationsBySeverity(
  violations: AccessibilityViolation[],
  minSeverity: ViolationSeverity
): AccessibilityViolation[] {
  const minLevel = SEVERITY_ORDER[minSeverity];
  return violations.filter(v => {
    const violationLevel = v.impact ? SEVERITY_ORDER[v.impact] : 0;
    return violationLevel >= minLevel;
  });
}

/**
 * Filter violations by WCAG tags.
 *
 * @param violations - Array of violations to filter
 * @param tags - WCAG tags to include (e.g., 'wcag2a', 'wcag21aa')
 * @returns Violations matching any of the specified tags
 */
export function filterViolationsByTags(
  violations: AccessibilityViolation[],
  tags: string[]
): AccessibilityViolation[] {
  return violations.filter(v =>
    v.tags.some(tag => tags.includes(tag))
  );
}

/**
 * Filter violations by rule IDs.
 *
 * @param violations - Array of violations to filter
 * @param ruleIds - Rule IDs to include
 * @returns Violations matching any of the specified rule IDs
 */
export function filterViolationsByRules(
  violations: AccessibilityViolation[],
  ruleIds: string[]
): AccessibilityViolation[] {
  return violations.filter(v => ruleIds.includes(v.id));
}

/**
 * Exclude violations by rule IDs.
 *
 * @param violations - Array of violations to filter
 * @param ruleIds - Rule IDs to exclude
 * @returns Violations NOT matching any of the specified rule IDs
 */
export function excludeViolationsByRules(
  violations: AccessibilityViolation[],
  ruleIds: string[]
): AccessibilityViolation[] {
  return violations.filter(v => !ruleIds.includes(v.id));
}

/**
 * Group violations by their impact severity.
 *
 * @param violations - Array of violations to group
 * @returns Object with violations grouped by severity
 */
export function groupViolationsBySeverity(
  violations: AccessibilityViolation[]
): Record<ViolationSeverity, AccessibilityViolation[]> {
  const grouped: Record<ViolationSeverity, AccessibilityViolation[]> = {
    critical: [],
    serious: [],
    moderate: [],
    minor: [],
  };

  for (const violation of violations) {
    const severity = violation.impact || 'minor';
    grouped[severity].push(violation);
  }

  return grouped;
}

/**
 * Sort violations by severity (most severe first).
 *
 * @param violations - Array of violations to sort
 * @returns Sorted violations array
 */
export function sortViolationsBySeverity(
  violations: AccessibilityViolation[]
): AccessibilityViolation[] {
  return [...violations].sort((a, b) => {
    const aLevel = a.impact ? SEVERITY_ORDER[a.impact] : 0;
    const bLevel = b.impact ? SEVERITY_ORDER[b.impact] : 0;
    return bLevel - aLevel;
  });
}

/**
 * Get count of violations by severity.
 *
 * @param violations - Array of violations to count
 * @returns Object with counts by severity level
 */
export function getViolationCounts(
  violations: AccessibilityViolation[]
): Record<ViolationSeverity, number> {
  const counts: Record<ViolationSeverity, number> = {
    critical: 0,
    serious: 0,
    moderate: 0,
    minor: 0,
  };

  for (const violation of violations) {
    const severity = violation.impact || 'minor';
    counts[severity]++;
  }

  return counts;
}

/**
 * Get total affected element count across all violations.
 *
 * @param violations - Array of violations
 * @returns Total number of affected elements
 */
export function getTotalAffectedElements(
  violations: AccessibilityViolation[]
): number {
  return violations.reduce((total, v) => total + v.nodes.length, 0);
}

// =============================================================================
// Report Generation Functions
// =============================================================================

/**
 * Generate a human-readable accessibility report.
 *
 * @param results - Accessibility audit results
 * @param options - Report options
 * @returns Formatted report string
 *
 * @example
 * ```ts
 * const results = await runAccessibilityAudit(page);
 * const report = generateAccessibilityReport(results);
 * console.log(report);
 * ```
 */
export function generateAccessibilityReport(
  results: AccessibilityAuditResult,
  options: AccessibilityReportOptions = {}
): string {
  const {
    includePasses = false,
    includeIncomplete = true,
    includeInapplicable = false,
    format = 'text',
    includeRemediation = true,
    groupBy = 'impact',
  } = options;

  switch (format) {
    case 'json':
      return generateJsonReport(results, options);
    case 'markdown':
      return generateMarkdownReport(results, options);
    default:
      return generateTextReport(results, options);
  }
}

/**
 * Generate a JSON report.
 */
function generateJsonReport(
  results: AccessibilityAuditResult,
  options: AccessibilityReportOptions
): string {
  const { includePasses, includeIncomplete, includeInapplicable } = options;

  const report: Record<string, unknown> = {
    timestamp: results.timestamp,
    url: results.url,
    summary: results.summary,
    violations: results.violations,
  };

  if (includePasses) {
    report.passes = results.passes;
  }
  if (includeIncomplete) {
    report.incomplete = results.incomplete;
  }
  if (includeInapplicable) {
    report.inapplicable = results.inapplicable;
  }

  return JSON.stringify(report, null, 2);
}

/**
 * Generate a text report.
 */
function generateTextReport(
  results: AccessibilityAuditResult,
  options: AccessibilityReportOptions
): string {
  const {
    includePasses,
    includeIncomplete,
    includeRemediation,
    groupBy,
  } = options;

  const lines: string[] = [];

  // Header
  lines.push('='.repeat(80));
  lines.push('ACCESSIBILITY AUDIT REPORT');
  lines.push('='.repeat(80));
  lines.push(`URL: ${results.url}`);
  lines.push(`Timestamp: ${results.timestamp}`);
  lines.push('');

  // Summary
  lines.push('SUMMARY');
  lines.push('-'.repeat(40));
  lines.push(`Violations: ${results.summary.violations}`);
  lines.push(`Passes: ${results.summary.passes}`);
  lines.push(`Incomplete: ${results.summary.incomplete}`);
  lines.push(`Inapplicable: ${results.summary.inapplicable}`);
  lines.push('');

  // Violations
  if (results.violations.length > 0) {
    lines.push('VIOLATIONS');
    lines.push('-'.repeat(40));

    const sortedViolations = sortViolationsBySeverity(results.violations);

    if (groupBy === 'impact') {
      const grouped = groupViolationsBySeverity(sortedViolations);

      for (const severity of ['critical', 'serious', 'moderate', 'minor'] as ViolationSeverity[]) {
        const violations = grouped[severity];
        if (violations.length > 0) {
          lines.push(`\n[${severity.toUpperCase()}]`);
          for (const v of violations) {
            lines.push(...formatViolationText(v, includeRemediation));
          }
        }
      }
    } else {
      for (const v of sortedViolations) {
        lines.push(...formatViolationText(v, includeRemediation));
      }
    }
  } else {
    lines.push('No accessibility violations found!');
  }

  // Incomplete (needs manual review)
  if (includeIncomplete && results.incomplete.length > 0) {
    lines.push('');
    lines.push('NEEDS MANUAL REVIEW');
    lines.push('-'.repeat(40));

    for (const item of results.incomplete) {
      lines.push(`- ${item.id}: ${item.description}`);
      lines.push(`  Affected elements: ${item.nodes.length}`);
    }
  }

  // Passes
  if (includePasses && results.passes.length > 0) {
    lines.push('');
    lines.push('PASSED RULES');
    lines.push('-'.repeat(40));

    for (const item of results.passes) {
      lines.push(`- ${item.id}: ${item.description}`);
    }
  }

  return lines.join('\n');
}

/**
 * Format a single violation for text report.
 */
function formatViolationText(
  violation: AccessibilityViolation,
  includeRemediation?: boolean
): string[] {
  const lines: string[] = [];

  lines.push(`\n  Rule: ${violation.id}`);
  lines.push(`  Impact: ${violation.impact || 'unknown'}`);
  lines.push(`  Description: ${violation.description}`);

  if (includeRemediation) {
    lines.push(`  Help: ${violation.help}`);
    lines.push(`  Learn more: ${violation.helpUrl}`);
  }

  lines.push(`  Affected elements (${violation.nodes.length}):`);

  for (const node of violation.nodes.slice(0, 5)) {
    lines.push(`    - ${node.target.join(' > ')}`);
    if (node.failureSummary) {
      lines.push(`      ${node.failureSummary}`);
    }
  }

  if (violation.nodes.length > 5) {
    lines.push(`    ... and ${violation.nodes.length - 5} more`);
  }

  return lines;
}

/**
 * Generate a Markdown report.
 */
function generateMarkdownReport(
  results: AccessibilityAuditResult,
  options: AccessibilityReportOptions
): string {
  const {
    includePasses,
    includeIncomplete,
    includeRemediation,
  } = options;

  const lines: string[] = [];

  // Header
  lines.push('# Accessibility Audit Report');
  lines.push('');
  lines.push(`**URL:** ${results.url}`);
  lines.push(`**Timestamp:** ${results.timestamp}`);
  lines.push('');

  // Summary
  lines.push('## Summary');
  lines.push('');
  lines.push('| Category | Count |');
  lines.push('|----------|-------|');
  lines.push(`| Violations | ${results.summary.violations} |`);
  lines.push(`| Passes | ${results.summary.passes} |`);
  lines.push(`| Incomplete | ${results.summary.incomplete} |`);
  lines.push(`| Inapplicable | ${results.summary.inapplicable} |`);
  lines.push('');

  // Violations
  if (results.violations.length > 0) {
    lines.push('## Violations');
    lines.push('');

    const sortedViolations = sortViolationsBySeverity(results.violations);
    const grouped = groupViolationsBySeverity(sortedViolations);

    for (const severity of ['critical', 'serious', 'moderate', 'minor'] as ViolationSeverity[]) {
      const violations = grouped[severity];
      if (violations.length > 0) {
        const emoji = getSeverityEmoji(severity);
        lines.push(`### ${emoji} ${capitalizeFirst(severity)} (${violations.length})`);
        lines.push('');

        for (const v of violations) {
          lines.push(`#### ${v.id}`);
          lines.push('');
          lines.push(`> ${v.description}`);
          lines.push('');

          if (includeRemediation) {
            lines.push(`**Fix:** ${v.help}`);
            lines.push('');
            lines.push(`[Learn more](${v.helpUrl})`);
            lines.push('');
          }

          lines.push('**Affected elements:**');
          lines.push('');

          for (const node of v.nodes.slice(0, 5)) {
            lines.push(`- \`${node.target.join(' > ')}\``);
          }

          if (v.nodes.length > 5) {
            lines.push(`- ... and ${v.nodes.length - 5} more`);
          }

          lines.push('');
        }
      }
    }
  } else {
    lines.push('## Violations');
    lines.push('');
    lines.push('No accessibility violations found!');
    lines.push('');
  }

  // Incomplete
  if (includeIncomplete && results.incomplete.length > 0) {
    lines.push('## Needs Manual Review');
    lines.push('');

    for (const item of results.incomplete) {
      lines.push(`- **${item.id}**: ${item.description} (${item.nodes.length} elements)`);
    }

    lines.push('');
  }

  // Passes
  if (includePasses && results.passes.length > 0) {
    lines.push('## Passed Rules');
    lines.push('');

    for (const item of results.passes) {
      lines.push(`- ${item.id}: ${item.description}`);
    }

    lines.push('');
  }

  return lines.join('\n');
}

/**
 * Get emoji for severity level.
 */
function getSeverityEmoji(severity: ViolationSeverity): string {
  switch (severity) {
    case 'critical':
      return '\u274C'; // Red X
    case 'serious':
      return '\u26A0\uFE0F'; // Warning
    case 'moderate':
      return '\u2139\uFE0F'; // Info
    case 'minor':
      return '\u2022'; // Bullet
  }
}

/**
 * Capitalize first letter.
 */
function capitalizeFirst(str: string): string {
  return str.charAt(0).toUpperCase() + str.slice(1);
}

// =============================================================================
// Assertion Helpers
// =============================================================================

/**
 * Assert that a page has no critical accessibility violations.
 *
 * @param page - Playwright Page object
 * @param options - Audit options
 * @throws Error if critical violations are found
 *
 * @example
 * ```ts
 * await assertNoCriticalViolations(page);
 * ```
 */
export async function assertNoCriticalViolations(
  page: Page,
  options: Omit<AccessibilityAuditOptions, 'minSeverity'> = {}
): Promise<void> {
  const results = await runAccessibilityAudit(page, {
    ...options,
    minSeverity: 'critical',
  });

  if (results.violations.length > 0) {
    const report = generateAccessibilityReport(results, { format: 'text' });
    throw new Error(
      `Found ${results.violations.length} critical accessibility violation(s):\n\n${report}`
    );
  }
}

/**
 * Assert that a page has no accessibility violations at or above a severity level.
 *
 * @param page - Playwright Page object
 * @param minSeverity - Minimum severity to fail on
 * @param options - Audit options
 * @throws Error if violations are found
 */
export async function assertNoViolationsAboveSeverity(
  page: Page,
  minSeverity: ViolationSeverity,
  options: Omit<AccessibilityAuditOptions, 'minSeverity'> = {}
): Promise<void> {
  const results = await runAccessibilityAudit(page, {
    ...options,
    minSeverity,
  });

  if (results.violations.length > 0) {
    const report = generateAccessibilityReport(results, { format: 'text' });
    throw new Error(
      `Found ${results.violations.length} accessibility violation(s) with severity >= ${minSeverity}:\n\n${report}`
    );
  }
}

/**
 * Assert page passes WCAG 2.1 Level AA.
 *
 * @param page - Playwright Page object
 * @param options - Additional options
 * @throws Error if WCAG 2.1 AA violations are found
 */
export async function assertWcag21AACompliant(
  page: Page,
  options: Omit<AccessibilityAuditOptions, 'wcagTags'> = {}
): Promise<void> {
  const results = await runWcag21AAAudit(page, options);

  if (results.violations.length > 0) {
    const report = generateAccessibilityReport(results, { format: 'text' });
    throw new Error(
      `Page does not meet WCAG 2.1 Level AA. Found ${results.violations.length} violation(s):\n\n${report}`
    );
  }
}

// =============================================================================
// Accessibility Helper Class
// =============================================================================

/**
 * Accessibility helper class for comprehensive a11y testing.
 * Provides a fluent interface for accessibility operations.
 *
 * @example
 * ```ts
 * const a11y = new AccessibilityHelper(page);
 *
 * // Run full audit
 * const results = await a11y.audit();
 *
 * // Check specific element
 * const dialog = page.locator('[role="dialog"]');
 * const dialogResults = await a11y.auditElement(dialog);
 *
 * // Assert no critical issues
 * await a11y.assertNoCriticalIssues();
 *
 * // Generate report
 * const report = a11y.generateReport(results);
 * ```
 */
export class AccessibilityHelper {
  private page: Page;
  private lastResults: AccessibilityAuditResult | null = null;

  constructor(page: Page) {
    this.page = page;
  }

  /**
   * Run a full accessibility audit.
   */
  async audit(options?: AccessibilityAuditOptions): Promise<AccessibilityAuditResult> {
    this.lastResults = await runAccessibilityAudit(this.page, options);
    return this.lastResults;
  }

  /**
   * Run a quick audit for critical/serious issues only.
   */
  async quickAudit(): Promise<AccessibilityViolation[]> {
    const results = await runAccessibilityAudit(this.page, {
      minSeverity: 'serious',
    });
    this.lastResults = results;
    return results.violations;
  }

  /**
   * Audit for WCAG 2.1 AA compliance.
   */
  async wcag21AAAudit(
    options?: Omit<AccessibilityAuditOptions, 'wcagTags'>
  ): Promise<AccessibilityAuditResult> {
    this.lastResults = await runWcag21AAAudit(this.page, options);
    return this.lastResults;
  }

  /**
   * Audit a specific element.
   */
  async auditElement(
    locator: Locator,
    options?: Omit<AccessibilityAuditOptions, 'selector'>
  ): Promise<AccessibilityAuditResult> {
    this.lastResults = await auditElement(this.page, locator, options);
    return this.lastResults;
  }

  /**
   * Get the last audit results.
   */
  getLastResults(): AccessibilityAuditResult | null {
    return this.lastResults;
  }

  /**
   * Get violations from the last audit.
   */
  getViolations(minSeverity?: ViolationSeverity): AccessibilityViolation[] {
    if (!this.lastResults) return [];

    return minSeverity
      ? filterViolationsBySeverity(this.lastResults.violations, minSeverity)
      : this.lastResults.violations;
  }

  /**
   * Get violation counts by severity.
   */
  getViolationCounts(): Record<ViolationSeverity, number> | null {
    if (!this.lastResults) return null;
    return getViolationCounts(this.lastResults.violations);
  }

  /**
   * Check if page has any violations.
   */
  hasViolations(minSeverity?: ViolationSeverity): boolean {
    return this.getViolations(minSeverity).length > 0;
  }

  /**
   * Assert no critical violations.
   */
  async assertNoCriticalIssues(
    options?: Omit<AccessibilityAuditOptions, 'minSeverity'>
  ): Promise<this> {
    await assertNoCriticalViolations(this.page, options);
    return this;
  }

  /**
   * Assert no violations at or above severity.
   */
  async assertNoIssuesAbove(
    minSeverity: ViolationSeverity,
    options?: Omit<AccessibilityAuditOptions, 'minSeverity'>
  ): Promise<this> {
    await assertNoViolationsAboveSeverity(this.page, minSeverity, options);
    return this;
  }

  /**
   * Assert WCAG 2.1 AA compliance.
   */
  async assertWcag21AA(
    options?: Omit<AccessibilityAuditOptions, 'wcagTags'>
  ): Promise<this> {
    await assertWcag21AACompliant(this.page, options);
    return this;
  }

  /**
   * Generate a report from the last audit.
   */
  generateReport(
    results?: AccessibilityAuditResult,
    options?: AccessibilityReportOptions
  ): string {
    const targetResults = results || this.lastResults;
    if (!targetResults) {
      throw new Error('No audit results available. Run audit() first.');
    }
    return generateAccessibilityReport(targetResults, options);
  }

  /**
   * Generate a Markdown report.
   */
  generateMarkdownReport(results?: AccessibilityAuditResult): string {
    return this.generateReport(results, { format: 'markdown' });
  }

  /**
   * Generate a JSON report.
   */
  generateJsonReport(results?: AccessibilityAuditResult): string {
    return this.generateReport(results, { format: 'json' });
  }
}

// =============================================================================
// Common Rule Sets
// =============================================================================

/**
 * Common accessibility rule sets for different testing scenarios.
 */
export const ACCESSIBILITY_RULE_SETS = {
  /** Keyboard navigation rules */
  keyboard: [
    'focus-order-semantics',
    'tabindex',
    'accesskeys',
    'bypass',
    'focus-visible',
  ],

  /** Color and contrast rules */
  color: [
    'color-contrast',
    'color-contrast-enhanced',
    'link-in-text-block',
  ],

  /** Form input rules */
  forms: [
    'autocomplete-valid',
    'form-field-multiple-labels',
    'input-button-name',
    'input-image-alt',
    'label',
    'label-title-only',
    'select-name',
  ],

  /** Interactive element rules */
  interactive: [
    'button-name',
    'link-name',
    'aria-input-field-name',
    'aria-toggle-field-name',
  ],

  /** Image and media rules */
  media: [
    'image-alt',
    'image-redundant-alt',
    'object-alt',
    'svg-img-alt',
    'video-caption',
    'audio-caption',
  ],

  /** Document structure rules */
  structure: [
    'document-title',
    'heading-order',
    'landmark-banner-is-top-level',
    'landmark-contentinfo-is-top-level',
    'landmark-main-is-top-level',
    'landmark-no-duplicate-banner',
    'landmark-no-duplicate-contentinfo',
    'landmark-one-main',
    'page-has-heading-one',
    'region',
  ],

  /** ARIA usage rules */
  aria: [
    'aria-allowed-attr',
    'aria-allowed-role',
    'aria-hidden-body',
    'aria-hidden-focus',
    'aria-required-attr',
    'aria-required-children',
    'aria-required-parent',
    'aria-roles',
    'aria-valid-attr',
    'aria-valid-attr-value',
  ],
};

/**
 * Export severity order for external use.
 */
export { SEVERITY_ORDER };
