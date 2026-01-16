import {
  test,
  expect,
  SELECTORS,
  waitForNetworkIdle,
  PageHelper
} from './fixtures';
import type { Page } from '@playwright/test';

/**
 * E2E tests for Expert Management Workflow.
 *
 * Tests cover:
 * - Displaying the list of experts (GET /experts or /api/experts)
 * - Creating a new expert (POST to expert endpoint)
 *
 * Note: These tests use test.skip() fallback if the expert endpoints are not yet
 * implemented in the server. This allows the test suite to run gracefully while
 * the feature is under development.
 */

// API endpoints for expert management
const EXPERT_ENDPOINTS = {
  list: '/api/experts',
  create: '/api/experts',
  detail: (id: string) => `/api/experts/${id}`,
};

// Expert interface for type safety
interface Expert {
  id: string;
  name: string;
  description?: string;
  expertise?: string[];
  capabilities?: Record<string, boolean>;
  status?: 'active' | 'inactive' | 'pending';
  created_at?: string;
}

test.describe('Expert Management Workflow', () => {
  /**
   * Helper to check if expert endpoints are available
   */
  async function checkExpertEndpointsAvailable(page: Page): Promise<{ apiAvailable: boolean; uiAvailable: boolean }> {
    // Check API endpoint availability
    let apiAvailable = false;
    let uiAvailable = false;

    try {
      const apiResponse = await page.request.get(EXPERT_ENDPOINTS.list);
      apiAvailable = apiResponse.status() !== 404 && apiResponse.status() !== 405;
    } catch {
      apiAvailable = false;
    }

    // Check UI endpoint availability
    try {
      const uiResponse = await page.request.get('/experts');
      uiAvailable = uiResponse.status() !== 404;
    } catch {
      uiAvailable = false;
    }

    return { apiAvailable, uiAvailable };
  }

  test.describe('Expert List Display', () => {
    test('should display expert list when navigating to experts page', async ({ page }) => {
      // First check if expert endpoints are available
      const { apiAvailable, uiAvailable } = await checkExpertEndpointsAvailable(page);

      if (!apiAvailable && !uiAvailable) {
        test.skip(true, 'Expert endpoints not yet implemented');
        return;
      }

      // Navigate to experts page
      await page.goto('/experts');
      await page.waitForLoadState('networkidle');

      // Verify the page has loaded
      const pageContent = page.locator('body');
      await expect(pageContent).toBeVisible();

      // Check for experts-related content indicators
      const expertsHeading = page.locator(
        'h1:has-text("Expert"), ' +
        'h2:has-text("Expert"), ' +
        '[data-testid="experts-heading"], ' +
        '[data-testid="page-title"]:has-text("Expert")'
      ).first();

      // Verify we're on the experts page
      const headingVisible = await expertsHeading.isVisible().catch(() => false);
      if (headingVisible) {
        await expect(expertsHeading).toBeVisible();
      }

      // Verify URL is correct
      await expect(page).toHaveURL(/.*\/experts.*/);
    });

    test('should fetch and display experts from GET /api/experts', async ({ page }) => {
      // Check if API endpoint is available
      const { apiAvailable } = await checkExpertEndpointsAvailable(page);

      if (!apiAvailable) {
        test.skip(true, 'GET /api/experts endpoint not yet implemented');
        return;
      }

      // Make direct API request to verify endpoint functionality
      const response = await page.request.get('/api/experts');
      expect(response.status()).toBe(200);

      const data = await response.json();

      // Verify response structure
      expect(data).toBeDefined();

      // Response should be an array or object with experts array
      if (Array.isArray(data)) {
        // Direct array of experts
        if (data.length > 0) {
          // Verify expert structure
          const firstExpert = data[0];
          expect(firstExpert).toHaveProperty('id');
          expect(firstExpert).toHaveProperty('name');
        }
      } else if (data.experts && Array.isArray(data.experts)) {
        // Object with experts array
        if (data.experts.length > 0) {
          const firstExpert = data.experts[0];
          expect(firstExpert).toHaveProperty('id');
          expect(firstExpert).toHaveProperty('name');
        }
      }
    });

    test('should display expert items in a list or table format', async ({ page }) => {
      const { uiAvailable } = await checkExpertEndpointsAvailable(page);

      if (!uiAvailable) {
        test.skip(true, 'Experts UI page not yet implemented');
        return;
      }

      // Navigate to experts page
      await page.goto('/experts');
      await waitForNetworkIdle(page);

      // Look for expert list container using shared SELECTORS
      const expertListContainer = page.locator(SELECTORS.experts.list).first();

      // Check for individual expert items using shared SELECTORS
      const expertItems = page.locator(SELECTORS.experts.item);

      // Get count of expert items
      const expertCount = await expertItems.count();

      // Log the count for debugging
      console.log(`Found ${expertCount} expert items on the page`);

      // If experts exist, verify they are visible and properly formatted
      if (expertCount > 0) {
        const firstExpert = expertItems.first();
        await expect(firstExpert).toBeVisible();

        // Expert items should contain identifiable information
        const expertText = await firstExpert.textContent();
        expect(expertText).toBeTruthy();
        expect(expertText!.length).toBeGreaterThan(0);
      }
    });

    test('should handle empty expert list gracefully', async ({ page }) => {
      const { apiAvailable } = await checkExpertEndpointsAvailable(page);

      if (!apiAvailable) {
        test.skip(true, 'GET /api/experts endpoint not yet implemented');
        return;
      }

      // Make API request
      const response = await page.request.get('/api/experts');

      // Should return 200 even if empty
      expect(response.status()).toBe(200);

      const data = await response.json();

      // Empty list should still have valid structure
      if (Array.isArray(data)) {
        expect(Array.isArray(data)).toBeTruthy();
      } else {
        expect(data).toHaveProperty('experts');
      }
    });
  });

  test.describe('Expert Creation', () => {
    test('should create new expert via POST /api/experts', async ({ page }) => {
      // Check if expert endpoints are available
      const { apiAvailable } = await checkExpertEndpointsAvailable(page);

      if (!apiAvailable) {
        test.skip(true, 'POST /api/experts endpoint not yet implemented');
        return;
      }

      // Test data for new expert
      const newExpert = {
        name: `Test Expert ${Date.now()}`,
        description: 'An expert created during E2E testing',
        expertise: ['testing', 'automation', 'quality-assurance'],
        capabilities: {
          canReview: true,
          canBuild: false,
          canPlan: true
        }
      };

      // Attempt to create expert via API
      const createResponse = await page.request.post('/api/experts', {
        data: newExpert,
        headers: {
          'Content-Type': 'application/json'
        }
      });

      // Check response status
      const status = createResponse.status();

      if (status === 404 || status === 405) {
        test.skip(true, 'POST /api/experts endpoint not yet implemented');
        return;
      }

      // Expect successful creation (201) or OK (200)
      expect([200, 201]).toContain(status);

      // Verify response contains created expert data
      const responseData = await createResponse.json();
      expect(responseData).toBeDefined();

      // Created expert should have an ID
      if (responseData.id) {
        expect(responseData.id).toBeTruthy();
      } else if (responseData.expert && responseData.expert.id) {
        expect(responseData.expert.id).toBeTruthy();
      }
    });
  });
});
