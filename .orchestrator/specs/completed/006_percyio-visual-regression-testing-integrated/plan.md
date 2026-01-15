# Plan: Add Percy.io visual regression testing integrated with Playwright. (1) Add @percy/cli and @percy/pla

Request: Add Percy.io visual regression testing integrated with Playwright. (1) Add @percy/cli and @percy/playwright to package.json dependencies. (2) Create percy.yml configuration file with snapshot settings, widths [1280, 768, 375]. (3) Create .orchestrator/tests/e2e/visual/ directory. (4) Create visual/snapshots.spec.ts that captures Percy snapshots of: plan list page, plan detail page (empty state), plan detail page (with steps), build progress page. (5) Add npm script 'test:visual' that runs percy exec with playwright. (6) Document Percy token setup in README or separate docs. (7) Add GitHub Actions workflow step for Percy CI integration.
Complexity: medium

## Goal

Add Percy visual regression testing to the Python/Playwright E2E test suite, capturing snapshots of plan list, plan detail, and build pages at multiple viewport widths.

## Context

- Python project using uv/pyproject.toml, NOT npm/package.json
- pytest-playwright 0.4.0 already configured in dev dependencies
- E2E tests in .orchestrator/tests/e2e/ using pytest fixtures (page, base_url, live_server)
- Percy requires percy-playwright Python package plus @percy/cli (run via npx in CI)
- No .github/workflows/ directory exists yet - must create from scratch

## Steps

1. Add Percy Python dependency
   DO: Add percy-playwright package to dev dependencies in pyproject.toml under [project.optional-dependencies] or [tool.uv.dev-dependencies]
   IN: .orchestrator/pyproject.toml
   OUT: .orchestrator/pyproject.toml (modified)
   DONE: uv sync completes without errors and percy-playwright is installed
   NEEDS: none

## Verify

- uv sync completes and percy-playwright is listed in installed packages
- pytest .orchestrator/tests/e2e/visual/ -v runs all four snapshot tests without errors
- PERCY_TOKEN=test npx percy exec -- pytest .orchestrator/tests/e2e/visual/ -v executes Percy CLI wrapper
- GitHub workflow YAML passes yamllint validation
