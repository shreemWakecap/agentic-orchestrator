# Plan: Extract inline JavaScript from .orchestrator/server/templates/*.html into separate files and add Jes

Request: Extract inline JavaScript from .orchestrator/server/templates/*.html into separate files and add Jest tests. (1) Analyze all HTML templates for inline <script> tags. (2) Extract JavaScript into .orchestrator/server/static/js/ with meaningful names (e.g., plan-list.js, build-progress.js). (3) Update HTML templates to reference external JS files. (4) Create package.json with jest dependency if not exists, or update existing. (5) Add jest.config.js with proper configuration. (6) Create .orchestrator/server/static/js/__tests__/ directory. (7) Write Jest unit tests for each extracted JS file testing main functions and event handlers. (8) Ensure no inline scripts remain in templates.
Complexity: medium

## Goal

Extract all inline JavaScript from 7 HTML templates into modular external files, configure Jest testing framework, and create comprehensive unit tests for each extracted module.

## Context

- 7 HTML templates in .orchestrator/server/templates/ contain inline scripts
- Scripts handle WebSocket connections, DOM manipulation, polling, copy-to-clipboard
- package.json exists with Playwright but no Jest setup
- static/js/ directory does not exist yet
- Templates use Jinja2 {{ }} placeholders that need runtime injection strategy

## Steps

1. Analyze all HTML templates for inline script tags
   DO: Read all 7 HTML template files and document each inline script's functionality, variables, and dependencies
   IN: .orchestrator/server/templates/plan_list.html, build_progress.html, logs.html, chat.html, static_analysis.html, index.html, base.html
   OUT: Analysis notes identifying script boundaries, shared code, and Jinja2 variable usage
   DONE: All inline scripts catalogued with function names and template variable dependencies
   NEEDS: none

2. Create static/js directory structure
   DO: Create .orchestrator/server/static/js/ directory and __tests__/ subdirectory
   IN: none
   OUT: .orchestrator/server/static/js/__tests__/ directory structure
   DONE: Directories exist and are writable
   NEEDS: 1

3. Extract plan-list.js module
   DO: Extract inline script from plan_list.html into module with WebSocket connection, plan rendering, and polling logic; export testable functions; handle Jinja2 variables via data attributes or init function
   IN: .orchestrator/server/templates/plan_list.html
   OUT: .orchestrator/server/static/js/plan-list.js
   DONE: File contains exported functions for plan list functionality
   NEEDS: 2

4. Extract build-progress.js module
   DO: Extract inline script from build_progress.html into module with build status tracking, progress bar updates, and WebSocket handlers
   IN: .orchestrator/server/templates/build_progress.html
   OUT: .orchestrator/server/static/js/build-progress.js
   DONE: File contains exported functions for build progress functionality
   NEEDS: 2

5. Extract logs.js module
   DO: Extract inline script from logs.html into module with log streaming, auto-scroll, and filtering logic
   IN: .orchestrator/server/templates/logs.html
   OUT: .orchestrator/server/static/js/logs.js
   DONE: File contains exported functions for log handling
   NEEDS: 2

6. Extract chat.js module
   DO: Extract inline script from chat.html into module with message sending, WebSocket chat connection, and DOM update functions
   IN: .orchestrator/server/templates/chat.html
   OUT: .orchestrator/server/static/js/chat.js
   DONE: File contains exported functions for chat functionality
   NEEDS: 2

7. Extract static-analysis.js module
   DO: Extract inline script from static_analysis.html into module with analysis display and copy functionality
   IN: .orchestrator/server/templates/static_analysis.html
   OUT: .orchestrator/server/static/js/static-analysis.js
   DONE: File contains exported functions for static analysis display
   NEEDS: 2

8. Create common.js utilities module
   DO: Identify and extract shared code patterns (copy-to-clipboard, formatters, WebSocket helpers) into reusable module
   IN: All extracted JS files from steps 3-7
   OUT: .orchestrator/server/static/js/common.js
   DONE: Common utilities exported and imported by other modules
   NEEDS: 3, 4, 5, 6, 7

9. Update plan_list.html template
   DO: Remove inline script block, add script tag referencing /static/js/common.js and /static/js/plan-list.js, add data attributes for Jinja2 variables
   IN: .orchestrator/server/templates/plan_list.html, .orchestrator/server/static/js/plan-list.js
   OUT: .orchestrator/server/templates/plan_list.html (modified)
   DONE: Template has no inline script, references external JS files correctly
   NEEDS: 3, 8

10. Update build_progress.html template
    DO: Remove inline script block, add script tag referencing external JS files, add data attributes for Jinja2 variables
    IN: .orchestrator/server/templates/build_progress.html, .orchestrator/server/static/js/build-progress.js
    OUT: .orchestrator/server/templates/build_progress.html (modified)
    DONE: Template has no inline script, references external JS files correctly
    NEEDS: 4, 8

11. Update logs.html template
    DO: Remove inline script block, add script tag referencing external JS files, add data attributes for Jinja2 variables
    IN: .orchestrator/server/templates/logs.html, .orchestrator/server/static/js/logs.js
    OUT: .orchestrator/server/templates/logs.html (modified)
    DONE: Template has no inline script, references external JS files correctly
    NEEDS: 5, 8

12. Update chat.html template
    DO: Remove inline script block, add script tag referencing external JS files, add data attributes for Jinja2 variables
    IN: .orchestrator/server/templates/chat.html, .orchestrator/server/static/js/chat.js
    OUT: .orchestrator/server/templates/chat.html (modified)
    DONE: Template has no inline script, references external JS files correctly
    NEEDS: 6, 8

13. Update static_analysis.html template
    DO: Remove inline script block, add script tag referencing external JS files, add data attributes for Jinja2 variables
    IN: .orchestrator/server/templates/static_analysis.html, .orchestrator/server/static/js/static-analysis.js
    OUT: .orchestrator/server/templates/static_analysis.html (modified)
    DONE: Template has no inline script, references external JS files correctly
    NEEDS: 7, 8

14. Update package.json with Jest dependencies
    DO: Add jest, jest-environment-jsdom, and @types/jest to devDependencies; add "test": "jest" and "test:watch": "jest --watch" scripts
    IN: package.json
    OUT: package.json (modified)
    DONE: npm install succeeds, jest command available
    NEEDS: none

15. Create jest.config.js configuration
    DO: Create Jest config with jsdom environment, testMatch for __tests__/*.test.js, moduleNameMapper for static assets, setupFilesAfterEnv if needed
    IN: none
    OUT: jest.config.js
    DONE: npx jest --showConfig runs without errors
    NEEDS: 14

16. Create common.test.js unit tests
    DO: Write tests for shared utilities including copy-to-clipboard mock, formatters, and helper functions
    IN: .orchestrator/server/static/js/common.js
    OUT: .orchestrator/server/static/js/__tests__/common.test.js
    DONE: npx jest common.test.js passes
    NEEDS: 8, 15

17. Create plan-list.test.js unit tests
    DO: Write tests for plan rendering functions, polling logic, and WebSocket message handlers with mocked WebSocket
    IN: .orchestrator/server/static/js/plan-list.js
    OUT: .orchestrator/server/static/js/__tests__/plan-list.test.js
    DONE: npx jest plan-list.test.js passes
    NEEDS: 3, 15

18. Create build-progress.test.js unit tests
    DO: Write tests for progress bar updates, status tracking, and WebSocket handlers with DOM mocking
    IN: .orchestrator/server/static/js/build-progress.js
    OUT: .orchestrator/server/static/js/__tests__/build-progress.test.js
    DONE: npx jest build-progress.test.js passes
    NEEDS: 4, 15

19. Create logs.test.js unit tests
    DO: Write tests for log streaming, auto-scroll behavior, and filtering logic
    IN: .orchestrator/server/static/js/logs.js
    OUT: .orchestrator/server/static/js/__tests__/logs.test.js
    DONE: npx jest logs.test.js passes
    NEEDS: 5, 15

20. Create chat.test.js unit tests
    DO: Write tests for message sending, WebSocket chat handlers, and DOM update functions
    IN: .orchestrator/server/static/js/chat.js
    OUT: .orchestrator/server/static/js/__tests__/chat.test.js
    DONE: npx jest chat.test.js passes
    NEEDS: 6, 15

21. Verify no inline scripts remain in templates
    DO: Scan all HTML templates in .orchestrator/server/templates/ for any remaining inline script tags (excluding external script references)
    IN: All files in .orchestrator/server/templates/
    OUT: Verification report confirming no inline scripts
    DONE: grep for inline scripts returns no matches except src= references
    NEEDS: 9, 10, 11, 12, 13

## Verify

- npm test runs all Jest tests successfully with 0 failures
- grep -r "<script>" .orchestrator/server/templates/ shows only external script references (src=)
- All 7 JS modules exist in .orchestrator/server/static/js/
- All 5 test files exist in .orchestrator/server/static/js/__tests__/
- npx playwright test still passes (existing E2E tests unbroken)
