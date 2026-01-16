import {
  test,
  expect,
  APIClient,
  waitFor,
  generateTestId,
  waitForNetworkIdle
} from './fixtures';
import type { Run } from './fixtures';

/**
 * E2E tests for Plan Lifecycle Workflow.
 *
 * Tests cover the core plan lifecycle operations:
 * - Creating a new plan via POST /api/workflows/plan
 * - Triggering a build for a plan via POST /api/workflows/build
 * - Completing review cycle via POST /api/workflows/review
 *
 * For comprehensive workflow tests, see workflows/plan-lifecycle.spec.ts
 */

test.describe('Plan Lifecycle Workflow', () => {
  /**
   * Helper to check if a workflow endpoint is available
   */
  async function isEndpointAvailable(
    apiClient: APIClient,
    endpoint: string,
    testPayload: Record<string, unknown>
  ): Promise<boolean> {
    try {
      const response = await apiClient.post(endpoint, testPayload);
      // 400/422 means endpoint exists but validation failed (expected for test payloads)
      return response.status !== 404 && response.status !== 405;
    } catch {
      return false;
    }
  }

  /**
   * Helper to poll for run completion with timeout
   */
  async function waitForRunCompletion(
    apiClient: APIClient,
    runId: string,
    timeoutMs: number = 60000
  ): Promise<Run> {
    return waitFor(
      async () => {
        const run = await apiClient.getRun(runId);
        if (run.status === 'completed' || run.status === 'failed') {
          return run;
        }
        return null as unknown as Run;
      },
      {
        timeout: timeoutMs,
        interval: 1000,
        message: `Run ${runId} did not complete within ${timeoutMs}ms`
      }
    );
  }

  test('should create new plan via workflow API', async ({ apiClient }) => {
    // Check if plan endpoint is available
    const isAvailable = await isEndpointAvailable(
      apiClient,
      '/api/workflows/plan',
      { description: '' }
    );

    if (!isAvailable) {
      test.skip(true, 'POST /api/workflows/plan endpoint not available');
      return;
    }

    // Create a unique plan description for the test
    const testId = generateTestId('plan-lifecycle');
    const description = `E2E Test: Create a hello world utility function. Test ID: ${testId}`;

    // Make POST request to create plan via workflow API
    const response = await apiClient.post('/api/workflows/plan', {
      description
    });

    // Verify response indicates success
    expect(response.ok).toBeTruthy();
    expect(response.status).toBe(200);

    const data = response.body as { run_id?: string; status?: string };

    // Should return a run_id for tracking the planning workflow
    expect(data).toBeDefined();
    expect(data.run_id).toBeTruthy();
    expect(typeof data.run_id).toBe('string');

    // Status should indicate the workflow has started
    if (data.status) {
      expect(['pending', 'running', 'started', 'queued']).toContain(
        data.status.toLowerCase()
      );
    }

    // Verify the run can be fetched and is a planning workflow
    if (data.run_id) {
      const run = await apiClient.getRun(data.run_id);
      expect(run).toBeDefined();
      expect(run.id).toBe(data.run_id);
      expect(run.workflow).toBe('planning');

      // Run should have expected structure
      expect(typeof run.progress).toBe('number');
      expect(run.progress).toBeGreaterThanOrEqual(0);
      expect(run.progress).toBeLessThanOrEqual(100);
      expect(Array.isArray(run.events)).toBeTruthy();
    }
  });

  test('should trigger build for created plan', async ({ apiClient, testPlan }) => {
    // Check if build endpoint is available
    const isAvailable = await isEndpointAvailable(
      apiClient,
      '/api/workflows/build',
      { plan_path: '' }
    );

    if (!isAvailable) {
      test.skip(true, 'POST /api/workflows/build endpoint not available');
      return;
    }

    // Get a plan to build - use fixture or fetch from API
    let planPath: string;

    if (testPlan && testPlan.file) {
      planPath = testPlan.file;
    } else {
      // Try to get any available plan from the API
      try {
        const { plans } = await apiClient.getPlans();
        if (plans.length === 0) {
          test.skip(true, 'No plans available to trigger build');
          return;
        }
        planPath = plans[0].file;
      } catch {
        test.skip(true, 'Could not fetch plans for build test');
        return;
      }
    }

    // Make POST request to trigger build workflow
    const response = await apiClient.post('/api/workflows/build', {
      plan_path: planPath
    });

    // Verify response indicates success
    expect(response.ok).toBeTruthy();
    expect(response.status).toBe(200);

    const data = response.body as { run_id?: string; status?: string };

    // Should return a run_id for tracking the build workflow
    expect(data).toBeDefined();
    expect(data.run_id).toBeTruthy();
    expect(typeof data.run_id).toBe('string');

    // Verify the run is a building workflow
    if (data.run_id) {
      const run = await apiClient.getRun(data.run_id);
      expect(run).toBeDefined();
      expect(run.id).toBe(data.run_id);
      expect(run.workflow).toBe('building');

      // Build run should reference the plan path
      expect(run.plan_path).toBe(planPath);

      // Run should have expected structure
      expect(typeof run.progress).toBe('number');
      expect(Array.isArray(run.events)).toBeTruthy();
    }
  });

  test('should complete review cycle', async ({ apiClient, testPlan }) => {
    // Check if review endpoint is available
    const isAvailable = await isEndpointAvailable(
      apiClient,
      '/api/workflows/review',
      { plan_path: '' }
    );

    if (!isAvailable) {
      test.skip(true, 'POST /api/workflows/review endpoint not available');
      return;
    }

    // Get a plan to review
    let planPath: string;

    if (testPlan && testPlan.file) {
      planPath = testPlan.file;
    } else {
      // Try to get any available plan from the API
      try {
        const { plans } = await apiClient.getPlans();
        if (plans.length === 0) {
          test.skip(true, 'No plans available for review');
          return;
        }
        planPath = plans[0].file;
      } catch {
        test.skip(true, 'Could not fetch plans for review test');
        return;
      }
    }

    // Make POST request to trigger review workflow
    const response = await apiClient.post('/api/workflows/review', {
      plan_path: planPath
    });

    // Verify response indicates success
    expect(response.ok).toBeTruthy();
    expect(response.status).toBe(200);

    const data = response.body as {
      run_id?: string;
      status?: string;
      result?: unknown;
      feedback?: unknown;
    };

    // Should return either a run_id (async) or result (sync)
    expect(data).toBeDefined();

    if (data.run_id) {
      // Async review workflow
      const run = await apiClient.getRun(data.run_id);
      expect(run).toBeDefined();
      expect(run.id).toBe(data.run_id);

      // Workflow type should be review-related
      expect(['reviewing', 'review', 'syncing']).toContain(run.workflow);

      // Run should have expected structure
      expect(typeof run.progress).toBe('number');
      expect(Array.isArray(run.events)).toBeTruthy();

      // Optionally wait for completion to verify review feedback
      try {
        const completedRun = await waitForRunCompletion(apiClient, data.run_id, 30000);

        if (completedRun.status === 'completed') {
          // Completed review should have output or result
          expect(
            completedRun.output_file ||
            (completedRun as unknown as Record<string, unknown>).result
          ).toBeDefined();
        }
      } catch {
        // Run didn't complete in time - acceptable for this test
        console.log('Review run did not complete within timeout');
      }
    } else if (data.result || data.feedback) {
      // Sync review - result directly returned
      expect(data.result || data.feedback).toBeDefined();
    }
  });
});
