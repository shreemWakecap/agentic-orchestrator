import { test as base, expect, Page, APIRequestContext } from '@playwright/test';

/**
 * API Client for interacting with the orchestrator backend.
 * Provides typed methods for common API operations.
 */
export class APIClient {
  constructor(
    private request: APIRequestContext,
    private baseURL: string
  ) {}

  /**
   * Health check endpoint to verify server is running.
   */
  async healthCheck(): Promise<{ status: string; version: string; uptime_seconds: number }> {
    const response = await this.request.get(`${this.baseURL}/api/health`);
    expect(response.ok()).toBeTruthy();
    return response.json();
  }

  /**
   * Get list of all plans.
   */
  async getPlans(): Promise<{ plans: Plan[] }> {
    const response = await this.request.get(`${this.baseURL}/api/plans`);
    expect(response.ok()).toBeTruthy();
    return response.json();
  }

  /**
   * Get a specific plan by ID.
   */
  async getPlan(planId: string): Promise<Plan> {
    const response = await this.request.get(`${this.baseURL}/api/plans/${planId}`);
    expect(response.ok()).toBeTruthy();
    return response.json();
  }

  /**
   * Get a specific file from a plan.
   */
  async getPlanFile(planId: string, filename: string): Promise<PlanFile> {
    const response = await this.request.get(`${this.baseURL}/api/plans/${planId}/files/${filename}`);
    expect(response.ok()).toBeTruthy();
    return response.json();
  }

  /**
   * Start a new planning workflow.
   */
  async createPlan(description: string): Promise<{ run_id: string; status: string }> {
    const response = await this.request.post(`${this.baseURL}/api/workflows/plan`, {
      data: { description }
    });
    expect(response.ok()).toBeTruthy();
    return response.json();
  }

  /**
   * Start a new build workflow.
   */
  async startBuild(planPath: string): Promise<{ run_id: string; status: string }> {
    const response = await this.request.post(`${this.baseURL}/api/workflows/build`, {
      data: { plan_path: planPath }
    });
    expect(response.ok()).toBeTruthy();
    return response.json();
  }

  /**
   * Get run status by ID.
   */
  async getRun(runId: string): Promise<Run> {
    const response = await this.request.get(`${this.baseURL}/api/runs/${runId}`);
    expect(response.ok()).toBeTruthy();
    return response.json();
  }

  /**
   * Get cost estimate for a workflow.
   */
  async getCostEstimate(
    workflow: 'plan' | 'build',
    options?: { requestText?: string; planPath?: string; complexity?: string }
  ): Promise<CostEstimate> {
    const params = new URLSearchParams();
    if (options?.requestText) params.set('request_text', options.requestText);
    if (options?.planPath) params.set('plan_path', options.planPath);
    if (options?.complexity) params.set('complexity', options.complexity);

    const url = `${this.baseURL}/api/cost/estimate/${workflow}?${params.toString()}`;
    const response = await this.request.get(url);
    expect(response.ok()).toBeTruthy();
    return response.json();
  }

  /**
   * Get cost summary.
   */
  async getCostSummary(): Promise<CostSummary> {
    const response = await this.request.get(`${this.baseURL}/api/cost/summary`);
    expect(response.ok()).toBeTruthy();
    return response.json();
  }

  /**
   * Get budget status.
   */
  async getBudget(): Promise<BudgetStatus> {
    const response = await this.request.get(`${this.baseURL}/api/cost/budget`);
    expect(response.ok()).toBeTruthy();
    return response.json();
  }

  /**
   * Make a raw GET request (for testing error cases).
   */
  async get(path: string): Promise<{ ok: boolean; status: number; body: unknown }> {
    const response = await this.request.get(`${this.baseURL}${path}`);
    let body: unknown;
    try {
      body = await response.json();
    } catch {
      body = await response.text();
    }
    return { ok: response.ok(), status: response.status(), body };
  }

  /**
   * Make a raw POST request (for testing error cases).
   */
  async post(path: string, data?: unknown): Promise<{ ok: boolean; status: number; body: unknown }> {
    const response = await this.request.post(`${this.baseURL}${path}`, { data });
    let body: unknown;
    try {
      body = await response.json();
    } catch {
      body = await response.text();
    }
    return { ok: response.ok(), status: response.status(), body };
  }
}

/**
 * Type definitions for API responses.
 */
export interface Plan {
  id: string;
  name: string;
  state: 'pending' | 'in-progress' | 'completed' | 'failed';
  file: string;
  files?: string[];
  modified: string;
  content?: string;
  request?: string;
  complexity?: string;
}

export interface PlanFile {
  plan_id: string;
  filename: string;
  content: string;
  state: string;
}

export interface Run {
  id: string;
  workflow: 'planning' | 'building' | 'syncing';
  status: 'pending' | 'running' | 'completed' | 'failed';
  started_at: string;
  completed_at?: string;
  progress: number;
  current_step?: string;
  events: RunEvent[];
  output_file?: string;
  error?: string;
  plan_path?: string;
  description?: string;
}

export interface RunEvent {
  type: string;
  timestamp: string;
  [key: string]: unknown;
}

export interface CostEstimate {
  estimated_tokens: number;
  estimated_cost_usd: number;
  confidence: string;
  breakdown?: Record<string, number>;
}

export interface CostSummary {
  daily: CostReport;
  weekly: CostReport;
  monthly: CostReport;
  budget: BudgetStatus;
}

export interface CostReport {
  total_cost: number;
  total_tokens: number;
  workflow_count: number;
  workflows?: Record<string, number>;
}

export interface BudgetStatus {
  daily_remaining?: number;
  weekly_remaining?: number;
  monthly_remaining?: number;
  per_workflow_remaining?: number;
  is_within_budget: boolean;
}

/**
 * Test data interface for tracking created resources.
 */
export interface TestData {
  plans: Plan[];
  runs: Run[];
  createdResources: string[];
}

/**
 * Extended test fixtures for E2E testing.
 */
export interface TestFixtures {
  /** API client for backend interactions */
  apiClient: APIClient;
  /** First available plan from the API (null if none exist) */
  testPlan: Plan | null;
  /** Test data tracking object */
  testData: TestData;
  /** Helper to ensure test data exists before running tests */
  ensureTestData: () => Promise<{ hasPlans: boolean; hasRuns: boolean }>;
}

/**
 * Extended Playwright test with custom fixtures.
 * Use this instead of the default `test` import for E2E tests that need
 * API access or test data setup.
 */
export const test = base.extend<TestFixtures>({
  /**
   * APIClient fixture - provides a typed client for API interactions.
   * Automatically uses the baseURL from playwright config.
   */
  apiClient: async ({ request }, use) => {
    const baseURL = process.env.BASE_URL || 'http://localhost:8000';
    const client = new APIClient(request, baseURL);

    // Verify server is running before tests
    try {
      await client.healthCheck();
    } catch (error) {
      throw new Error(
        `Server health check failed. Ensure the server is running at ${baseURL}. ` +
        `Error: ${error instanceof Error ? error.message : String(error)}`
      );
    }

    await use(client);
  },

  /**
   * testPlan fixture - fetches the first available plan.
   * Returns null if no plans exist (tests should handle this gracefully).
   */
  testPlan: async ({ apiClient }, use) => {
    let plan: Plan | null = null;

    try {
      const { plans } = await apiClient.getPlans();
      if (plans.length > 0) {
        // Get full plan details for the first plan
        plan = await apiClient.getPlan(plans[0].id);
      }
    } catch (error) {
      console.warn('Could not fetch test plan:', error);
    }

    await use(plan);
  },

  /**
   * testData fixture - tracks test resources for cleanup.
   */
  testData: async ({}, use) => {
    const data: TestData = {
      plans: [],
      runs: [],
      createdResources: []
    };

    await use(data);

    // Cleanup is handled by ensureTestData or manually by tests
    // No automatic cleanup to avoid affecting other tests
  },

  /**
   * ensureTestData fixture - verifies test data exists before tests.
   * Use this in beforeEach hooks to skip tests gracefully when no data exists.
   */
  ensureTestData: async ({ apiClient }, use) => {
    const ensureTestData = async () => {
      let hasPlans = false;
      let hasRuns = false;

      try {
        const { plans } = await apiClient.getPlans();
        hasPlans = plans.length > 0;
      } catch {
        hasPlans = false;
      }

      // Check for runs via API (if endpoint exists)
      // Note: runs are in-memory, so they may not persist between server restarts
      hasRuns = false; // Runs are typically created during test execution

      return { hasPlans, hasRuns };
    };

    await use(ensureTestData);
  }
});

/**
 * Re-export expect for convenience.
 */
export { expect };

/**
 * Helper function to wait for a condition with timeout.
 */
export async function waitFor<T>(
  fn: () => Promise<T>,
  options: { timeout?: number; interval?: number; message?: string } = {}
): Promise<T> {
  const { timeout = 10000, interval = 500, message = 'Condition not met' } = options;
  const startTime = Date.now();

  while (Date.now() - startTime < timeout) {
    try {
      const result = await fn();
      if (result) return result;
    } catch {
      // Continue waiting
    }
    await new Promise(resolve => setTimeout(resolve, interval));
  }

  throw new Error(`${message} (timeout: ${timeout}ms)`);
}

/**
 * Helper function to generate unique test identifiers.
 */
export function generateTestId(prefix: string = 'test'): string {
  const timestamp = Date.now().toString(36);
  const random = Math.random().toString(36).substring(2, 8);
  return `${prefix}-${timestamp}-${random}`;
}

/**
 * Helper to skip test if condition is not met.
 */
export function skipIf(condition: boolean, reason: string): void {
  if (condition) {
    test.skip(true, reason);
  }
}

/**
 * Page object helper for common page interactions.
 */
export class PageHelper {
  constructor(private page: Page) {}

  /**
   * Navigate to a page and wait for it to load.
   */
  async navigateTo(path: string): Promise<void> {
    await this.page.goto(path);
    await this.page.waitForLoadState('networkidle');
  }

  /**
   * Wait for page to be stable (no pending network requests).
   */
  async waitForStable(): Promise<void> {
    await this.page.waitForLoadState('networkidle');
  }

  /**
   * Get text content from an element, with fallback.
   */
  async getText(selector: string, fallback: string = ''): Promise<string> {
    try {
      const element = this.page.locator(selector).first();
      const isVisible = await element.isVisible();
      if (!isVisible) return fallback;
      return (await element.textContent()) || fallback;
    } catch {
      return fallback;
    }
  }

  /**
   * Check if an element exists and is visible.
   */
  async isVisible(selector: string): Promise<boolean> {
    try {
      const element = this.page.locator(selector).first();
      return await element.isVisible();
    } catch {
      return false;
    }
  }

  /**
   * Click an element if it exists.
   */
  async clickIfExists(selector: string): Promise<boolean> {
    try {
      const element = this.page.locator(selector).first();
      const isVisible = await element.isVisible();
      if (isVisible) {
        await element.click();
        return true;
      }
      return false;
    } catch {
      return false;
    }
  }
}
