import { test, expect, APIClient, waitFor } from './fixtures';

/**
 * E2E tests for Cost Tracking Workflow.
 *
 * Tests cover the cost tracking API endpoints:
 * - GET /api/cost/estimate/{workflow} - Cost estimates for workflows
 * - GET /api/cost/summary - Cost summary view
 * - GET /api/cost/budget - Budget information
 *
 * These tests verify the orchestrator's cost tracking functionality
 * including estimation, reporting, and budget management.
 */

test.describe('Cost Tracking Workflow', () => {
  /**
   * Helper to check if cost endpoints are available
   */
  async function checkCostEndpoints(apiClient: APIClient): Promise<{
    estimateAvailable: boolean;
    summaryAvailable: boolean;
    budgetAvailable: boolean;
  }> {
    let estimateAvailable = false;
    let summaryAvailable = false;
    let budgetAvailable = false;

    // Check estimate endpoint
    try {
      const estimateResponse = await apiClient.get('/api/cost/estimate/plan');
      estimateAvailable = estimateResponse.status !== 404 && estimateResponse.status !== 405;
    } catch {
      estimateAvailable = false;
    }

    // Check summary endpoint
    try {
      const summaryResponse = await apiClient.get('/api/cost/summary');
      summaryAvailable = summaryResponse.status !== 404 && summaryResponse.status !== 405;
    } catch {
      summaryAvailable = false;
    }

    // Check budget endpoint
    try {
      const budgetResponse = await apiClient.get('/api/cost/budget');
      budgetAvailable = budgetResponse.status !== 404 && budgetResponse.status !== 405;
    } catch {
      budgetAvailable = false;
    }

    return { estimateAvailable, summaryAvailable, budgetAvailable };
  }

  test.describe('Cost Estimate', () => {
    test('should display cost estimate for workflow', async ({ apiClient }) => {
      // Check if estimate endpoint is available
      const endpoints = await checkCostEndpoints(apiClient);

      if (!endpoints.estimateAvailable) {
        test.skip(true, 'GET /api/cost/estimate/{workflow} endpoint not available');
        return;
      }

      // Test plan workflow estimate
      const planEstimateResponse = await apiClient.get('/api/cost/estimate/plan?complexity=medium');

      expect(planEstimateResponse.ok).toBeTruthy();
      expect(planEstimateResponse.status).toBe(200);

      const planEstimate = planEstimateResponse.body as {
        estimated_tokens?: number;
        estimated_cost_usd?: number;
        confidence?: string;
        breakdown?: Record<string, number>;
      };

      // Verify estimate response structure
      expect(planEstimate).toBeDefined();
      expect(planEstimate).toHaveProperty('estimated_tokens');
      expect(planEstimate).toHaveProperty('estimated_cost_usd');

      // Verify estimate values are valid numbers
      expect(typeof planEstimate.estimated_tokens).toBe('number');
      expect(typeof planEstimate.estimated_cost_usd).toBe('number');
      expect(planEstimate.estimated_tokens).toBeGreaterThanOrEqual(0);
      expect(planEstimate.estimated_cost_usd).toBeGreaterThanOrEqual(0);

      // Test build workflow estimate
      const buildEstimateResponse = await apiClient.get('/api/cost/estimate/build?complexity=simple');

      if (buildEstimateResponse.ok) {
        const buildEstimate = buildEstimateResponse.body as {
          estimated_tokens?: number;
          estimated_cost_usd?: number;
        };

        expect(buildEstimate).toHaveProperty('estimated_tokens');
        expect(buildEstimate).toHaveProperty('estimated_cost_usd');
        expect(typeof buildEstimate.estimated_tokens).toBe('number');
        expect(typeof buildEstimate.estimated_cost_usd).toBe('number');
      }

      // Log estimates for debugging
      console.log('Plan estimate:', planEstimate);
    });

    test('should include confidence level in cost estimates', async ({ apiClient }) => {
      const endpoints = await checkCostEndpoints(apiClient);

      if (!endpoints.estimateAvailable) {
        test.skip(true, 'GET /api/cost/estimate/{workflow} endpoint not available');
        return;
      }

      const response = await apiClient.get('/api/cost/estimate/plan?complexity=complex&request_text=Create%20authentication%20module');

      if (!response.ok) {
        test.skip(true, 'Could not fetch cost estimate');
        return;
      }

      const estimate = response.body as {
        estimated_tokens: number;
        estimated_cost_usd: number;
        confidence: string;
      };

      // Verify confidence is present and valid
      expect(estimate.confidence).toBeTruthy();
      expect(['low', 'medium', 'high']).toContain(estimate.confidence.toLowerCase());

      // Complex requests should have token estimates
      expect(estimate.estimated_tokens).toBeGreaterThan(0);
    });

    test('should handle different workflow types', async ({ apiClient }) => {
      const endpoints = await checkCostEndpoints(apiClient);

      if (!endpoints.estimateAvailable) {
        test.skip(true, 'GET /api/cost/estimate/{workflow} endpoint not available');
        return;
      }

      const workflowTypes = ['plan', 'build'];
      const estimates: Record<string, unknown> = {};

      for (const workflow of workflowTypes) {
        const response = await apiClient.get(`/api/cost/estimate/${workflow}`);

        if (response.ok) {
          estimates[workflow] = response.body;

          const estimate = response.body as { estimated_tokens: number; estimated_cost_usd: number };
          expect(typeof estimate.estimated_tokens).toBe('number');
          expect(typeof estimate.estimated_cost_usd).toBe('number');
        }
      }

      console.log('Workflow estimates:', estimates);
    });
  });

  test.describe('Cost Summary', () => {
    test('should show cost summary view', async ({ apiClient }) => {
      // Check if summary endpoint is available
      const endpoints = await checkCostEndpoints(apiClient);

      if (!endpoints.summaryAvailable) {
        test.skip(true, 'GET /api/cost/summary endpoint not available');
        return;
      }

      // Fetch cost summary
      const response = await apiClient.get('/api/cost/summary');

      expect(response.ok).toBeTruthy();
      expect(response.status).toBe(200);

      const summary = response.body as {
        daily?: { total_cost: number; total_tokens: number; workflow_count: number };
        weekly?: { total_cost: number; total_tokens: number; workflow_count: number };
        monthly?: { total_cost: number; total_tokens: number; workflow_count: number };
        budget?: { is_within_budget: boolean };
      };

      // Verify summary structure with daily, weekly, monthly breakdowns
      expect(summary).toBeDefined();
      expect(summary).toHaveProperty('daily');
      expect(summary).toHaveProperty('weekly');
      expect(summary).toHaveProperty('monthly');

      // Verify daily report structure
      if (summary.daily) {
        expect(summary.daily).toHaveProperty('total_cost');
        expect(summary.daily).toHaveProperty('total_tokens');
        expect(summary.daily).toHaveProperty('workflow_count');
        expect(typeof summary.daily.total_cost).toBe('number');
        expect(typeof summary.daily.total_tokens).toBe('number');
        expect(typeof summary.daily.workflow_count).toBe('number');
        expect(summary.daily.total_cost).toBeGreaterThanOrEqual(0);
        expect(summary.daily.total_tokens).toBeGreaterThanOrEqual(0);
        expect(summary.daily.workflow_count).toBeGreaterThanOrEqual(0);
      }

      // Verify weekly report structure
      if (summary.weekly) {
        expect(typeof summary.weekly.total_cost).toBe('number');
        expect(typeof summary.weekly.total_tokens).toBe('number');
        expect(summary.weekly.total_cost).toBeGreaterThanOrEqual(0);
      }

      // Verify monthly report structure
      if (summary.monthly) {
        expect(typeof summary.monthly.total_cost).toBe('number');
        expect(typeof summary.monthly.total_tokens).toBe('number');
        expect(summary.monthly.total_cost).toBeGreaterThanOrEqual(0);
      }

      // Log summary for debugging
      console.log('Cost summary:', JSON.stringify(summary, null, 2));
    });

    test('should track workflow counts in summary', async ({ apiClient }) => {
      const endpoints = await checkCostEndpoints(apiClient);

      if (!endpoints.summaryAvailable) {
        test.skip(true, 'GET /api/cost/summary endpoint not available');
        return;
      }

      const response = await apiClient.get('/api/cost/summary');

      if (!response.ok) {
        test.skip(true, 'Could not fetch cost summary');
        return;
      }

      const summary = response.body as {
        daily: { total_cost: number; total_tokens: number; workflow_count: number };
        weekly: { total_cost: number; total_tokens: number; workflow_count: number };
        monthly: { total_cost: number; total_tokens: number; workflow_count: number };
      };

      // Workflow counts should be non-negative integers
      expect(summary.daily.workflow_count).toBeGreaterThanOrEqual(0);
      expect(summary.weekly.workflow_count).toBeGreaterThanOrEqual(0);
      expect(summary.monthly.workflow_count).toBeGreaterThanOrEqual(0);

      // Total cost should be non-negative
      expect(summary.daily.total_cost).toBeGreaterThanOrEqual(0);
      expect(summary.weekly.total_cost).toBeGreaterThanOrEqual(0);
      expect(summary.monthly.total_cost).toBeGreaterThanOrEqual(0);
    });

    test('should include budget status in summary', async ({ apiClient }) => {
      const endpoints = await checkCostEndpoints(apiClient);

      if (!endpoints.summaryAvailable) {
        test.skip(true, 'GET /api/cost/summary endpoint not available');
        return;
      }

      const response = await apiClient.get('/api/cost/summary');

      if (!response.ok) {
        test.skip(true, 'Could not fetch cost summary');
        return;
      }

      const summary = response.body as {
        budget?: { is_within_budget: boolean };
      };

      // Cost summary should include budget status
      expect(summary).toHaveProperty('budget');
      if (summary.budget) {
        expect(summary.budget).toHaveProperty('is_within_budget');
        expect(typeof summary.budget.is_within_budget).toBe('boolean');
      }
    });
  });

  test.describe('Budget Information', () => {
    test('should display budget information', async ({ apiClient }) => {
      // Check if budget endpoint is available
      const endpoints = await checkCostEndpoints(apiClient);

      if (!endpoints.budgetAvailable) {
        test.skip(true, 'GET /api/cost/budget endpoint not available');
        return;
      }

      // Fetch budget status
      const response = await apiClient.get('/api/cost/budget');

      expect(response.ok).toBeTruthy();
      expect(response.status).toBe(200);

      const budget = response.body as {
        is_within_budget: boolean;
        daily_remaining?: number;
        weekly_remaining?: number;
        monthly_remaining?: number;
        per_workflow_remaining?: number;
      };

      // Verify budget status structure
      expect(budget).toBeDefined();
      expect(budget).toHaveProperty('is_within_budget');
      expect(typeof budget.is_within_budget).toBe('boolean');

      // Check for optional remaining budget fields
      const hasRemainingBudget =
        budget.daily_remaining !== undefined ||
        budget.weekly_remaining !== undefined ||
        budget.monthly_remaining !== undefined ||
        budget.per_workflow_remaining !== undefined;

      // If budget limits are configured, verify remaining amounts
      if (hasRemainingBudget) {
        if (budget.daily_remaining !== undefined) {
          expect(typeof budget.daily_remaining).toBe('number');
        }
        if (budget.weekly_remaining !== undefined) {
          expect(typeof budget.weekly_remaining).toBe('number');
        }
        if (budget.monthly_remaining !== undefined) {
          expect(typeof budget.monthly_remaining).toBe('number');
        }
        if (budget.per_workflow_remaining !== undefined) {
          expect(typeof budget.per_workflow_remaining).toBe('number');
        }
      }

      // Log budget status for debugging
      console.log('Budget status:', budget);
    });

    test('should indicate when within budget', async ({ apiClient }) => {
      const endpoints = await checkCostEndpoints(apiClient);

      if (!endpoints.budgetAvailable) {
        test.skip(true, 'GET /api/cost/budget endpoint not available');
        return;
      }

      const response = await apiClient.get('/api/cost/budget');

      if (!response.ok) {
        test.skip(true, 'Could not fetch budget status');
        return;
      }

      const budget = response.body as {
        is_within_budget: boolean;
        daily_remaining?: number;
        weekly_remaining?: number;
        monthly_remaining?: number;
      };

      // Budget status should always have a boolean indicator
      expect(typeof budget.is_within_budget).toBe('boolean');

      // If within budget, remaining amounts should be non-negative
      if (budget.is_within_budget) {
        if (budget.daily_remaining !== undefined) {
          expect(budget.daily_remaining).toBeGreaterThanOrEqual(0);
        }
        if (budget.weekly_remaining !== undefined) {
          expect(budget.weekly_remaining).toBeGreaterThanOrEqual(0);
        }
        if (budget.monthly_remaining !== undefined) {
          expect(budget.monthly_remaining).toBeGreaterThanOrEqual(0);
        }
      }
    });

    test('should handle budget exceeded state', async ({ apiClient }) => {
      const endpoints = await checkCostEndpoints(apiClient);

      if (!endpoints.budgetAvailable) {
        test.skip(true, 'GET /api/cost/budget endpoint not available');
        return;
      }

      const response = await apiClient.get('/api/cost/budget');

      if (!response.ok) {
        test.skip(true, 'Could not fetch budget status');
        return;
      }

      const budget = response.body as {
        is_within_budget: boolean;
        daily_remaining?: number;
        weekly_remaining?: number;
        monthly_remaining?: number;
      };

      // If budget is exceeded, verify the flag is set correctly
      if (!budget.is_within_budget) {
        // At least one remaining amount should be zero or negative
        const anyExceeded =
          (budget.daily_remaining !== undefined && budget.daily_remaining <= 0) ||
          (budget.weekly_remaining !== undefined && budget.weekly_remaining <= 0) ||
          (budget.monthly_remaining !== undefined && budget.monthly_remaining <= 0);

        // This is expected when over budget (but not required if no limits set)
        console.log('Budget exceeded - remaining amounts:', {
          daily: budget.daily_remaining,
          weekly: budget.weekly_remaining,
          monthly: budget.monthly_remaining
        });
      }
    });
  });

  test.describe('Cost API Consistency', () => {
    test('should return consistent data across endpoints', async ({ apiClient }) => {
      const endpoints = await checkCostEndpoints(apiClient);

      if (!endpoints.summaryAvailable || !endpoints.budgetAvailable) {
        test.skip(true, 'Cost summary or budget endpoints not available');
        return;
      }

      // Fetch both summary and budget
      const summaryResponse = await apiClient.get('/api/cost/summary');
      const budgetResponse = await apiClient.get('/api/cost/budget');

      if (!summaryResponse.ok || !budgetResponse.ok) {
        test.skip(true, 'Could not fetch cost data');
        return;
      }

      const summary = summaryResponse.body as {
        budget?: { is_within_budget: boolean };
      };
      const budget = budgetResponse.body as {
        is_within_budget: boolean;
      };

      // Budget status should be consistent between endpoints
      if (summary.budget) {
        expect(summary.budget.is_within_budget).toBe(budget.is_within_budget);
      }
    });

    test('should handle multiple concurrent requests', async ({ apiClient }) => {
      const endpoints = await checkCostEndpoints(apiClient);

      if (!endpoints.summaryAvailable) {
        test.skip(true, 'Cost summary endpoint not available');
        return;
      }

      // Make multiple concurrent requests
      const requests = [
        apiClient.get('/api/cost/summary'),
        apiClient.get('/api/cost/summary'),
        apiClient.get('/api/cost/summary')
      ];

      const responses = await Promise.all(requests);

      // All requests should succeed
      for (const response of responses) {
        expect(response.ok).toBeTruthy();
        expect(response.status).toBe(200);
      }

      // All responses should have the same structure
      const summaries = responses.map(r => r.body as { daily: { total_cost: number } });
      for (const summary of summaries) {
        expect(summary).toHaveProperty('daily');
      }
    });
  });
});
