# Plan: Extract inline JavaScript from server/templates/*.html into separate .js files in server/static/js/. Add Jest for testing. Create package.json with jest dependency, configure Jest, and add unit tests for extracted JS functions.

> Generated: 2026-01-15 00:32
> Complexity: medium
> Depth: moderate

## Context

```json
{
  "project_type": "webapp",
  "tech_stack": {
    "languages": ["python", "javascript", "html"],
    "frameworks": ["fastapi", "jinja2", "htmx", "tailwindcss"],
    "tools": ["uv", "pytest", "uvicorn"]
  },
  "relevant_files": [
    {
      "path": ".orchestrator/server/templates/base.html",
      "purpose": "Base template with SidePopup JavaScript component - extract to separate file",
      "relevance": "high",
      "action_needed": "modify"
    },
    {
      "path": ".orchestrator/server/templates/dashboard.html",
      "purpose": "Dashboard with inline JS for plan form submission - extract to separate file",
      "relevance": "high",
      "action_needed": "modify"
    },
    {
      "path": ".orchestrator/server/templates/plans.html",
      "purpose": "Plans page with inline JS for expand/collapse and file open - extract to separate file",
      "relevance": "high",
      "action_needed": "modify"
    },
    {
      "path": ".orchestrator/server/templates/plan_detail.html",
      "purpose": "Plan detail with inline JS for build/review actions - extract to separate file",
      "relevance": "high",
      "action_needed": "modify"
    },
    {
      "path": ".orchestrator/server/templates/run_detail.html",
      "purpose": "Run detail with inline JS for SSE event streaming - extract to separate file",
      "relevance": "high",
      "action_needed": "modify"
    },
    {
      "path": ".orchestrator/server/templates/runs.html",
      "purpose": "Runs list page with no inline JS - reference only",
      "relevance": "low",
      "action_needed": "none"
    },
    {
      "path": ".orchestrator/server/static/js/",
      "purpose": "Target directory for extracted JS files - currently empty",
      "relevance": "high",
      "action_needed": "modify"
    },
    {
      "path": ".orchestrator/server/app.py",
      "purpose": "FastAPI app - already mounts /static directory, no changes needed",
      "relevance": "medium",
      "action_needed": "reference"
    },
    {
      "path": ".orchestrator/pyproject.toml",
      "purpose": "Python project config - has pytest configured, but no Node.js/Jest config",
      "relevance": "medium",
      "action_needed": "reference"
    }
  ],
  "patterns": [
    {
      "name": "Jinja2 template blocks",
      "description": "Templates use {% block scripts %}{% endblock %} for page-specific JS",
      "example_file": ".orchestrator/server/templates/base.html",
      "must_follow": true
    },
    {
      "name": "Static files mounting",
      "description": "FastAPI mounts /static at .orchestrator/server/static/, already configured",
      "example_file": ".orchestrator/server/app.py",
      "must_follow": true
    },
    {
      "name": "Global SidePopup component",
      "description": "SidePopup object defined in base.html used across multiple pages",
      "example_file": ".orchestrator/server/templates/base.html",
      "must_follow": true
    }
  ],
  "dependencies": {
    "internal": [
      {
        "module": ".orchestrator/server/static/",
        "impact": "Already exists and mounted - create js/ subdirectory for extracted files"
      },
      {
        "module": "SidePopup global object",
        "impact": "Used by plans.html openFile() - must remain accessible after extraction"
      }
    ],
    "external": [
      {
        "package": "jest",
        "usage": "New dependency needed for JavaScript unit testing"
      },
      {
        "package": "@babel/preset-env",
        "usage": "May be needed for ES6 module support in Jest"
      }
    ]
  },
  "considerations": [
    {
      "type": "constraint",
      "description": "No existing package.json or Node.js tooling - need to create from scratch",
      "severity": "medium"
    },
    {
      "type": "constraint",
      "description": "JavaScript uses ES6 features (async/await, const, arrow functions) - Jest config must support this",
      "severity": "medium"
    },
    {
      "type": "risk",
      "description": "SidePopup is a global object initialized on DOMContentLoaded - extracted JS must maintain this pattern",
      "severity": "high"
    },
    {
      "type": "edge_case",
      "description": "run_detail.html uses template variable interpolation ({{ run.status }}) in JS - must handle server-side values",
      "severity": "high"
    },
    {
      "type": "note",
      "description": "Static directory exists but is empty - js/ subdirectory needs to be created",
      "severity": "low"
    },
    {
      "type": "note",
      "description": "Some JS functions are page-specific and reference DOM IDs that only exist on that page",
      "severity": "medium"
    }
  ],
  "summary": "This is a FastAPI web application using Jinja2 templates with inline JavaScript in 5 HTML template files under .orchestrator/server/templates/. The JS includes: SidePopup component (base.html), plan form submission (dashboard.html), expand/collapse functionality (plans.html), build/review actions (plan_detail.html), and SSE event streaming (run_detail.html). The static file serving is already configured at /static. No Node.js tooling exists - package.json, jest.config.js, and the js/ directory all need to be created. Key challenge: some inline JS uses Jinja2 template variables (e.g., {{ run.status }}) that must be handled via data attributes or inline script variables when extracting to external files."
}
```

---

## Architecture

```json
{
  "approach": {
    "summary": "Extract inline JavaScript from 5 template files into modular .js files, handle Jinja2 template variables via data attributes, and add Jest testing infrastructure",
    "rationale": "Modular extraction allows testability while maintaining the existing global patterns (SidePopup). Data attributes bridge server-side values to client-side JS without breaking extraction.",
    "complexity": "moderate"
  },
  "components": [
    {
      "name": "SidePopup Module",
      "type": "util",
      "file_path": ".orchestrator/server/static/js/side-popup.js",
      "action": "create",
      "responsibility": "Global SidePopup component for panel show/hide functionality",
      "interfaces": {
        "inputs": ["contentUrl: string"],
        "outputs": ["SidePopup global object with show(), hide(), toggle() methods"]
      }
    },
    {
      "name": "Dashboard Module",
      "type": "util",
      "file_path": ".orchestrator/server/static/js/dashboard.js",
      "action": "create",
      "responsibility": "Plan form submission handling with validation",
      "interfaces": {
        "inputs": ["form submit event"],
        "outputs": ["POST request to /plans endpoint"]
      }
    },
    {
      "name": "Plans Module",
      "type": "util",
      "file_path": ".orchestrator/server/static/js/plans.js",
      "action": "create",
      "responsibility": "Expand/collapse plan steps and file open via SidePopup",
      "interfaces": {
        "inputs": ["click events on plan rows", "file path string"],
        "outputs": ["DOM toggle, SidePopup.show() call"]
      }
    },
    {
      "name": "Plan Detail Module",
      "type": "util",
      "file_path": ".orchestrator/server/static/js/plan-detail.js",
      "action": "create",
      "responsibility": "Build and review action button handlers",
      "interfaces": {
        "inputs": ["button click events", "plan ID from data attribute"],
        "outputs": ["POST requests to build/review endpoints"]
      }
    },
    {
      "name": "Run Detail Module",
      "type": "util",
      "file_path": ".orchestrator/server/static/js/run-detail.js",
      "action": "create",
      "responsibility": "SSE event streaming for run status updates",
      "interfaces": {
        "inputs": ["run ID from data attribute", "initial status from data attribute"],
        "outputs": ["DOM updates for status, output streaming"]
      }
    },
    {
      "name": "Base Template",
      "type": "config",
      "file_path": ".orchestrator/server/templates/base.html",
      "action": "modify",
      "responsibility": "Replace inline SidePopup JS with script tag, keep block scripts pattern",
      "interfaces": {
        "inputs": [],
        "outputs": ["<script src='/static/js/side-popup.js'>"]
      }
    },
    {
      "name": "Dashboard Template",
      "type": "config",
      "file_path": ".orchestrator/server/templates/dashboard.html",
      "action": "modify",
      "responsibility": "Replace inline JS with external script reference in scripts block",
      "interfaces": {
        "inputs": [],
        "outputs": ["<script src='/static/js/dashboard.js'>"]
      }
    },
    {
      "name": "Plans Template",
      "type": "config",
      "file_path": ".orchestrator/server/templates/plans.html",
      "action": "modify",
      "responsibility": "Replace inline JS with external script reference",
      "interfaces": {
        "inputs": [],
        "outputs": ["<script src='/static/js/plans.js'>"]
      }
    },
    {
      "name": "Plan Detail Template",
      "type": "config",
      "file_path": ".orchestrator/server/templates/plan_detail.html",
      "action": "modify",
      "responsibility": "Add data-plan-id attribute, replace inline JS with external script",
      "interfaces": {
        "inputs": [],
        "outputs": ["data-plan-id='{{ plan.id }}' on container element"]
      }
    },
    {
      "name": "Run Detail Template",
      "type": "config",
      "file_path": ".orchestrator/server/templates/run_detail.html",
      "action": "modify",
      "responsibility": "Add data-run-id and data-run-status attributes, replace inline JS",
      "interfaces": {
        "inputs": [],
        "outputs": ["data-run-id='{{ run.id }}', data-run-status='{{ run.status }}'"]
      }
    },
    {
      "name": "Package.json",
      "type": "config",
      "file_path": ".orchestrator/package.json",
      "action": "create",
      "responsibility": "Node.js project config with Jest dependency",
      "interfaces": {
        "inputs": [],
        "outputs": ["jest ^29.x dependency, test script"]
      }
    },
    {
      "name": "Jest Config",
      "type": "config",
      "file_path": ".orchestrator/jest.config.js",
      "action": "create",
      "responsibility": "Jest configuration for ES6 and jsdom environment",
      "interfaces": {
        "inputs": [],
        "outputs": ["testEnvironment: jsdom, testMatch pattern"]
      }
    },
    {
      "name": "SidePopup Tests",
      "type": "test",
      "file_path": ".orchestrator/server/static/js/__tests__/side-popup.test.js",
      "action": "create",
      "responsibility": "Unit tests for SidePopup show/hide/toggle methods",
      "interfaces": {
        "inputs": ["mock DOM"],
        "outputs": ["test results"]
      }
    },
    {
      "name": "Plans Tests",
      "type": "test",
      "file_path": ".orchestrator/server/static/js/__tests__/plans.test.js",
      "action": "create",
      "responsibility": "Unit tests for expand/collapse and openFile functions",
      "interfaces": {
        "inputs": ["mock DOM", "mock SidePopup"],
        "outputs": ["test results"]
      }
    },
    {
      "name": "Dashboard Tests",
      "type": "test",
      "file_path": ".orchestrator/server/static/js/__tests__/dashboard.test.js",
      "action": "create",
      "responsibility": "Unit tests for form submission and validation",
      "interfaces": {
        "inputs": ["mock DOM", "mock fetch"],
        "outputs": ["test results"]
      }
    }
  ],
  "data_flow": [
    {
      "step": 1,
      "from": "Jinja2 Template",
      "to": "HTML data attributes",
      "data": "Server-side values (run.id, run.status, plan.id)",
      "description": "Template renders dynamic values into data-* attributes on container elements"
    },
    {
      "step": 2,
      "from": "Browser",
      "to": "External JS files",
      "data": "Script load via <script src>",
      "description": "base.html loads side-popup.js first, page-specific scripts load in scripts block"
    },
    {
      "step": 3,
      "from": "External JS",
      "to": "DOM data attributes",
      "data": "element.dataset.runId, element.dataset.runStatus",
      "description": "JS reads server values from data attributes at runtime"
    },
    {
      "step": 4,
      "from": "Jest test runner",
      "to": "JS modules",
      "data": "Function imports or global object access",
      "description": "Tests import/access functions and verify behavior with mock DOM"
    }
  ],
  "technical_decisions": [
    {
      "decision": "Use data attributes for Jinja2 template variable bridging",
      "alternatives": ["Inline script block with variables", "Window global injection"],
      "rationale": "Data attributes are standard HTML, testable without server, and keep JS fully external",
      "trade_offs": "Slightly more verbose HTML, requires DOM query to read values"
    },
    {
      "decision": "Keep SidePopup as global object pattern",
      "alternatives": ["ES6 module export/import", "Custom element"],
      "rationale": "Maintains backward compatibility, works without bundler, matches existing usage pattern",
      "trade_offs": "Not true module isolation, but simpler for this codebase size"
    },
    {
      "decision": "Place Jest config at .orchestrator/ level alongside pyproject.toml",
      "alternatives": ["Root level package.json", "server/static/js/package.json"],
      "rationale": "Keeps JS tooling scoped to orchestrator project, matches Python project structure",
      "trade_offs": "Need to run npm commands from .orchestrator/ directory"
    }
  ],
  "integration_points": [
    {
      "component": ".orchestrator/server/app.py",
      "external_system": "FastAPI StaticFiles",
      "protocol": "HTTP /static/* routing",
      "notes": "Already configured - no changes needed, JS files auto-served from static/js/"
    },
    {
      "component": ".orchestrator/server/static/js/run-detail.js",
      "external_system": "Server-Sent Events endpoint",
      "protocol": "EventSource API",
      "notes": "Existing SSE endpoint unchanged, JS just moves to external file"
    }
  ],
  "open_questions": [
    {
      "question": "Should extracted JS use ES6 modules (export/import) or global IIFE pattern?",
      "impact": "medium",
      "suggested_resolution": "Use IIFE with global assignment for simplicity - avoids bundler requirement while still being testable"
    }
  ]
}
```

---

## Implementation Steps

## Implementation Steps

### Phase 1: Setup
> Node.js tooling and Jest configuration

#### Step 1.1: create .orchestrator/package.json
**Action:** create
**Target:** .orchestrator/package.json
**Dependencies:** none
**Parallel:** setup
**Description:** Create Node.js project config with Jest and jsdom dependencies

```json
{
  "name": "orchestrator-frontend",
  "version": "1.0.0",
  "description": "Frontend JavaScript for orchestrator web UI",
  "scripts": {
    "test": "jest",
    "test:watch": "jest --watch",
    "test:coverage": "jest --coverage"
  },
  "devDependencies": {
    "jest": "^29.7.0",
    "jest-environment-jsdom": "^29.7.0"
  }
}
```

#### Step 1.2: create .orchestrator/jest.config.js
**Action:** create
**Target:** .orchestrator/jest.config.js
**Dependencies:** none
**Parallel:** setup
**Description:** Configure Jest for jsdom environment and test file location

```javascript
module.exports = {
  testEnvironment: 'jsdom',
  roots: ['<rootDir>/server/static/js'],
  testMatch: ['**/__tests__/**/*.test.js'],
  moduleFileExtensions: ['js'],
  collectCoverageFrom: [
    'server/static/js/**/*.js',
    '!server/static/js/__tests__/**'
  ],
  verbose: true
};
```

### Phase 2: Core Implementation
> Extract inline JavaScript to external files

#### Step 2.1: create .orchestrator/server/static/js/side-popup.js
**Action:** create
**Target:** .orchestrator/server/static/js/side-popup.js
**Dependencies:** none
**Parallel:** js-extract
**Description:** Extract SidePopup component from base.html into standalone module

```javascript
/**
 * SidePopup - Global side panel component for displaying content
 */
(function() {
    'use strict';

    const SidePopup = {
        panel: null,
        contentFrame: null,
        isOpen: false,

        init: function() {
            this.panel = document.getElementById('side-popup');
            this.contentFrame = document.getElementById('side-popup-content');
            
            // Close on escape key
            document.addEventListener('keydown', (e) => {
                if (e.key === 'Escape' && this.isOpen) {
                    this.hide();
                }
            });

            // Close on overlay click
            const overlay = document.getElementById('side-popup-overlay');
            if (overlay) {
                overlay.addEventListener('click', () => this.hide());
            }
        },

        show: function(contentUrl) {
            if (!this.panel || !this.contentFrame) {
                console.error('SidePopup not initialized');
                return;
            }
            
            this.contentFrame.src = contentUrl;
            this.panel.classList.remove('hidden');
            this.panel.classList.add('open');
            this.isOpen = true;
            document.body.style.overflow = 'hidden';
        },

        hide: function() {
            if (!this.panel) return;
            
            this.panel.classList.add('hidden');
            this.panel.classList.remove('open');
            this.isOpen = false;
            document.body.style.overflow = '';
            
            if (this.contentFrame) {
                this.contentFrame.src = 'about:blank';
            }
        },

        toggle: function(contentUrl) {
            if (this.isOpen) {
                this.hide();
            } else {
                this.show(contentUrl);
            }
        }
    };

    // Initialize on DOM ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => SidePopup.init());
    } else {
        SidePopup.init();
    }

    // Export globally
    window.SidePopup = SidePopup;
})();
```

#### Step 2.2: create .orchestrator/server/static/js/dashboard.js
**Action:** create
**Target:** .orchestrator/server/static/js/dashboard.js
**Dependencies:** none
**Parallel:** js-extract
**Description:** Extract plan form submission handling from dashboard.html

```javascript
/**
 * Dashboard - Plan creation form handling
 */
(function() {
    'use strict';

    const Dashboard = {
        form: null,
        submitButton: null,
        requestInput: null,

        init: function() {
            this.form = document.getElementById('plan-form');
            this.submitButton = document.getElementById('submit-plan');
            this.requestInput = document.getElementById('request-input');

            if (this.form) {
                this.form.addEventListener('submit', (e) => this.handleSubmit(e));
            }
        },

        handleSubmit: async function(e) {
            e.preventDefault();

            const request = this.requestInput?.value?.trim();
            if (!request) {
                this.showError('Please enter a request');
                return;
            }

            this.setLoading(true);

            try {
                const response = await fetch('/plans', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ request: request })
                });

                if (response.ok) {
                    const data = await response.json();
                    window.location.href = `/plans/${data.id}`;
                } else {
                    const error = await response.json();
                    this.showError(error.detail || 'Failed to create plan');
                }
            } catch (err) {
                this.showError('Network error: ' + err.message);
            } finally {
                this.setLoading(false);
            }
        },

        setLoading: function(loading) {
            if (this.submitButton) {
                this.submitButton.disabled = loading;
                this.submitButton.textContent = loading ? 'Creating...' : 'Create Plan';
            }
        },

        showError: function(message) {
            const errorEl = document.getElementById('form-error');
            if (errorEl) {
                errorEl.textContent = message;
                errorEl.classList.remove('hidden');
            } else {
                alert(message);
            }
        }
    };

    // Initialize on DOM ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => Dashboard.init());
    } else {
        Dashboard.init();
    }

    // Export for testing
    window.Dashboard = Dashboard;
})();
```

#### Step 2.3: create .orchestrator/server/static/js/plans.js
**Action:** create
**Target:** .orchestrator/server/static/js/plans.js
**Dependencies:** none
**Parallel:** js-extract
**Description:** Extract expand/collapse and file open functionality from plans.html

```javascript
/**
 * Plans - Plan list expand/collapse and file viewer
 */
(function() {
    'use strict';

    const Plans = {
        init: function() {
            // Attach click handlers to expandable rows
            const expandableRows = document.querySelectorAll('[data-expandable]');
            expandableRows.forEach(row => {
                row.addEventListener('click', (e) => {
                    // Don't toggle if clicking a link or button
                    if (e.target.tagName === 'A' || e.target.tagName === 'BUTTON') {
                        return;
                    }
                    this.toggleExpand(row);
                });
            });
        },

        toggleExpand: function(element) {
            const targetId = element.dataset.expandable;
            const target = document.getElementById(targetId);
            
            if (!target) return;

            const isExpanded = !target.classList.contains('hidden');
            
            if (isExpanded) {
                target.classList.add('hidden');
                element.classList.remove('expanded');
                element.setAttribute('aria-expanded', 'false');
            } else {
                target.classList.remove('hidden');
                element.classList.add('expanded');
                element.setAttribute('aria-expanded', 'true');
            }
        },

        openFile: function(filePath) {
            if (!filePath) {
                console.error('No file path provided');
                return;
            }

            const encodedPath = encodeURIComponent(filePath);
            const url = `/files/view?path=${encodedPath}`;
            
            if (window.SidePopup) {
                window.SidePopup.show(url);
            } else {
                // Fallback: open in new tab
                window.open(url, '_blank');
            }
        }
    };

    // Initialize on DOM ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => Plans.init());
    } else {
        Plans.init();
    }

    // Export globally (openFile called from onclick attributes)
    window.Plans = Plans;
    window.openFile = (path) => Plans.openFile(path);
})();
```

#### Step 2.4: create .orchestrator/server/static/js/plan-detail.js
**Action:** create
**Target:** .orchestrator/server/static/js/plan-detail.js
**Dependencies:** none
**Parallel:** js-extract
**Description:** Extract build and review action handlers from plan_detail.html

```javascript
/**
 * PlanDetail - Build and review action handlers
 */
(function() {
    'use strict';

    const PlanDetail = {
        planId: null,
        buildButton: null,
        reviewButton: null,

        init: function() {
            // Get plan ID from data attribute
            const container = document.querySelector('[data-plan-id]');
            if (container) {
                this.planId = container.dataset.planId;
            }

            this.buildButton = document.getElementById('build-btn');
            this.reviewButton = document.getElementById('review-btn');

            if (this.buildButton) {
                this.buildButton.addEventListener('click', () => this.startBuild());
            }

            if (this.reviewButton) {
                this.reviewButton.addEventListener('click', () => this.startReview());
            }
        },

        startBuild: async function() {
            if (!this.planId) {
                console.error('No plan ID found');
                return;
            }

            this.setButtonLoading(this.buildButton, true, 'Building...');

            try {
                const response = await fetch(`/plans/${this.planId}/build`, {
                    method: 'POST'
                });

                if (response.ok) {
                    const data = await response.json();
                    window.location.href = `/runs/${data.run_id}`;
                } else {
                    const error = await response.json();
                    alert(error.detail || 'Failed to start build');
                }
            } catch (err) {
                alert('Network error: ' + err.message);
            } finally {
                this.setButtonLoading(this.buildButton, false, 'Build');
            }
        },

        startReview: async function() {
            if (!this.planId) {
                console.error('No plan ID found');
                return;
            }

            this.setButtonLoading(this.reviewButton, true, 'Starting Review...');

            try {
                const response = await fetch(`/plans/${this.planId}/review`, {
                    method: 'POST'
                });

                if (response.ok) {
                    const data = await response.json();
                    window.location.href = `/runs/${data.run_id}`;
                } else {
                    const error = await response.json();
                    alert(error.detail || 'Failed to start review');
                }
            } catch (err) {
                alert('Network error: ' + err.message);
            } finally {
                this.setButtonLoading(this.reviewButton, false, 'Review');
            }
        },

        setButtonLoading: function(button, loading, text) {
            if (!button) return;
            button.disabled = loading;
            button.textContent = text;
        }
    };

    // Initialize on DOM ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => PlanDetail.init());
    } else {
        PlanDetail.init();
    }

    // Export for testing
    window.PlanDetail = PlanDetail;
})();
```

#### Step 2.5: create .orchestrator/server/static/js/run-detail.js
**Action:** create
**Target:** .orchestrator/server/static/js/run-detail.js
**Dependencies:** none
**Parallel:** js-extract
**Description:** Extract SSE event streaming from run_detail.html with data attribute support

```javascript
/**
 * RunDetail - Server-Sent Events streaming for run status
 */
(function() {
    'use strict';

    const RunDetail = {
        runId: null,
        initialStatus: null,
        eventSource: null,
        outputContainer: null,
        statusBadge: null,

        init: function() {
            // Get run data from data attributes
            const container = document.querySelector('[data-run-id]');
            if (!container) return;

            this.runId = container.dataset.runId;
            this.initialStatus = container.dataset.runStatus;
            this.outputContainer = document.getElementById('run-output');
            this.statusBadge = document.getElementById('status-badge');

            // Only start streaming for active runs
            if (this.isActiveStatus(this.initialStatus)) {
                this.startStreaming();
            }
        },

        isActiveStatus: function(status) {
            return status === 'running' || status === 'pending';
        },

        startStreaming: function() {
            if (!this.runId) return;

            const url = `/runs/${this.runId}/stream`;
            this.eventSource = new EventSource(url);

            this.eventSource.onmessage = (event) => {
                this.handleMessage(event.data);
            };

            this.eventSource.addEventListener('status', (event) => {
                this.handleStatusUpdate(event.data);
            });

            this.eventSource.addEventListener('output', (event) => {
                this.appendOutput(event.data);
            });

            this.eventSource.addEventListener('complete', (event) => {
                this.handleComplete(event.data);
            });

            this.eventSource.onerror = (err) => {
                console.error('SSE error:', err);
                this.stopStreaming();
            };
        },

        stopStreaming: function() {
            if (this.eventSource) {
                this.eventSource.close();
                this.eventSource = null;
            }
        },

        handleMessage: function(data) {
            try {
                const parsed = JSON.parse(data);
                if (parsed.output) {
                    this.appendOutput(parsed.output);
                }
                if (parsed.status) {
                    this.updateStatus(parsed.status);
                }
            } catch (e) {
                // Plain text message
                this.appendOutput(data);
            }
        },

        handleStatusUpdate: function(status) {
            this.updateStatus(status);
        },

        handleComplete: function(data) {
            try {
                const parsed = JSON.parse(data);
                this.updateStatus(parsed.status || 'completed');
            } catch (e) {
                this.updateStatus('completed');
            }
            this.stopStreaming();
        },

        updateStatus: function(status) {
            if (this.statusBadge) {
                this.statusBadge.textContent = status;
                this.statusBadge.className = 'status-badge status-' + status;
            }
        },

        appendOutput: function(text) {
            if (this.outputContainer) {
                this.outputContainer.textContent += text;
                // Auto-scroll to bottom
                this.outputContainer.scrollTop = this.outputContainer.scrollHeight;
            }
        }
    };

    // Initialize on DOM ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => RunDetail.init());
    } else {
        RunDetail.init();
    }

    // Cleanup on page unload
    window.addEventListener('beforeunload', () => RunDetail.stopStreaming());

    // Export for testing
    window.RunDetail = RunDetail;
})();
```

#### Step 2.6: modify .orchestrator/server/templates/base.html
**Action:** modify
**Target:** .orchestrator/server/templates/base.html
**Dependencies:** Step 2.1
**Description:** Replace inline SidePopup JS with external script reference

```html
<!-- Find and remove the inline <script> block containing SidePopup definition -->
<!-- Replace it with: -->
<script src="/static/js/side-popup.js"></script>

<!-- Keep the existing {% block scripts %}{% endblock %} pattern intact -->
```

#### Step 2.7: modify .orchestrator/server/templates/dashboard.html
**Action:** modify
**Target:** .orchestrator/server/templates/dashboard.html
**Dependencies:** Step 2.2
**Description:** Replace inline form JS with external script in scripts block

```html
<!-- In {% block scripts %} section, replace inline JS with: -->
{% block scripts %}
<script src="/static/js/dashboard.js"></script>
{% endblock %}
```

#### Step 2.8: modify .orchestrator/server/templates/plans.html
**Action:** modify
**Target:** .orchestrator/server/templates/plans.html
**Dependencies:** Step 2.3
**Description:** Replace inline expand/collapse JS with external script

```html
<!-- In {% block scripts %} section, replace inline JS with: -->
{% block scripts %}
<script src="/static/js/plans.js"></script>
{% endblock %}
```

#### Step 2.9: modify .orchestrator/server/templates/plan_detail.html
**Action:** modify
**Target:** .orchestrator/server/templates/plan_detail.html
**Dependencies:** Step 2.4
**Description:** Add data-plan-id attribute and replace inline JS with external script

```html
<!-- Add data attribute to the main container element: -->
<div class="plan-detail-container" data-plan-id="{{ plan.id }}">

<!-- In {% block scripts %} section, replace inline JS with: -->
{% block scripts %}
<script src="/static/js/plan-detail.js"></script>
{% endblock %}
```

#### Step 2.10: modify .orchestrator/server/templates/run_detail.html
**Action:** modify
**Target:** .orchestrator/server/templates/run_detail.html
**Dependencies:** Step 2.5
**Description:** Add data attributes for run ID and status, replace inline JS

```html
<!-- Add data attributes to the main container element: -->
<div class="run-detail-container" data-run-id="{{ run.id }}" data-run-status="{{ run.status }}">

<!-- In {% block scripts %} section, replace inline JS with: -->
{% block scripts %}
<script src="/static/js/run-detail.js"></script>
{% endblock %}
```

### Phase 3: Testing
> Jest unit tests for extracted JavaScript

#### Step 3.1: create .orchestrator/server/static/js/__tests__/side-popup.test.js
**Action:** create
**Target:** .orchestrator/server/static/js/__tests__/side-popup.test.js
**Dependencies:** Step 2.1
**Parallel:** tests
**Description:** Unit tests for SidePopup show/hide/toggle methods

```javascript
/**
 * @jest-environment jsdom
 */

describe('SidePopup', () => {
    let SidePopup;

    beforeEach(() => {
        // Reset DOM
        document.body.innerHTML = `
            <div id="side-popup" class="hidden">
                <iframe id="side-popup-content" src="about:blank"></iframe>
            </div>
            <div id="side-popup-overlay"></div>
        `;

        // Clear module cache and reload
        jest.resetModules();
        delete window.SidePopup;
        
        // Load the module
        require('../side-popup.js');
        SidePopup = window.SidePopup;
    });

    test('init sets up panel and contentFrame references', () => {
        expect(SidePopup.panel).toBe(document.getElementById('side-popup'));
        expect(SidePopup.contentFrame).toBe(document.getElementById('side-popup-content'));
    });

    test('show opens panel and sets iframe src', () => {
        SidePopup.show('/test/url');

        expect(SidePopup.isOpen).toBe(true);
        expect(SidePopup.panel.classList.contains('hidden')).toBe(false);
        expect(SidePopup.panel.classList.contains('open')).toBe(true);
        expect(SidePopup.contentFrame.src).toContain('/test/url');
        expect(document.body.style.overflow).toBe('hidden');
    });

    test('hide closes panel and resets iframe', () => {
        SidePopup.show('/test/url');
        SidePopup.hide();

        expect(SidePopup.isOpen).toBe(false);
        expect(SidePopup.panel.classList.contains('hidden')).toBe(true);
        expect(SidePopup.panel.classList.contains('open')).toBe(false);
        expect(SidePopup.contentFrame.src).toContain('about:blank');
        expect(document.body.style.overflow).toBe('');
    });

    test('toggle opens when closed', () => {
        SidePopup.toggle('/test/url');

        expect(SidePopup.isOpen).toBe(true);
    });

    test('toggle closes when open', () => {
        SidePopup.show('/test/url');
        SidePopup.toggle('/test/url');

        expect(SidePopup.isOpen).toBe(false);
    });

    test('escape key closes popup', () => {
        SidePopup.show('/test/url');
        
        const event = new KeyboardEvent('keydown', { key: 'Escape' });
        document.dispatchEvent(event);

        expect(SidePopup.isOpen).toBe(false);
    });

    test('overlay click closes popup', () => {
        SidePopup.show('/test/url');
        
        const overlay = document.getElementById('side-popup-overlay');
        overlay.click();

        expect(SidePopup.isOpen).toBe(false);
    });
});
```

#### Step 3.2: create .orchestrator/server/static/js/__tests__/plans.test.js
**Action:** create
**Target:** .orchestrator/server/static/js/__tests__/plans.test.js
**Dependencies:** Step 2.3
**Parallel:** tests
**Description:** Unit tests for expand/collapse and openFile functions

```javascript
/**
 * @jest-environment jsdom
 */

describe('Plans', () => {
    let Plans;

    beforeEach(() => {
        document.body.innerHTML = `
            <div data-expandable="details-1" aria-expanded="false">
                Plan Row 1
            </div>
            <div id="details-1" class="hidden">
                Plan details content
            </div>
        `;

        // Mock SidePopup
        window.SidePopup = {
            show: jest.fn()
        };

        jest.resetModules();
        delete window.Plans;
        delete window.openFile;

        require('../plans.js');
        Plans = window.Plans;
    });

    afterEach(() => {
        delete window.SidePopup;
    });

    test('toggleExpand shows hidden content', () => {
        const row = document.querySelector('[data-expandable]');
        const details = document.getElementById('details-1');

        Plans.toggleExpand(row);

        expect(details.classList.contains('hidden')).toBe(false);
        expect(row.classList.contains('expanded')).toBe(true);
        expect(row.getAttribute('aria-expanded')).toBe('true');
    });

    test('toggleExpand hides visible content', () => {
        const row = document.querySelector('[data-expandable]');
        const details = document.getElementById('details-1');

        // First expand
        Plans.toggleExpand(row);
        // Then collapse
        Plans.toggleExpand(row);

        expect(details.classList.contains('hidden')).toBe(true);
        expect(row.classList.contains('expanded')).toBe(false);
        expect(row.getAttribute('aria-expanded')).toBe('false');
    });

    test('openFile calls SidePopup.show with encoded path', () => {
        Plans.openFile('/path/to/file.py');

        expect(window.SidePopup.show).toHaveBeenCalledWith(
            '/files/view?path=%2Fpath%2Fto%2Ffile.py'
        );
    });

    test('openFile handles path with spaces', () => {
        Plans.openFile('/path/to/my file.py');

        expect(window.SidePopup.show).toHaveBeenCalledWith(
            '/files/view?path=%2Fpath%2Fto%2Fmy%20file.py'
        );
    });

    test('openFile opens in new tab when SidePopup unavailable', () => {
        delete window.SidePopup;
        window.open = jest.fn();

        Plans.openFile('/path/to/file.py');

        expect(window.open).toHaveBeenCalledWith(
            '/files/view?path=%2Fpath%2Fto%2Ffile.py',
            '_blank'
        );
    });

    test('global openFile function works', () => {
        window.openFile('/test/path.js');

        expect(window.SidePopup.show).toHaveBeenCalled();
    });
});
```

#### Step 3.3: create .orchestrator/server/static/js/__tests__/dashboard.test.js
**Action:** create
**Target:** .orchestrator/server/static/js/__tests__/dashboard.test.js
**Dependencies:** Step 2.2
**Parallel:** tests
**Description:** Unit tests for form submission and validation

```javascript
/**
 * @jest-environment jsdom
 */

describe('Dashboard', () => {
    let Dashboard;

    beforeEach(() => {
        document.body.innerHTML = `
            <form id="plan-form">
                <textarea id="request-input"></textarea>
                <button id="submit-plan" type="submit">Create Plan</button>
                <div id="form-error" class="hidden"></div>
            </form>
        `;

        // Mock fetch
        global.fetch = jest.fn();

        jest.resetModules();
        delete window.Dashboard;

        require('../dashboard.js');
        Dashboard = window.Dashboard;
    });

    afterEach(() => {
        jest.restoreAllMocks();
    });

    test('init sets up form references', () => {
        expect(Dashboard.form).toBe(document.getElementById('plan-form'));
        expect(Dashboard.submitButton).toBe(document.getElementById('submit-plan'));
        expect(Dashboard.requestInput).toBe(document.getElementById('request-input'));
    });

    test('showError displays error message', () => {
        Dashboard.showError('Test error');

        const errorEl = document.getElementById('form-error');
        expect(errorEl.textContent).toBe('Test error');
        expect(errorEl.classList.contains('hidden')).toBe(false);
    });

    test('setLoading disables button and changes text', () => {
        Dashboard.setLoading(true);

        expect(Dashboard.submitButton.disabled).toBe(true);
        expect(Dashboard.submitButton.textContent).toBe('Creating...');
    });

    test('setLoading re-enables button', () => {
        Dashboard.setLoading(true);
        Dashboard.setLoading(false);

        expect(Dashboard.submitButton.disabled).toBe(false);
        expect(Dashboard.submitButton.textContent).toBe('Create Plan');
    });

    test('handleSubmit validates empty input', async () => {
        Dashboard.requestInput.value = '   ';
        const event = { preventDefault: jest.fn() };

        await Dashboard.handleSubmit(event);

        expect(event.preventDefault).toHaveBeenCalled();
        expect(global.fetch).not.toHaveBeenCalled();
        expect(document.getElementById('form-error').textContent).toBe('Please enter a request');
    });

    test('handleSubmit sends POST request with valid input', async () => {
        Dashboard.requestInput.value = 'Create a new feature';
        global.fetch.mockResolvedValueOnce({
            ok: true,
            json: async () => ({ id: '123' })
        });

        // Mock window.location
        delete window.location;
        window.location = { href: '' };

        const event = { preventDefault: jest.fn() };
        await Dashboard.handleSubmit(event);

        expect(global.fetch).toHaveBeenCalledWith('/plans', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ request: 'Create a new feature' })
        });
        expect(window.location.href).toBe('/plans/123');
    });

    test('handleSubmit shows error on failure', async () => {
        Dashboard.requestInput.value = 'Create a feature';
        global.fetch.mockResolvedValueOnce({
            ok: false,
            json: async () => ({ detail: 'Server error' })
        });

        const event = { preventDefault: jest.fn() };
        await Dashboard.handleSubmit(event);

        expect(document.getElementById('form-error').textContent).toBe('Server error');
    });
});
```

#### Step 3.4: run npm install
**Action:** run
**Target:** .orchestrator/
**Dependencies:** Step 1.1, Step 1.2
**Description:** Install Jest and dependencies

```bash
cd .orchestrator && npm install
```

#### Step 3.5: run npm test
**Action:** run
**Target:** .orchestrator/
**Dependencies:** Step 3.1, Step 3.2, Step 3.3, Step 3.4
**Description:** Run Jest tests to verify all extracted JS works correctly

```bash
cd .orchestrator && npm test
```

## Testing Strategy

| Test Type | File | What it verifies |
|-----------|------|------------------|
| Unit | __tests__/side-popup.test.js | SidePopup show/hide/toggle, keyboard/click handlers |
| Unit | __tests__/plans.test.js | Expand/collapse toggle, openFile with SidePopup and fallback |
| Unit | __tests__/dashboard.test.js | Form validation, POST request, error handling |

## Validation Commands

```bash
# Install dependencies
cd .orchestrator && npm install

# Run all tests
cd .orchestrator && npm test

# Run tests with coverage
cd .orchestrator && npm run test:coverage

# Start the server and verify scripts load
cd .orchestrator && uv run uvicorn server.app:app --reload

# Check browser console for any JS errors on each page:
# - http://localhost:8000/           (dashboard.js)
# - http://localhost:8000/plans      (plans.js)
# - http://localhost:8000/plans/{id} (plan-detail.js)
# - http://localhost:8000/runs/{id}  (run-detail.js)
```

---

## Validation

```json
{
  "status": "needs_revision",
  "score": 78,
  "checks": [
    {
      "name": "steps_have_actions",
      "passed": true,
      "details": "All 15 steps have valid actions (6 create, 5 modify, 2 run in Phase 3)",
      "severity": "critical"
    },
    {
      "name": "steps_have_targets",
      "passed": true,
      "details": "All steps specify exact file paths (e.g., .orchestrator/server/static/js/side-popup.js)",
      "severity": "critical"
    },
    {
      "name": "steps_have_code",
      "passed": false,
      "details": "Steps 2.6-2.10 (modify actions) have incomplete code snippets - they show only fragments with HTML comments indicating what to find/replace rather than complete before/after code blocks",
      "severity": "high"
    },
    {
      "name": "dependencies_valid",
      "passed": true,
      "details": "Dependency graph is valid: Phase 1 has no deps, Phase 2 JS files have no deps, template modifications depend on their JS files, Phase 3 tests depend on source files and npm install",
      "severity": "critical"
    },
    {
      "name": "testing_included",
      "passed": true,
      "details": "Phase 3 includes 3 test files and npm test commands",
      "severity": "high"
    },
    {
      "name": "validation_commands",
      "passed": true,
      "details": "Comprehensive validation commands provided: npm install, npm test, npm run test:coverage, server start, and manual browser checks",
      "severity": "medium"
    },
    {
      "name": "patterns_followed",
      "passed": true,
      "details": "IIFE module pattern used consistently across all JS files, Jest with jsdom environment configured correctly",
      "severity": "medium"
    },
    {
      "name": "no_vague_refs",
      "passed": false,
      "details": "Steps 2.6-2.10 contain vague instructions like 'Find and remove the inline <script> block' and 'Add data attribute to the main container element' without specifying exact line numbers or full context",
      "severity": "high"
    },
    {
      "name": "phases_ordered",
      "passed": true,
      "details": "Logical ordering: Phase 1 (Setup) → Phase 2 (Core Implementation) → Phase 3 (Testing)",
      "severity": "medium"
    },
    {
      "name": "no_placeholders",
      "passed": true,
      "details": "No TODO, TBD, or placeholder text found in code snippets",
      "severity": "critical"
    }
  ],
  "blocking_issues": [
    {
      "step": "Step 2.6",
      "issue": "Code snippet only shows replacement script tag with HTML comments - does not show the actual inline script to find/remove or complete modified file content",
      "fix_suggestion": "Provide the exact inline SidePopup script block that needs to be removed (first few lines to identify it) and show the complete {% block scripts %} section after modification"
    },
    {
      "step": "Step 2.7",
      "issue": "Code snippet assumes inline JS exists in scripts block but doesn't show what to replace",
      "fix_suggestion": "Show the existing inline JavaScript that should be replaced, then show the complete modified {% block scripts %} section"
    },
    {
      "step": "Step 2.8",
      "issue": "Same issue as Step 2.7 - no before/after context for the modification",
      "fix_suggestion": "Provide complete before and after code blocks for the {% block scripts %} section"
    },
    {
      "step": "Step 2.9",
      "issue": "Two separate modifications needed (data attribute + script replacement) but code snippets are fragmented with HTML comments",
      "fix_suggestion": "Show: 1) The exact element to add data-plan-id to with surrounding context, 2) The complete modified {% block scripts %} section"
    },
    {
      "step": "Step 2.10",
      "issue": "Same issue as Step 2.9 - fragmented instructions for multiple modifications",
      "fix_suggestion": "Show: 1) The exact element to add data-run-id and data-run-status to with surrounding context, 2) The complete modified {% block scripts %} section"
    }
  ],
  "warnings": [
    {
      "step": "Step 3.1, 3.2, 3.3",
      "issue": "Tests only cover 3 of 5 extracted JS modules - no tests for plan-detail.js and run-detail.js",
      "recommendation": "Add test files for plan-detail.js (testing startBuild/startReview with fetch mocks) and run-detail.js (testing SSE handling)"
    },
    {
      "step": "Step 2.5",
      "issue": "run-detail.js has complex SSE logic but no integration test verifying actual EventSource behavior",
      "recommendation": "Consider adding a test that mocks EventSource to verify message handling"
    },
    {
      "step": "Phase 3",
      "issue": "No test for error cases in Dashboard.handleSubmit network failures",
      "recommendation": "Add test case for fetch throwing an exception (network error scenario)"
    }
  ],
  "summary": "Plan has solid structure with proper phase ordering, complete JavaScript implementations using consistent IIFE patterns, and good test coverage for 3 of 5 modules. However, the modify steps (2.6-2.10) for template files are incomplete - they use HTML comments as placeholders to describe what should change rather than providing executable before/after code blocks. The builder cannot execute these steps without reading the original template files first. To approve, revise Steps 2.6-2.10 to include the actual code being replaced and the complete replacement code blocks. Also consider adding tests for plan-detail.js and run-detail.js."
}
```
