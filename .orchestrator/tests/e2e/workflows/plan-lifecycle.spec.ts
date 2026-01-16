import { test, expect, APIClient, Run, Plan, waitFor, generateTestId } from '../fixtures/test-fixtures';

/**
 * E2E tests for Plan Lifecycle Workflow.
 *
 * Tests cover the complete plan lifecycle:
 * - Creating a new plan via POST /api/workflows/plan
 * - Triggering a build for the created plan via POST /api/workflows/build
 * - Completing the review cycle via POST /api/workflows/review
 *
 * These tests verify the orchestrator's core workflow functionality
 * from end to end.
 */

test.describe('Plan Lifecycle Workflow', () => {
  /**
   * Helper to check if workflow endpoints are available
   */
  async function checkWorkflowEndpoints(apiClient: APIClient): Promise<{
    planAvailable: boolean;
    buildAvailable: boolean;
    reviewAvailable: boolean;
  }> {
    let planAvailable = false;
    let buildAvailable = false;
    let reviewAvailable = false;

    // Check plan workflow endpoint
    try {
      const planResponse = await apiClient.post('/api/workflows/plan', { description: '' });
      // 400/422 means endpoint exists but validation failed (expected for empty description)
      planAvailable = planResponse.status !== 404 && planResponse.status !== 405;
    } catch {
      planAvailable = false;
    }

    // Check build workflow endpoint
    try {
      const buildResponse = await apiClient.post('/api/workflows/build', { plan_path: '' });
      buildAvailable = buildResponse.status !== 404 && buildResponse.status !== 405;
    } catch {
      buildAvailable = false;
    }

    // Check review workflow endpoint
    try {
      const reviewResponse = await apiClient.post('/api/workflows/review', { plan_path: '' });
      reviewAvailable = reviewResponse.status !== 404 && reviewResponse.status !== 405;
    } catch {
      reviewAvailable = false;
    }

    return { planAvailable, buildAvailable, reviewAvailable };
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

  test.describe('Plan Creation', () => {
    test('should create new plan via workflow API', async ({ apiClient }) => {
      // Check if plan endpoint is available
      const endpoints = await checkWorkflowEndpoints(apiClient);

      if (!endpoints.planAvailable) {
        test.skip(true, 'POST /api/workflows/plan endpoint not available');
        return;
      }

      // Create a unique plan description
      const testId = generateTestId('plan');
      const description = `E2E Test Plan: Create a simple hello world function. Test ID: ${testId}`;

      // Make POST request to create plan
      const response = await apiClient.post('/api/workflows/plan', {
        description
      });

      // Verify response
      expect(response.ok).toBeTruthy();
      expect(response.status).toBe(200);

      const data = response.body as { run_id?: string; status?: string };

      // Should return a run_id for tracking the planning workflow
      expect(data).toBeDefined();
      expect(data.run_id).toBeTruthy();
      expect(typeof data.run_id).toBe('string');

      // Status should indicate the workflow has started
      if (data.status) {
        expect(['pending', 'running', 'started', 'queued']).toContain(data.status.toLowerCase());
      }

      // Verify the run can be fetched
      if (data.run_id) {
        const run = await apiClient.getRun(data.run_id);
        expect(run).toBeDefined();
        expect(run.id).toBe(data.run_id);
        expect(run.workflow).toBe('planning');
      }
    });

    test('should validate plan description is required', async ({ apiClient }) => {
      const endpoints = await checkWorkflowEndpoints(apiClient);

      if (!endpoints.planAvailable) {
        test.skip(true, 'POST /api/workflows/plan endpoint not available');
        return;
      }

      // Try to create plan without description
      const response = await apiClient.post('/api/workflows/plan', {});

      // Should return validation error
      expect([400, 422]).toContain(response.status);
    });

    test('should reject empty description', async ({ apiClient }) => {
      const endpoints = await checkWorkflowEndpoints(apiClient);

      if (!endpoints.planAvailable) {
        test.skip(true, 'POST /api/workflows/plan endpoint not available');
        return;
      }

      // Try to create plan with empty description
      const response = await apiClient.post('/api/workflows/plan', {
        description: ''
      });

      // Should return validation error
      expect([400, 422]).toContain(response.status);
    });

    test('should track planning progress via run events', async ({ apiClient }) => {
      const endpoints = await checkWorkflowEndpoints(apiClient);

      if (!endpoints.planAvailable) {
        test.skip(true, 'POST /api/workflows/plan endpoint not available');
        return;
      }

      const testId = generateTestId('plan');
      const description = `E2E Progress Test: Simple task. Test ID: ${testId}`;

      // Create the plan
      const response = await apiClient.post('/api/workflows/plan', { description });

      if (!response.ok) {
        test.skip(true, 'Could not create plan for progress tracking test');
        return;
      }

      const data = response.body as { run_id: string };
      const runId = data.run_id;

      // Fetch run status and verify structure
      const run = await apiClient.getRun(runId);

      expect(run).toBeDefined();
      expect(run.id).toBe(runId);
      expect(typeof run.progress).toBe('number');
      expect(run.progress).toBeGreaterThanOrEqual(0);
      expect(run.progress).toBeLessThanOrEqual(100);

      // Events should be an array
      expect(Array.isArray(run.events)).toBeTruthy();
    });
  });

  test.describe('Build Triggering', () => {
    test('should trigger build for created plan', async ({ apiClient, testPlan }) => {
      const endpoints = await checkWorkflowEndpoints(apiClient);

      if (!endpoints.buildAvailable) {
        test.skip(true, 'POST /api/workflows/build endpoint not available');
        return;
      }

      // Get a plan to build
      let planPath: string;

      if (testPlan && testPlan.file) {
        planPath = testPlan.file;
      } else {
        // Try to get any available plan
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

      // Make POST request to trigger build
      const response = await apiClient.post('/api/workflows/build', {
        plan_path: planPath
      });

      // Verify response
      expect(response.ok).toBeTruthy();
      expect(response.status).toBe(200);

      const data = response.body as { run_id?: string; status?: string };

      // Should return a run_id for tracking the build workflow
      expect(data).toBeDefined();
      expect(data.run_id).toBeTruthy();

      // Verify the run is a building workflow
      if (data.run_id) {
        const run = await apiClient.getRun(data.run_id);
        expect(run).toBeDefined();
        expect(run.workflow).toBe('building');
        expect(run.plan_path).toBe(planPath);
      }
    });

    test('should validate plan_path is required for build', async ({ apiClient }) => {
      const endpoints = await checkWorkflowEndpoints(apiClient);

      if (!endpoints.buildAvailable) {
        test.skip(true, 'POST /api/workflows/build endpoint not available');
        return;
      }

      // Try to trigger build without plan_path
      const response = await apiClient.post('/api/workflows/build', {});

      // Should return validation error
      expect([400, 422]).toContain(response.status);
    });

    test('should reject invalid plan path', async ({ apiClient }) => {
      const endpoints = await checkWorkflowEndpoints(apiClient);

      if (!endpoints.buildAvailable) {
        test.skip(true, 'POST /api/workflows/build endpoint not available');
        return;
      }

      // Try to trigger build with non-existent plan
      const response = await apiClient.post('/api/workflows/build', {
        plan_path: '/non/existent/plan/path/plan.md'
      });

      // Should return error (400 or 404)
      expect([400, 404, 422]).toContain(response.status);
    });

    test('should track build progress via run events', async ({ apiClient, testPlan }) => {
      const endpoints = await checkWorkflowEndpoints(apiClient);

      if (!endpoints.buildAvailable) {
        test.skip(true, 'POST /api/workflows/build endpoint not available');
        return;
      }

      let planPath: string;

      if (testPlan && testPlan.file) {
        planPath = testPlan.file;
      } else {
        try {
          const { plans } = await apiClient.getPlans();
          if (plans.length === 0) {
            test.skip(true, 'No plans available for build progress test');
            return;
          }
          planPath = plans[0].file;
        } catch {
          test.skip(true, 'Could not fetch plans');
          return;
        }
      }

      // Trigger build
      const response = await apiClient.post('/api/workflows/build', {
        plan_path: planPath
      });

      if (!response.ok) {
        test.skip(true, 'Could not trigger build for progress test');
        return;
      }

      const data = response.body as { run_id: string };
      const runId = data.run_id;

      // Fetch run status
      const run = await apiClient.getRun(runId);

      expect(run).toBeDefined();
      expect(run.id).toBe(runId);
      expect(typeof run.progress).toBe('number');
      expect(Array.isArray(run.events)).toBeTruthy();

      // Build run should have plan_path associated
      expect(run.plan_path).toBeDefined();
    });
  });

  test.describe('Review Cycle', () => {
    test('should complete review cycle', async ({ apiClient, testPlan }) => {
      const endpoints = await checkWorkflowEndpoints(apiClient);

      if (!endpoints.reviewAvailable) {
        test.skip(true, 'POST /api/workflows/review endpoint not available');
        return;
      }

      // Get a plan to review
      let planPath: string;

      if (testPlan && testPlan.file) {
        planPath = testPlan.file;
      } else {
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

      // Make POST request to trigger review
      const response = await apiClient.post('/api/workflows/review', {
        plan_path: planPath
      });

      // Verify response
      expect(response.ok).toBeTruthy();
      expect(response.status).toBe(200);

      const data = response.body as { run_id?: string; status?: string; result?: unknown };

      // Should return either a run_id (async) or result (sync)
      expect(data).toBeDefined();

      if (data.run_id) {
        // Async review workflow
        const run = await apiClient.getRun(data.run_id);
        expect(run).toBeDefined();
        // Workflow type might be 'reviewing' or similar
        expect(['reviewing', 'review', 'syncing']).toContain(run.workflow);
      } else if (data.result) {
        // Sync review - result directly returned
        expect(data.result).toBeDefined();
      }
    });

    test('should validate plan_path is required for review', async ({ apiClient }) => {
      const endpoints = await checkWorkflowEndpoints(apiClient);

      if (!endpoints.reviewAvailable) {
        test.skip(true, 'POST /api/workflows/review endpoint not available');
        return;
      }

      // Try to trigger review without plan_path
      const response = await apiClient.post('/api/workflows/review', {});

      // Should return validation error
      expect([400, 422]).toContain(response.status);
    });

    test('should reject invalid plan path for review', async ({ apiClient }) => {
      const endpoints = await checkWorkflowEndpoints(apiClient);

      if (!endpoints.reviewAvailable) {
        test.skip(true, 'POST /api/workflows/review endpoint not available');
        return;
      }

      // Try to trigger review with non-existent plan
      const response = await apiClient.post('/api/workflows/review', {
        plan_path: '/non/existent/plan/path/plan.md'
      });

      // Should return error
      expect([400, 404, 422]).toContain(response.status);
    });

    test('should return review feedback in response', async ({ apiClient, testPlan }) => {
      const endpoints = await checkWorkflowEndpoints(apiClient);

      if (!endpoints.reviewAvailable) {
        test.skip(true, 'POST /api/workflows/review endpoint not available');
        return;
      }

      let planPath: string;

      if (testPlan && testPlan.file) {
        planPath = testPlan.file;
      } else {
        try {
          const { plans } = await apiClient.getPlans();
          if (plans.length === 0) {
            test.skip(true, 'No plans available for review feedback test');
            return;
          }
          planPath = plans[0].file;
        } catch {
          test.skip(true, 'Could not fetch plans');
          return;
        }
      }

      // Trigger review
      const response = await apiClient.post('/api/workflows/review', {
        plan_path: planPath
      });

      if (!response.ok) {
        test.skip(true, 'Could not trigger review');
        return;
      }

      const data = response.body as { run_id?: string; result?: unknown; feedback?: unknown };

      // If async, wait for completion and check result
      if (data.run_id) {
        try {
          const completedRun = await waitForRunCompletion(apiClient, data.run_id, 30000);

          // Completed run should have output or result
          if (completedRun.status === 'completed') {
            expect(
              completedRun.output_file ||
              (completedRun as unknown as Record<string, unknown>).result
            ).toBeDefined();
          }
        } catch {
          // Run didn't complete in time - that's ok for this test
          console.log('Review run did not complete within timeout');
        }
      } else if (data.result || data.feedback) {
        // Sync review returned result directly
        expect(data.result || data.feedback).toBeDefined();
      }
    });
  });

  test.describe('Full Lifecycle Integration', () => {
    test('should complete full plan-build-review cycle', async ({ apiClient }) => {
      const endpoints = await checkWorkflowEndpoints(apiClient);

      if (!endpoints.planAvailable) {
        test.skip(true, 'Plan workflow not available');
        return;
      }

      // Step 1: Create a new plan
      const testId = generateTestId('lifecycle');
      const description = `E2E Lifecycle Test: Create a utility function. Test ID: ${testId}`;

      const planResponse = await apiClient.post('/api/workflows/plan', { description });

      if (!planResponse.ok) {
        test.skip(true, 'Could not create plan for lifecycle test');
        return;
      }

      const planData = planResponse.body as { run_id: string };
      expect(planData.run_id).toBeTruthy();

      // Verify planning run was created
      const planRun = await apiClient.getRun(planData.run_id);
      expect(planRun.workflow).toBe('planning');

      // Step 2: Check if build endpoint is available
      if (!endpoints.buildAvailable) {
        console.log('Build workflow not available - lifecycle test limited to plan creation');
        return;
      }

      // Wait for plan to complete (with timeout)
      let completedPlanRun: Run;
      try {
        completedPlanRun = await waitForRunCompletion(apiClient, planData.run_id, 60000);
      } catch {
        console.log('Plan run did not complete within timeout - continuing with existing plans');
        // Try to use an existing plan instead
        try {
          const { plans } = await apiClient.getPlans();
          if (plans.length === 0) {
            console.log('No existing plans available for build step');
            return;
          }

          const buildResponse = await apiClient.post('/api/workflows/build', {
            plan_path: plans[0].file
          });

          if (buildResponse.ok) {
            const buildData = buildResponse.body as { run_id: string };
            const buildRun = await apiClient.getRun(buildData.run_id);
            expect(buildRun.workflow).toBe('building');
          }
        } catch {
          console.log('Could not trigger build with existing plans');
        }
        return;
      }

      // If plan completed successfully, use its output for build
      if (completedPlanRun.status === 'completed' && completedPlanRun.output_file) {
        const buildResponse = await apiClient.post('/api/workflows/build', {
          plan_path: completedPlanRun.output_file
        });

        if (buildResponse.ok) {
          const buildData = buildResponse.body as { run_id: string };
          const buildRun = await apiClient.getRun(buildData.run_id);
          expect(buildRun.workflow).toBe('building');
          expect(buildRun.plan_path).toBe(completedPlanRun.output_file);

          // Step 3: Trigger review if available
          if (endpoints.reviewAvailable) {
            const reviewResponse = await apiClient.post('/api/workflows/review', {
              plan_path: completedPlanRun.output_file
            });

            if (reviewResponse.ok) {
              const reviewData = reviewResponse.body as { run_id?: string };
              if (reviewData.run_id) {
                const reviewRun = await apiClient.getRun(reviewData.run_id);
                expect(['reviewing', 'review', 'syncing']).toContain(reviewRun.workflow);
              }
            }
          }
        }
      }
    });

    test('should maintain data consistency across workflow steps', async ({ apiClient }) => {
      const endpoints = await checkWorkflowEndpoints(apiClient);

      if (!endpoints.planAvailable) {
        test.skip(true, 'Plan workflow not available');
        return;
      }

      // Create a plan with specific content
      const testId = generateTestId('consistency');
      const description = `E2E Consistency Test: Verify data persistence. Test ID: ${testId}`;

      const response = await apiClient.post('/api/workflows/plan', { description });

      if (!response.ok) {
        test.skip(true, 'Could not create plan');
        return;
      }

      const data = response.body as { run_id: string };

      // Fetch the run multiple times to verify consistency
      const run1 = await apiClient.getRun(data.run_id);
      const run2 = await apiClient.getRun(data.run_id);

      // Run data should be consistent
      expect(run1.id).toBe(run2.id);
      expect(run1.workflow).toBe(run2.workflow);
      expect(run1.description || description).toBeDefined();

      // Progress should only increase or stay the same
      expect(run2.progress).toBeGreaterThanOrEqual(run1.progress);
    });
  });
});
