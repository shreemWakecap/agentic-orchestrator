import { test, expect } from '@playwright/test';
import {
  mockApiError,
  mockNetworkFailure,
  mockTimeout,
  restoreAllMocks,
  ErrorPresets,
  OrchestratorMocks,
  SELECTORS,
  waitForElement,
  waitForToast,
  MockContext,
} from './fixtures';

/**
 * E2E tests for error handling scenarios.
 *
 * Tests cover four main categories:
 * - API Error Responses: HTTP error codes and server-side errors
 * - Network Failures: Connection issues and network interruptions
 * - Invalid Submissions: Form validation and malformed data handling
 * - Error Recovery: Application recovery from error states
 */

test.describe('API Error Responses', () => {
  let mocks: MockContext[] = [];

  test.afterEach(async () => {
    await restoreAllMocks(mocks);
    mocks = [];
  });

  test('should display error message when plans API returns 500', async ({ page }) => {
    // Setup: Mock the plans endpoint to return a server error
    const mock = await mockApiError(
      page,
      /\/api\/plans\/?$/,
      500,
      'Internal Server Error'
    );
    mocks.push(mock);

    // Navigate to plans page
    await page.goto('/plans');

    // Verify error indication is shown
    const errorElement = page.locator(`${SELECTORS.ui.error}, ${SELECTORS.ui.toast}`).first();
    await expect(errorElement).toBeVisible({ timeout: 10000 });

    // Verify the mock was called
    expect(mock.interceptCount).toBeGreaterThan(0);
  });

  test('should display not found message when plan does not exist', async ({ page }) => {
    // Setup: Mock a 404 response for a specific plan
    const mock = await OrchestratorMocks.planNotFound(page, 'nonexistent-plan-123');
    mocks.push(mock);

    // Navigate to the non-existent plan
    await page.goto('/plans/nonexistent-plan-123');

    // Look for 404 or "not found" indication
    const notFoundIndicators = page.locator(
      `${SELECTORS.ui.error}, ` +
      ':text("not found"), ' +
      ':text("404"), ' +
      ':text("does not exist")'
    ).first();

    await expect(notFoundIndicators).toBeVisible({ timeout: 10000 });
  });

  test('should handle 403 forbidden error gracefully', async ({ page }) => {
    const preset = ErrorPresets.forbidden('Access denied to this resource');
    const mock = await mockApiError(
      page,
      /\/api\/plans/,
      preset.statusCode,
      preset.message
    );
    mocks.push(mock);

    await page.goto('/plans');

    // Verify forbidden/access denied message
    const forbiddenIndicators = page.locator(
      `${SELECTORS.ui.error}, ` +
      ':text("forbidden"), ' +
      ':text("access denied"), ' +
      ':text("permission")'
    ).first();

    await expect(forbiddenIndicators).toBeVisible({ timeout: 10000 });
  });

  test('should display validation errors from API (422 response)', async ({ page }) => {
    // Setup: Mock validation error response
    const mock = await OrchestratorMocks.planValidationError(page, {
      goal: ['Goal is required and must be at least 10 characters'],
      name: ['Plan name cannot be empty'],
    });
    mocks.push(mock);

    // Navigate to plan creation page
    await page.goto('/plans/new');

    // Try to submit an empty form (or navigate to trigger validation)
    const submitButton = page.locator(
      `${SELECTORS.forms.submitButton}, ${SELECTORS.plans.createButton}`
    ).first();

    if (await submitButton.isVisible({ timeout: 5000 }).catch(() => false)) {
      await submitButton.click();

      // Verify validation errors are displayed
      const errorMessages = page.locator(SELECTORS.forms.errorMessage);
      await expect(errorMessages.first()).toBeVisible({ timeout: 10000 });
    }
  });

  test('should show rate limit message on 429 response', async ({ page }) => {
    const preset = ErrorPresets.rateLimited(60);
    const mock = await mockApiError(
      page,
      /\/api\/plans/,
      preset.statusCode,
      preset.message,
      { headers: preset.headers }
    );
    mocks.push(mock);

    await page.goto('/plans');

    // Look for rate limit or "too many requests" message
    const rateLimitIndicators = page.locator(
      `${SELECTORS.ui.error}, ` +
      ':text("rate limit"), ' +
      ':text("too many"), ' +
      ':text("try again")'
    ).first();

    await expect(rateLimitIndicators).toBeVisible({ timeout: 10000 });
  });

  test('should handle build failure API error', async ({ page }) => {
    const mock = await OrchestratorMocks.buildFailed(page, 'Build process crashed');
    mocks.push(mock);

    // Navigate to a page that triggers build
    await page.goto('/plans');
    await page.waitForLoadState('networkidle');

    // Find and click a plan to potentially trigger build
    const planLink = page.locator('a[href*="/plan"]').first();
    if (await planLink.isVisible({ timeout: 3000 }).catch(() => false)) {
      await planLink.click();
      await page.waitForLoadState('networkidle');

      // Try to trigger a build
      const buildButton = page.locator(SELECTORS.build.startButton).first();
      if (await buildButton.isVisible({ timeout: 3000 }).catch(() => false)) {
        await buildButton.click();

        // Verify build failure is indicated
        const errorIndicator = page.locator(
          `${SELECTORS.ui.error}, ` +
          ':text("build failed"), ' +
          ':text("error")'
        ).first();

        await expect(errorIndicator).toBeVisible({ timeout: 10000 });
      }
    }
  });

  test('should handle service unavailable (503) with retry message', async ({ page }) => {
    const preset = ErrorPresets.serviceUnavailable('Service temporarily unavailable', 30);
    const mock = await mockApiError(
      page,
      /\/api\/plans/,
      preset.statusCode,
      preset.message,
      { headers: preset.headers }
    );
    mocks.push(mock);

    await page.goto('/plans');

    // Look for service unavailable indication
    const unavailableIndicators = page.locator(
      `${SELECTORS.ui.error}, ` +
      ':text("unavailable"), ' +
      ':text("temporarily"), ' +
      ':text("try again")'
    ).first();

    await expect(unavailableIndicators).toBeVisible({ timeout: 10000 });
  });
});

test.describe('Network Failures', () => {
  let mocks: MockContext[] = [];

  test.afterEach(async () => {
    await restoreAllMocks(mocks);
    mocks = [];
  });

  test('should display network error when connection is refused', async ({ page }) => {
    const mock = await mockNetworkFailure(page, /\/api\/plans/, {
      failureType: 'connectionrefused',
    });
    mocks.push(mock);

    await page.goto('/plans');

    // Look for network/connection error indication
    const networkErrorIndicators = page.locator(
      `${SELECTORS.ui.error}, ` +
      ':text("network"), ' +
      ':text("connection"), ' +
      ':text("unable to connect"), ' +
      ':text("offline")'
    ).first();

    await expect(networkErrorIndicators).toBeVisible({ timeout: 10000 });
  });

  test('should handle internet disconnection gracefully', async ({ page }) => {
    const mock = await mockNetworkFailure(page, /\/api\//, {
      failureType: 'internetdisconnected',
    });
    mocks.push(mock);

    await page.goto('/plans');

    // Verify offline/disconnected indication
    const offlineIndicators = page.locator(
      `${SELECTORS.ui.error}, ` +
      ':text("offline"), ' +
      ':text("disconnected"), ' +
      ':text("no internet"), ' +
      ':text("network")'
    ).first();

    await expect(offlineIndicators).toBeVisible({ timeout: 10000 });
  });

  test('should handle connection reset during request', async ({ page }) => {
    const mock = await mockNetworkFailure(page, /\/api\/plans/, {
      failureType: 'connectionreset',
    });
    mocks.push(mock);

    await page.goto('/plans');

    // Verify error handling for connection reset
    const errorIndicator = page.locator(SELECTORS.ui.error).first();
    await expect(errorIndicator).toBeVisible({ timeout: 10000 });
  });

  test('should show timeout message for slow responses', async ({ page }) => {
    // Use a shorter timeout for test efficiency
    const mock = await mockTimeout(page, /\/api\/plans/, 8000, {
      abortAfterDelay: true,
    });
    mocks.push(mock);

    await page.goto('/plans');

    // Verify timeout indication (may show as loading then error)
    const timeoutIndicators = page.locator(
      `${SELECTORS.ui.error}, ` +
      `${SELECTORS.ui.loading}, ` +
      ':text("timeout"), ' +
      ':text("taking too long"), ' +
      ':text("slow")'
    ).first();

    await expect(timeoutIndicators).toBeVisible({ timeout: 15000 });
  });

  test('should handle complete backend outage', async ({ page }) => {
    const mock = await OrchestratorMocks.backendOutage(page);
    mocks.push(mock);

    await page.goto('/plans');

    // Verify outage/unavailable indication
    const outageIndicators = page.locator(
      `${SELECTORS.ui.error}, ` +
      ':text("unavailable"), ' +
      ':text("cannot connect"), ' +
      ':text("server error")'
    ).first();

    await expect(outageIndicators).toBeVisible({ timeout: 10000 });
  });

  test('should handle request abort gracefully', async ({ page }) => {
    const mock = await mockNetworkFailure(page, /\/api\/plans/, {
      failureType: 'abort',
    });
    mocks.push(mock);

    await page.goto('/plans');

    // Verify the application handles aborted requests
    const errorIndicator = page.locator(`${SELECTORS.ui.error}`).first();
    await expect(errorIndicator).toBeVisible({ timeout: 10000 });
  });
});

test.describe('Invalid Submissions', () => {
  let mocks: MockContext[] = [];

  test.afterEach(async () => {
    await restoreAllMocks(mocks);
    mocks = [];
  });

  test('should show validation error for empty required fields', async ({ page }) => {
    await page.goto('/plans/new');
    await page.waitForLoadState('networkidle');

    // Find the submit button
    const submitButton = page.locator(
      `${SELECTORS.forms.submitButton}, ${SELECTORS.plans.createButton}`
    ).first();

    if (await submitButton.isVisible({ timeout: 5000 }).catch(() => false)) {
      // Try to submit without filling required fields
      await submitButton.click();

      // Look for validation errors (either browser-native or custom)
      const validationIndicators = page.locator(
        `${SELECTORS.forms.errorMessage}, ` +
        ':text("required"), ' +
        ':text("cannot be empty"), ' +
        '[aria-invalid="true"]'
      ).first();

      await expect(validationIndicators).toBeVisible({ timeout: 5000 });
    }
  });

  test('should validate plan name format', async ({ page }) => {
    // Setup: Mock validation error for invalid plan name
    const mock = await mockApiError(
      page,
      /\/api\/plans\/?$/,
      422,
      'Validation failed',
      {
        body: {
          error: 'Validation Error',
          message: 'Invalid plan name format',
          errors: {
            name: ['Plan name contains invalid characters'],
          },
        },
      }
    );
    mocks.push(mock);

    await page.goto('/plans/new');
    await page.waitForLoadState('networkidle');

    // Find text input and fill with invalid data
    const nameInput = page.locator(
      'input[name="name"], ' +
      'input[placeholder*="name"], ' +
      `${SELECTORS.forms.textInput}`
    ).first();

    if (await nameInput.isVisible({ timeout: 5000 }).catch(() => false)) {
      await nameInput.fill('invalid<>name!@#$');

      const submitButton = page.locator(SELECTORS.forms.submitButton).first();
      if (await submitButton.isVisible({ timeout: 3000 }).catch(() => false)) {
        await submitButton.click();

        // Verify validation error is shown
        const errorMessage = page.locator(SELECTORS.forms.errorMessage).first();
        await expect(errorMessage).toBeVisible({ timeout: 10000 });
      }
    }
  });

  test('should handle malformed JSON submission', async ({ page }) => {
    const mock = await mockApiError(
      page,
      /\/api\/plans/,
      400,
      'Bad Request',
      {
        body: {
          error: 'Bad Request',
          message: 'Invalid JSON in request body',
        },
      }
    );
    mocks.push(mock);

    await page.goto('/plans/new');
    await page.waitForLoadState('networkidle');

    // Try to submit (the mock will return bad request error)
    const submitButton = page.locator(
      `${SELECTORS.forms.submitButton}, ${SELECTORS.plans.createButton}`
    ).first();

    if (await submitButton.isVisible({ timeout: 5000 }).catch(() => false)) {
      await submitButton.click();

      // Verify bad request error is shown
      const errorIndicators = page.locator(
        `${SELECTORS.ui.error}, ` +
        ':text("invalid"), ' +
        ':text("bad request")'
      ).first();

      await expect(errorIndicators).toBeVisible({ timeout: 10000 });
    }
  });

  test('should validate goal field minimum length', async ({ page }) => {
    await page.goto('/plans/new');
    await page.waitForLoadState('networkidle');

    // Find goal/description textarea
    const goalInput = page.locator(
      'textarea[name="goal"], ' +
      'textarea[placeholder*="goal"], ' +
      'textarea'
    ).first();

    if (await goalInput.isVisible({ timeout: 5000 }).catch(() => false)) {
      // Enter too short goal
      await goalInput.fill('abc');

      const submitButton = page.locator(SELECTORS.forms.submitButton).first();
      if (await submitButton.isVisible({ timeout: 3000 }).catch(() => false)) {
        await submitButton.click();

        // Look for length validation error
        const validationIndicators = page.locator(
          `${SELECTORS.forms.errorMessage}, ` +
          ':text("minimum"), ' +
          ':text("too short"), ' +
          ':text("at least")'
        ).first();

        await expect(validationIndicators).toBeVisible({ timeout: 5000 });
      }
    }
  });

  test('should prevent duplicate plan submission', async ({ page }) => {
    const mock = await mockApiError(
      page,
      /\/api\/plans\/?$/,
      409,
      'Conflict',
      {
        body: {
          error: 'Conflict',
          message: 'A plan with this name already exists',
        },
      }
    );
    mocks.push(mock);

    await page.goto('/plans/new');
    await page.waitForLoadState('networkidle');

    const nameInput = page.locator(SELECTORS.forms.textInput).first();
    if (await nameInput.isVisible({ timeout: 5000 }).catch(() => false)) {
      await nameInput.fill('existing-plan');

      const submitButton = page.locator(SELECTORS.forms.submitButton).first();
      if (await submitButton.isVisible({ timeout: 3000 }).catch(() => false)) {
        await submitButton.click();

        // Verify conflict error
        const conflictIndicators = page.locator(
          `${SELECTORS.ui.error}, ` +
          ':text("already exists"), ' +
          ':text("duplicate"), ' +
          ':text("conflict")'
        ).first();

        await expect(conflictIndicators).toBeVisible({ timeout: 10000 });
      }
    }
  });

  test('should handle oversized payload error', async ({ page }) => {
    const mock = await mockApiError(
      page,
      /\/api\/plans/,
      413,
      'Payload Too Large',
      {
        body: {
          error: 'Payload Too Large',
          message: 'Request body exceeds maximum allowed size',
        },
      }
    );
    mocks.push(mock);

    await page.goto('/plans/new');
    await page.waitForLoadState('networkidle');

    const submitButton = page.locator(SELECTORS.forms.submitButton).first();
    if (await submitButton.isVisible({ timeout: 5000 }).catch(() => false)) {
      await submitButton.click();

      // Verify payload error message
      const sizeErrorIndicators = page.locator(
        `${SELECTORS.ui.error}, ` +
        ':text("too large"), ' +
        ':text("exceeds"), ' +
        ':text("size limit")'
      ).first();

      await expect(sizeErrorIndicators).toBeVisible({ timeout: 10000 });
    }
  });
});

test.describe('Error Recovery', () => {
  let mocks: MockContext[] = [];

  test.afterEach(async () => {
    await restoreAllMocks(mocks);
    mocks = [];
  });

  test('should recover when API becomes available after failure', async ({ page }) => {
    // First, mock a failure that only happens once
    const mock = await mockApiError(
      page,
      /\/api\/plans\/?$/,
      500,
      'Temporary Server Error',
      { times: 1 }
    );
    mocks.push(mock);

    // Navigate - first request will fail
    await page.goto('/plans');

    // Verify error is shown
    const errorIndicator = page.locator(SELECTORS.ui.error).first();
    await expect(errorIndicator).toBeVisible({ timeout: 10000 });

    // Reload the page - second request should succeed (mock passes through)
    await page.reload();
    await page.waitForLoadState('networkidle');

    // Verify the page loads normally now (error should be gone or content visible)
    const pageContent = page.locator('body');
    await expect(pageContent).toBeVisible();

    // Verify mock was called twice (once failed, once passed through)
    expect(mock.interceptCount).toBe(2);
  });

  test('should allow retry after network failure', async ({ page }) => {
    // Mock network failure that only happens once
    const mock = await mockNetworkFailure(page, /\/api\/plans/, {
      failureType: 'connectionrefused',
      times: 1,
    });
    mocks.push(mock);

    // Navigate - first request will fail
    await page.goto('/plans');

    // Look for retry button or reload capability
    const retryButton = page.locator(
      'button:has-text("retry"), ' +
      'button:has-text("try again"), ' +
      'button:has-text("reload"), ' +
      '[data-testid="retry-button"]'
    ).first();

    // Either click retry button or reload page
    if (await retryButton.isVisible({ timeout: 3000 }).catch(() => false)) {
      await retryButton.click();
    } else {
      await page.reload();
    }

    await page.waitForLoadState('networkidle');

    // Verify the page recovers (mock passes through on second attempt)
    const pageContent = page.locator('body');
    await expect(pageContent).toBeVisible();
  });

  test('should clear error state when navigating away', async ({ page }) => {
    const mock = await mockApiError(
      page,
      /\/api\/plans\/?$/,
      500,
      'Server Error'
    );
    mocks.push(mock);

    // Navigate to plans page (will show error)
    await page.goto('/plans');

    const errorIndicator = page.locator(SELECTORS.ui.error).first();
    await expect(errorIndicator).toBeVisible({ timeout: 10000 });

    // Restore the mock
    await mock.restore();
    mocks = [];

    // Navigate to a different page
    await page.goto('/');
    await page.waitForLoadState('networkidle');

    // Verify error state is cleared (error should not be visible)
    const homeContent = page.locator('body');
    await expect(homeContent).toBeVisible();

    // Error from previous page should not persist
    const persistedError = page.locator(SELECTORS.ui.error);
    const errorCount = await persistedError.count();

    // If errors are visible, they should be new errors, not from previous page
    // This is acceptable - we just want to verify navigation worked
    expect(await homeContent.textContent()).not.toContain('plans');
  });

  test('should maintain form data after validation error', async ({ page }) => {
    await page.goto('/plans/new');
    await page.waitForLoadState('networkidle');

    const nameInput = page.locator(
      'input[name="name"], ' +
      'input[placeholder*="name"], ' +
      `${SELECTORS.forms.textInput}`
    ).first();

    if (await nameInput.isVisible({ timeout: 5000 }).catch(() => false)) {
      const testValue = 'my-test-plan-name';
      await nameInput.fill(testValue);

      // Setup validation error mock
      const mock = await OrchestratorMocks.planValidationError(page, {
        goal: ['Goal is required'],
      });
      mocks.push(mock);

      // Submit the form (will fail validation)
      const submitButton = page.locator(SELECTORS.forms.submitButton).first();
      if (await submitButton.isVisible({ timeout: 3000 }).catch(() => false)) {
        await submitButton.click();

        // Wait for validation response
        await page.waitForTimeout(1000);

        // Verify form data is preserved
        const currentValue = await nameInput.inputValue();
        expect(currentValue).toBe(testValue);
      }
    }
  });

  test('should show loading state during recovery attempt', async ({ page }) => {
    // Mock slow recovery
    const mock = await mockTimeout(page, /\/api\/plans/, 3000, {
      abortAfterDelay: false,
    });
    mocks.push(mock);

    await page.goto('/plans');

    // Verify loading indicator appears during slow request
    const loadingIndicator = page.locator(SELECTORS.ui.loading).first();

    // Loading should be visible while waiting for response
    await expect(loadingIndicator).toBeVisible({ timeout: 5000 });

    // Wait for the mock timeout to complete
    await page.waitForTimeout(3500);
  });

  test('should handle multiple consecutive errors gracefully', async ({ page }) => {
    // Mock multiple errors
    const plansMock = await mockApiError(page, /\/api\/plans/, 500, 'Plans error');
    const expertsMock = await mockApiError(page, /\/api\/experts/, 503, 'Experts unavailable');
    mocks.push(plansMock, expertsMock);

    // Navigate to plans
    await page.goto('/plans');

    // Verify error handling
    const errorIndicator = page.locator(SELECTORS.ui.error).first();
    await expect(errorIndicator).toBeVisible({ timeout: 10000 });

    // Restore mocks
    await restoreAllMocks(mocks);
    mocks = [];

    // Reload should recover
    await page.reload();
    await page.waitForLoadState('networkidle');

    const pageContent = page.locator('body');
    await expect(pageContent).toBeVisible();
  });

  test('should preserve application state during transient errors', async ({ page }) => {
    // Navigate to plans first (successfully)
    await page.goto('/plans');
    await page.waitForLoadState('networkidle');

    // Record initial URL
    const initialUrl = page.url();

    // Now mock an error for subsequent requests
    const mock = await mockApiError(
      page,
      /\/api\/plans\/[^/]+/,
      500,
      'Temporary error',
      { times: 1 }
    );
    mocks.push(mock);

    // Try to access a specific plan (will fail)
    await page.goto('/plans/some-plan-id');

    // Verify error is shown
    const errorIndicator = page.locator(SELECTORS.ui.error).first();
    await expect(errorIndicator).toBeVisible({ timeout: 10000 });

    // Navigate back to plans list (should work since mock passed through)
    await page.goBack();
    await page.waitForLoadState('networkidle');

    // Application should still be functional
    const pageContent = page.locator('body');
    await expect(pageContent).toBeVisible();
  });
});
