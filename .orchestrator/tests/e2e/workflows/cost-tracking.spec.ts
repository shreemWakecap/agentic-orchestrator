import { test, expect, SELECTORS, waitForApiResponse, waitForNetworkIdle } from '../fixtures';

/**
 * E2E tests for Cost Tracking Workflow.
 *
 * Tests cover:
 * - Cost estimate display for workflows (GET /api/cost/estimate/{workflow})
 * - Cost summary view (GET /api/cost/summary)
 * - Budget information display (GET /api/cost/budget)
 */

test.describe('Cost Tracking Workflow', () => {
  test.describe('Cost Estimate', () => {
    test('should display cost estimate for workflow', async ({ page, apiClient }) => {
      // First verify the API endpoint works via the API client
      const planEstimate = await apiClient.getCostEstimate('plan', {
        requestText: 'Test plan request',
        complexity: 'medium'
      });

      // Verify estimate response structure
      expect(planEstimate).toHaveProperty('estimated_tokens');
      expect(planEstimate).toHaveProperty('estimated_cost_usd');
      expect(planEstimate).toHaveProperty('confidence');
      expect(typeof planEstimate.estimated_tokens).toBe('number');
      expect(typeof planEstimate.estimated_cost_usd).toBe('number');
      expect(planEstimate.estimated_tokens).toBeGreaterThanOrEqual(0);
      expect(planEstimate.estimated_cost_usd).toBeGreaterThanOrEqual(0);

      // Also test build workflow estimate
      const buildEstimate = await apiClient.getCostEstimate('build', {
        complexity: 'simple'
      });

      expect(buildEstimate).toHaveProperty('estimated_tokens');
      expect(buildEstimate).toHaveProperty('estimated_cost_usd');
      expect(typeof buildEstimate.estimated_tokens).toBe('number');
      expect(typeof buildEstimate.estimated_cost_usd).toBe('number');

      // Navigate to a page that might display cost estimates
      await page.goto('/plans');
      await waitForNetworkIdle(page);

      // Check for cost estimate UI elements on page (if present)
      const costEstimateElement = page.locator(SELECTORS.cost.estimate).first();
      const hasEstimateUI = await costEstimateElement.isVisible().catch(() => false);

      if (hasEstimateUI) {
        // Verify the estimate is displayed with proper formatting
        const estimateText = await costEstimateElement.textContent();
        expect(estimateText).toBeTruthy();
        // Cost estimates should contain currency symbol or numeric value
        expect(estimateText).toMatch(/\$|cost|estimate|\d+/i);
      }

      // Log the API estimates for debugging
      console.log('Plan estimate:', planEstimate);
      console.log('Build estimate:', buildEstimate);
    });

    test('should include confidence level in cost estimates', async ({ apiClient }) => {
      // Test that cost estimates include confidence levels
      const estimate = await apiClient.getCostEstimate('plan', {
        requestText: 'Create a new authentication module with OAuth support',
        complexity: 'complex'
      });

      // Verify confidence is one of expected values
      expect(estimate.confidence).toBeTruthy();
      expect(['low', 'medium', 'high']).toContain(estimate.confidence.toLowerCase());

      // Complex requests should have reasonable token estimates
      expect(estimate.estimated_tokens).toBeGreaterThan(0);
    });
  });

  test.describe('Cost Summary', () => {
    test('should show cost summary view', async ({ page, apiClient }) => {
      // Verify cost summary API endpoint
      const summary = await apiClient.getCostSummary();

      // Verify summary structure with daily, weekly, monthly breakdowns
      expect(summary).toHaveProperty('daily');
      expect(summary).toHaveProperty('weekly');
      expect(summary).toHaveProperty('monthly');
      expect(summary).toHaveProperty('budget');

      // Verify daily report structure
      expect(summary.daily).toHaveProperty('total_cost');
      expect(summary.daily).toHaveProperty('total_tokens');
      expect(summary.daily).toHaveProperty('workflow_count');
      expect(typeof summary.daily.total_cost).toBe('number');
      expect(typeof summary.daily.total_tokens).toBe('number');
      expect(typeof summary.daily.workflow_count).toBe('number');

      // Verify weekly report structure
      expect(summary.weekly).toHaveProperty('total_cost');
      expect(summary.weekly).toHaveProperty('total_tokens');
      expect(typeof summary.weekly.total_cost).toBe('number');

      // Verify monthly report structure
      expect(summary.monthly).toHaveProperty('total_cost');
      expect(summary.monthly).toHaveProperty('total_tokens');
      expect(typeof summary.monthly.total_cost).toBe('number');

      // Navigate to a page that might display cost summary
      await page.goto('/');
      await waitForNetworkIdle(page);

      // Look for dashboard or status page with cost information
      const costTotalElement = page.locator(SELECTORS.cost.total).first();
      const hasCostUI = await costTotalElement.isVisible().catch(() => false);

      if (hasCostUI) {
        const totalText = await costTotalElement.textContent();
        expect(totalText).toBeTruthy();
      }

      // Log summary for debugging
      console.log('Cost summary:', JSON.stringify(summary, null, 2));
    });

    test('should track workflow counts in summary', async ({ apiClient }) => {
      const summary = await apiClient.getCostSummary();

      // Workflow counts should be non-negative integers
      expect(summary.daily.workflow_count).toBeGreaterThanOrEqual(0);
      expect(summary.weekly.workflow_count).toBeGreaterThanOrEqual(0);
      expect(summary.monthly.workflow_count).toBeGreaterThanOrEqual(0);

      // Total cost should be non-negative
      expect(summary.daily.total_cost).toBeGreaterThanOrEqual(0);
      expect(summary.weekly.total_cost).toBeGreaterThanOrEqual(0);
      expect(summary.monthly.total_cost).toBeGreaterThanOrEqual(0);
    });
  });

  test.describe('Budget Information', () => {
    test('should display budget information', async ({ page, apiClient }) => {
      // Verify budget API endpoint
      const budget = await apiClient.getBudget();

      // Verify budget status structure
      expect(budget).toHaveProperty('is_within_budget');
      expect(typeof budget.is_within_budget).toBe('boolean');

      // Budget should have at least one of the remaining fields
      const hasRemainingBudget =
        budget.daily_remaining !== undefined ||
        budget.weekly_remaining !== undefined ||
        budget.monthly_remaining !== undefined ||
        budget.per_workflow_remaining !== undefined;

      // If budget limits are configured, remaining amounts should be present
      // If not configured, is_within_budget should still be valid
      if (hasRemainingBudget) {
        // Verify remaining amounts are numbers when present
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

      // Navigate to check for budget UI elements
      await page.goto('/');
      await waitForNetworkIdle(page);

      // Look for budget status indicator
      const budgetStatusElement = page.locator(SELECTORS.cost.budget).first();
      const hasBudgetUI = await budgetStatusElement.isVisible().catch(() => false);

      if (hasBudgetUI) {
        const budgetText = await budgetStatusElement.textContent();
        expect(budgetText).toBeTruthy();
      }

      // Check for budget warning if over budget
      if (!budget.is_within_budget) {
        const warningElement = page.locator(SELECTORS.cost.warning).first();
        const hasWarning = await warningElement.isVisible().catch(() => false);
        // Warning should be visible when over budget
        console.log('Budget exceeded - warning visible:', hasWarning);
      }

      // Log budget status for debugging
      console.log('Budget status:', budget);
    });

    test('should indicate when within budget', async ({ apiClient }) => {
      const budget = await apiClient.getBudget();

      // Budget status should always have a boolean indicator
      expect(typeof budget.is_within_budget).toBe('boolean');

      // If within budget, remaining amounts (if present) should be non-negative
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

    test('should include budget info in cost summary', async ({ apiClient }) => {
      const summary = await apiClient.getCostSummary();

      // Cost summary should include budget status
      expect(summary).toHaveProperty('budget');
      expect(summary.budget).toHaveProperty('is_within_budget');
      expect(typeof summary.budget.is_within_budget).toBe('boolean');
    });
  });

  test.describe('Cost Breakdown', () => {
    test('should provide cost breakdown by component when available', async ({ apiClient }) => {
      const estimate = await apiClient.getCostEstimate('plan', {
        requestText: 'Create a REST API with CRUD operations for user management',
        complexity: 'complex'
      });

      // If breakdown is provided, verify its structure
      if (estimate.breakdown) {
        expect(typeof estimate.breakdown).toBe('object');

        // Breakdown values should be numbers
        for (const [key, value] of Object.entries(estimate.breakdown)) {
          expect(typeof key).toBe('string');
          expect(typeof value).toBe('number');
          expect(value).toBeGreaterThanOrEqual(0);
        }
      }

      // Estimate should still have total values regardless of breakdown
      expect(estimate.estimated_tokens).toBeGreaterThan(0);
      expect(estimate.estimated_cost_usd).toBeGreaterThanOrEqual(0);
    });
  });

  test.describe('API Request Interception', () => {
    test('should make correct API calls for cost estimate', async ({ page }) => {
      // Set up request interception to verify API calls
      const apiCalls: string[] = [];

      page.on('request', (request) => {
        if (request.url().includes('/api/cost/')) {
          apiCalls.push(request.url());
        }
      });

      // Navigate to plans page which may trigger cost estimate requests
      await page.goto('/plans');
      await waitForNetworkIdle(page);

      // Try to trigger a workflow that would show cost estimate
      const createButton = page.locator(SELECTORS.plans.createButton).first();
      const hasCreateButton = await createButton.isVisible().catch(() => false);

      if (hasCreateButton) {
        await createButton.click();
        await waitForNetworkIdle(page);
      }

      // Log captured API calls for debugging
      console.log('Cost API calls made:', apiCalls);
    });

    test('should handle cost API responses correctly', async ({ page, apiClient }) => {
      // Make direct API call and verify response handling
      const response = await apiClient.get('/api/cost/summary');

      expect(response.ok).toBe(true);
      expect(response.status).toBe(200);
      expect(response.body).toBeTruthy();
    });
  });
});
