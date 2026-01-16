# Plan: Add Percy.io visual regression testing integrated with Playwright. (1) Add @percy/cli and @percy/pla

Request: Add Percy.io visual regression testing integrated with Playwright. (1) Add @percy/cli and @percy/playwright to package.json dependencies. (2) Create percy.yml configuration file with snapshot settings, widths [1280, 768, 375]. (3) Create .orchestrator/tests/e2e/visual/ directory. (4) Create visual/snapshots.spec.ts that captures Percy snapshots of: plan list page, plan detail page (empty state), plan detail page (with steps), build progress page. (5) Add npm script 'test:visual' that runs percy exec with playwright. (6) Document Percy token setup in README or separate docs. (7) Add GitHub Actions workflow step for Percy CI integration.
Complexity: medium

## Goal

Integrate Percy.io visual regression testing with existing Playwright E2E tests, enabling automated screenshot comparison across key pages at multiple viewport widths.

## Context

- Playwright E2E tests exist in .orchestrator/tests/e2e/ with established patterns
- No GitHub Actions workflows exist yet - .github/workflows/ must be created
- Existing tests use test.skip() for conditional skipping when data unavailable
- Server runs on localhost:8000 via python -m orchestrator.server.app
- Package.json already has test script patterns to follow

## Steps

1. Add Percy dependencies to package.json
   DO: Add @percy/cli and @percy/playwright as devDependencies in the existing package.json
   IN: .orchestrator/tests/e2e/package.json
   OUT: .orchestrator/tests/e2e/package.json (modified)
   DONE: npm install succeeds without errors; package.json contains both @percy/cli and @percy/playwright in devDependencies
   NEEDS: none

2. Create Percy configuration file
   DO: Create percy.yml with snapshot settings including widths array [1280, 768, 375], snapshot command configuration, and any relevant Percy options for Playwright integration
   IN: none
   OUT: .orchestrator/tests/e2e/percy.yml
   DONE: File exists with valid YAML syntax containing widths configuration
   NEEDS: none

3. Create visual tests directory
   DO: Create the visual/ subdirectory under .orchestrator/tests/e2e/ to house Percy snapshot tests
   IN: none
   OUT: .orchestrator/tests/e2e/visual/ (directory)
   DONE: Directory exists at specified path
   NEEDS: none

4. Create visual snapshots test file
   DO: Create snapshots.spec.ts with Percy snapshot tests for four pages: (a) plan list page at /plans, (b) plan detail page empty state at /plans/:id with no steps, (c) plan detail page with steps showing populated content, (d) build progress page at /runs/:id. Use percySnapshot() from @percy/playwright. Follow existing test patterns with describe/test blocks, page.goto(), waitForLoadState('networkidle'), and test.skip() for conditional skipping when required data unavailable
   IN: .orchestrator/tests/e2e/plans.spec.ts, .orchestrator/tests/e2e/plan-details.spec.ts, .orchestrator/tests/e2e/build.spec.ts
   OUT: .orchestrator/tests/e2e/visual/snapshots.spec.ts
   DONE: File contains four distinct test cases with percySnapshot() calls; TypeScript compiles without errors
   NEEDS: 1, 3

5. Add npm script for visual testing
   DO: Add "test:visual" script to package.json scripts section that runs "percy exec -- playwright test visual/" to execute Percy with Playwright visual tests
   IN: .orchestrator/tests/e2e/package.json
   OUT: .orchestrator/tests/e2e/package.json (modified)
   DONE: npm run test:visual command is recognized; script value matches expected pattern
   NEEDS: 1

6. Create Percy setup documentation
   DO: Create PERCY_SETUP.md documenting how to obtain Percy token from percy.io, configure PERCY_TOKEN environment variable locally, set up GitHub secret for CI, run visual tests locally and in CI, and interpret Percy dashboard results
   IN: none
   OUT: .orchestrator/tests/e2e/docs/PERCY_SETUP.md
   DONE: File exists with sections for token setup, local usage, CI configuration, and troubleshooting
   NEEDS: none

7. Create GitHub Actions workflow for Percy CI
   DO: Create visual-regression.yml workflow that triggers on push/PR to main branches, sets up Node.js, installs dependencies, starts the Python server (python -m orchestrator.server.app), waits for server ready, runs npm run test:visual with PERCY_TOKEN from GitHub secrets, and handles cleanup
   IN: .orchestrator/tests/e2e/package.json
   OUT: .github/workflows/visual-regression.yml
   DONE: Workflow file has valid YAML syntax; contains jobs with checkout, setup-node, npm install, server start, and percy exec steps; references secrets.PERCY_TOKEN
   NEEDS: 5, 6

## Verify

- npm run test:visual executes without script errors (may skip snapshots without PERCY_TOKEN)
- npx playwright test visual/ --list shows four test cases
- cat .github/workflows/visual-regression.yml shows valid workflow with PERCY_TOKEN secret usage
