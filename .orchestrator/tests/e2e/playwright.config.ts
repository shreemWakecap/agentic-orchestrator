import { defineConfig, devices } from '@playwright/test';

/**
 * Playwright configuration for orchestrator E2E tests.
 * @see https://playwright.dev/docs/test-configuration
 */
export default defineConfig({
  // Test directory - current folder
  testDir: '.',

  // Test file patterns
  testMatch: '**/*.spec.ts',

  // Run tests in parallel
  fullyParallel: true,

  // Fail the build on CI if test.only is left in the code
  forbidOnly: !!process.env.CI,

  // Retry failed tests on CI
  retries: process.env.CI ? 2 : 0,

  // Number of parallel workers
  workers: process.env.CI ? 1 : undefined,

  // Reporter configuration
  reporter: [
    ['list'],
    ['html', { outputFolder: 'playwright-report', open: 'never' }],
  ],

  // Global timeout for each test - 30 seconds
  timeout: 30000,

  // Expect timeout
  expect: {
    timeout: 5000,
  },

  // Shared settings for all projects
  use: {
    // Base URL for all tests
    baseURL: 'http://localhost:8000',

    // Capture screenshot on test failure
    screenshot: 'only-on-failure',

    // Capture trace on first retry
    trace: 'on-first-retry',

    // Record video only on failure
    video: 'retain-on-failure',

    // Action timeout
    actionTimeout: 10000,

    // Navigation timeout
    navigationTimeout: 15000,
  },

  // Configure projects for major browsers
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],

  // Web server configuration - start the orchestrator server before tests
  webServer: {
    command: 'cd ../../../ && python -m orchestrator.server.app',
    url: 'http://localhost:8000',
    reuseExistingServer: !process.env.CI,
    timeout: 120000,
  },
});
