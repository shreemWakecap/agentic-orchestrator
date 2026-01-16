import { Page, Route, Request } from '@playwright/test';

/**
 * Reusable route interception helpers for testing error scenarios.
 * These utilities enable comprehensive error handling tests by simulating
 * various API failure conditions including HTTP errors, network failures, and timeouts.
 */

/**
 * Options for configuring mock API error responses
 */
export interface MockApiErrorOptions {
  /** HTTP status code to return (default: derived from preset or 500) */
  statusCode?: number;
  /** Error message to include in response body */
  message?: string;
  /** Content type of the response (default: 'application/json') */
  contentType?: string;
  /** Additional response headers */
  headers?: Record<string, string>;
  /** Custom response body (overrides message-based body) */
  body?: string | object;
  /** Number of times to intercept before passing through (default: unlimited) */
  times?: number;
}

/**
 * Options for configuring network failure simulation
 */
export interface MockNetworkFailureOptions {
  /** Type of network failure to simulate */
  failureType?: 'abort' | 'close' | 'connectionrefused' | 'connectionreset' | 'internetdisconnected';
  /** Number of times to intercept before passing through (default: unlimited) */
  times?: number;
}

/**
 * Options for configuring timeout simulation
 */
export interface MockTimeoutOptions {
  /** Delay in milliseconds before responding (default: 30000) */
  delayMs?: number;
  /** Whether to abort after delay (simulates true timeout) or respond after delay */
  abortAfterDelay?: boolean;
  /** Number of times to intercept before passing through (default: unlimited) */
  times?: number;
}

/**
 * Context object returned by mock functions for cleanup and inspection
 */
export interface MockContext {
  /** Removes the route handler */
  restore: () => Promise<void>;
  /** Number of times the route was intercepted */
  interceptCount: number;
  /** URLs that were intercepted */
  interceptedUrls: string[];
}

/**
 * Mock an API endpoint to return an error response.
 *
 * @param page - Playwright Page object
 * @param urlPattern - URL pattern to match (string, RegExp, or predicate function)
 * @param statusCode - HTTP status code to return
 * @param message - Error message to include in response
 * @param options - Additional options for customizing the error response
 * @returns MockContext for cleanup and inspection
 *
 * @example
 * // Mock a 404 error for a specific endpoint
 * const mock = await mockApiError(page, '/api/plans/123', 404, 'Plan not found');
 *
 * @example
 * // Mock a 500 error with custom body
 * const mock = await mockApiError(page, new RegExp('/api/workflows/.*'), 500, 'Internal error', {
 *   body: { error: 'Internal Server Error', details: 'Database connection failed' }
 * });
 */
export async function mockApiError(
  page: Page,
  urlPattern: string | RegExp | ((url: URL) => boolean),
  statusCode: number,
  message: string,
  options: MockApiErrorOptions = {}
): Promise<MockContext> {
  const {
    contentType = 'application/json',
    headers = {},
    body,
    times,
  } = options;

  const context: MockContext = {
    interceptCount: 0,
    interceptedUrls: [],
    restore: async () => {},
  };

  const handler = async (route: Route, request: Request) => {
    context.interceptCount++;
    context.interceptedUrls.push(request.url());

    // Check if we should pass through after reaching times limit
    if (times !== undefined && context.interceptCount > times) {
      await route.continue();
      return;
    }

    // Determine response body
    let responseBody: string;
    if (body !== undefined) {
      responseBody = typeof body === 'string' ? body : JSON.stringify(body);
    } else {
      responseBody = JSON.stringify({
        error: message,
        statusCode,
        timestamp: new Date().toISOString(),
        path: new URL(request.url()).pathname,
      });
    }

    await route.fulfill({
      status: statusCode,
      contentType,
      headers: {
        'X-Mock-Error': 'true',
        ...headers,
      },
      body: responseBody,
    });
  };

  await page.route(urlPattern, handler);

  context.restore = async () => {
    await page.unroute(urlPattern, handler);
  };

  return context;
}

/**
 * Mock network failure for a URL pattern.
 *
 * @param page - Playwright Page object
 * @param urlPattern - URL pattern to match (string, RegExp, or predicate function)
 * @param options - Options for configuring the network failure
 * @returns MockContext for cleanup and inspection
 *
 * @example
 * // Simulate a connection refused error
 * const mock = await mockNetworkFailure(page, '/api/plans', {
 *   failureType: 'connectionrefused'
 * });
 *
 * @example
 * // Simulate internet disconnection
 * const mock = await mockNetworkFailure(page, new RegExp('/api/.*'), {
 *   failureType: 'internetdisconnected'
 * });
 */
export async function mockNetworkFailure(
  page: Page,
  urlPattern: string | RegExp | ((url: URL) => boolean),
  options: MockNetworkFailureOptions = {}
): Promise<MockContext> {
  const { failureType = 'connectionrefused', times } = options;

  const context: MockContext = {
    interceptCount: 0,
    interceptedUrls: [],
    restore: async () => {},
  };

  const handler = async (route: Route, request: Request) => {
    context.interceptCount++;
    context.interceptedUrls.push(request.url());

    // Check if we should pass through after reaching times limit
    if (times !== undefined && context.interceptCount > times) {
      await route.continue();
      return;
    }

    await route.abort(failureType);
  };

  await page.route(urlPattern, handler);

  context.restore = async () => {
    await page.unroute(urlPattern, handler);
  };

  return context;
}

/**
 * Mock a timeout for a URL pattern.
 *
 * @param page - Playwright Page object
 * @param urlPattern - URL pattern to match (string, RegExp, or predicate function)
 * @param delayMs - Delay in milliseconds before responding/aborting
 * @param options - Additional options for timeout behavior
 * @returns MockContext for cleanup and inspection
 *
 * @example
 * // Simulate a slow response (5 second delay)
 * const mock = await mockTimeout(page, '/api/workflows/build', 5000);
 *
 * @example
 * // Simulate a true timeout (abort after delay)
 * const mock = await mockTimeout(page, new RegExp('/api/.*'), 10000, {
 *   abortAfterDelay: true
 * });
 */
export async function mockTimeout(
  page: Page,
  urlPattern: string | RegExp | ((url: URL) => boolean),
  delayMs: number = 30000,
  options: MockTimeoutOptions = {}
): Promise<MockContext> {
  const { abortAfterDelay = false, times } = options;

  const context: MockContext = {
    interceptCount: 0,
    interceptedUrls: [],
    restore: async () => {},
  };

  const handler = async (route: Route, request: Request) => {
    context.interceptCount++;
    context.interceptedUrls.push(request.url());

    // Check if we should pass through after reaching times limit
    if (times !== undefined && context.interceptCount > times) {
      await route.continue();
      return;
    }

    // Wait for the specified delay
    await new Promise(resolve => setTimeout(resolve, delayMs));

    if (abortAfterDelay) {
      await route.abort('timedout');
    } else {
      // Return a timeout error response after delay
      await route.fulfill({
        status: 504,
        contentType: 'application/json',
        headers: {
          'X-Mock-Timeout': 'true',
        },
        body: JSON.stringify({
          error: 'Gateway Timeout',
          message: `Request timed out after ${delayMs}ms`,
          statusCode: 504,
          timestamp: new Date().toISOString(),
          path: new URL(request.url()).pathname,
        }),
      });
    }
  };

  await page.route(urlPattern, handler);

  context.restore = async () => {
    await page.unroute(urlPattern, handler);
  };

  return context;
}

/**
 * Preset error configurations for common scenarios
 */
export const ErrorPresets = {
  /** 400 Bad Request */
  badRequest: (message = 'Bad Request') => ({
    statusCode: 400,
    message,
  }),

  /** 401 Unauthorized */
  unauthorized: (message = 'Unauthorized') => ({
    statusCode: 401,
    message,
  }),

  /** 403 Forbidden */
  forbidden: (message = 'Forbidden') => ({
    statusCode: 403,
    message,
  }),

  /** 404 Not Found */
  notFound: (message = 'Not Found') => ({
    statusCode: 404,
    message,
  }),

  /** 409 Conflict */
  conflict: (message = 'Conflict') => ({
    statusCode: 409,
    message,
  }),

  /** 422 Unprocessable Entity (validation error) */
  validationError: (message = 'Validation Error', details?: Record<string, string[]>) => ({
    statusCode: 422,
    message,
    body: {
      error: 'Validation Error',
      message,
      details: details || {},
    },
  }),

  /** 429 Too Many Requests (rate limit) */
  rateLimited: (retryAfter = 60) => ({
    statusCode: 429,
    message: 'Too Many Requests',
    headers: {
      'Retry-After': String(retryAfter),
    },
  }),

  /** 500 Internal Server Error */
  serverError: (message = 'Internal Server Error') => ({
    statusCode: 500,
    message,
  }),

  /** 502 Bad Gateway */
  badGateway: (message = 'Bad Gateway') => ({
    statusCode: 502,
    message,
  }),

  /** 503 Service Unavailable */
  serviceUnavailable: (message = 'Service Unavailable', retryAfter?: number) => ({
    statusCode: 503,
    message,
    headers: retryAfter ? { 'Retry-After': String(retryAfter) } : {},
  }),
} as const;

/**
 * Helper to mock multiple endpoints at once
 *
 * @param page - Playwright Page object
 * @param mocks - Array of mock configurations
 * @returns Array of MockContexts for cleanup
 *
 * @example
 * const mocks = await mockMultipleErrors(page, [
 *   { pattern: '/api/plans', statusCode: 500, message: 'Server error' },
 *   { pattern: '/api/experts', statusCode: 404, message: 'Not found' },
 * ]);
 *
 * // Cleanup all mocks
 * await Promise.all(mocks.map(m => m.restore()));
 */
export async function mockMultipleErrors(
  page: Page,
  mocks: Array<{
    pattern: string | RegExp | ((url: URL) => boolean);
    statusCode: number;
    message: string;
    options?: MockApiErrorOptions;
  }>
): Promise<MockContext[]> {
  return Promise.all(
    mocks.map(({ pattern, statusCode, message, options }) =>
      mockApiError(page, pattern, statusCode, message, options)
    )
  );
}

/**
 * Helper to restore multiple mock contexts at once
 *
 * @param contexts - Array of MockContexts to restore
 */
export async function restoreAllMocks(contexts: MockContext[]): Promise<void> {
  await Promise.all(contexts.map(ctx => ctx.restore()));
}

/**
 * Utility to wait for a mocked request to be intercepted
 *
 * @param context - MockContext to monitor
 * @param timeout - Maximum time to wait in ms (default: 5000)
 * @returns Promise that resolves when a request is intercepted
 */
export async function waitForInterception(
  context: MockContext,
  timeout: number = 5000
): Promise<void> {
  const startTime = Date.now();
  const initialCount = context.interceptCount;

  while (context.interceptCount === initialCount) {
    if (Date.now() - startTime > timeout) {
      throw new Error(`Timeout waiting for route interception after ${timeout}ms`);
    }
    await new Promise(resolve => setTimeout(resolve, 50));
  }
}

/**
 * Mock specific orchestrator API endpoints
 */
export const OrchestratorMocks = {
  /**
   * Mock plan creation failure
   */
  async planCreationFailed(page: Page, message = 'Failed to create plan'): Promise<MockContext> {
    return mockApiError(page, /\/api\/plans\/?$/, 500, message, {
      body: {
        error: 'Plan Creation Failed',
        message,
        details: 'An error occurred while creating the plan',
      },
    });
  },

  /**
   * Mock plan not found
   */
  async planNotFound(page: Page, planId?: string): Promise<MockContext> {
    const pattern = planId ? `/api/plans/${planId}` : /\/api\/plans\/[^/]+$/;
    return mockApiError(page, pattern, 404, 'Plan not found', {
      body: {
        error: 'Not Found',
        message: planId ? `Plan '${planId}' not found` : 'Plan not found',
      },
    });
  },

  /**
   * Mock build workflow failure
   */
  async buildFailed(page: Page, message = 'Build workflow failed'): Promise<MockContext> {
    return mockApiError(page, /\/api\/workflows\/build/, 500, message, {
      body: {
        error: 'Build Failed',
        message,
        stage: 'execution',
        details: 'The build process encountered an error',
      },
    });
  },

  /**
   * Mock expert listing failure
   */
  async expertsUnavailable(page: Page): Promise<MockContext> {
    return mockApiError(page, /\/api\/experts/, 503, 'Expert service unavailable', {
      headers: { 'Retry-After': '30' },
    });
  },

  /**
   * Mock cost estimation failure
   */
  async costEstimationFailed(page: Page): Promise<MockContext> {
    return mockApiError(page, /\/api\/cost/, 500, 'Cost estimation failed', {
      body: {
        error: 'Cost Estimation Error',
        message: 'Unable to calculate cost estimate',
      },
    });
  },

  /**
   * Mock run/build not found
   */
  async runNotFound(page: Page, runId?: string): Promise<MockContext> {
    const pattern = runId ? `/api/runs/${runId}` : /\/api\/runs\/[^/]+$/;
    return mockApiError(page, pattern, 404, 'Run not found');
  },

  /**
   * Mock validation error for plan creation
   */
  async planValidationError(
    page: Page,
    errors: Record<string, string[]> = { goal: ['Goal is required'] }
  ): Promise<MockContext> {
    return mockApiError(page, /\/api\/plans\/?$/, 422, 'Validation failed', {
      body: {
        error: 'Validation Error',
        message: 'Plan validation failed',
        errors,
      },
    });
  },

  /**
   * Mock all API endpoints to simulate complete backend outage
   */
  async backendOutage(page: Page): Promise<MockContext> {
    return mockNetworkFailure(page, /\/api\//, {
      failureType: 'connectionrefused',
    });
  },

  /**
   * Mock slow API responses
   */
  async slowBackend(page: Page, delayMs = 5000): Promise<MockContext> {
    return mockTimeout(page, /\/api\//, delayMs, {
      abortAfterDelay: false,
    });
  },
};
