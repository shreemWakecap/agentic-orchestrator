# Inline JavaScript Analysis for Template Extraction

## Overview

This document analyzes all inline JavaScript code in the 6 HTML templates to prepare for extraction into external JS files.

---

## 1. base.html (Lines 160-236)

### Script Location
- **Lines**: 160-236
- **Type**: Global utility module (SidePopup)

### Functionality
The `SidePopup` object provides a reusable side panel component for displaying content.

### Code Structure
```javascript
const SidePopup = {
    overlay: null,
    popup: null,
    titleEl: null,
    contentEl: null,

    init(),              // Initialize DOM references, attach ESC key handler
    open(title, content, options),  // Open popup with static content
    close(),             // Close popup
    loadUrl(title, url, options),   // Async load content from URL
    escapeHtml(text)     // Utility to escape HTML
};
```

### DOM Dependencies
- `#side-popup-overlay` - Overlay element
- `#side-popup` - Main popup container
- `#side-popup-title` - Title element
- `#side-popup-content` - Content container

### External Dependencies
- None (vanilla JS)

### Jinja2 Variables
- None

### Event Listeners
- `document.addEventListener('keydown', ...)` - ESC key to close
- `document.addEventListener('DOMContentLoaded', ...)` - Initialize on load

### CSS Class Manipulations
- `.active` class on overlay and popup
- `document.body.style.overflow` toggling

### Extraction Notes
- **Standalone module**: Yes, can be extracted as-is
- **Initialization**: Self-initializing on DOMContentLoaded
- **Global exposure**: Must remain global (`window.SidePopup`)

---

## 2. dashboard.html (Lines 199-240)

### Script Location
- **Lines**: 199-240
- **Type**: Page-specific event handler

### Functionality
Handles the "Create Plan" form submission via async POST request.

### Code Structure
```javascript
document.getElementById('plan-form').addEventListener('submit', async function(e) {
    // Prevent default form submission
    // Validate input (description not empty)
    // POST to /api/workflows/plan
    // Redirect to /runs/{run_id} on success
});
```

### DOM Dependencies
- `#plan-form` - Form element
- `#plan-description` - Input element
- `button[type="submit"]` - Submit button

### External Dependencies
- None (vanilla JS, fetch API)

### Jinja2 Variables
- None

### API Calls
- `POST /api/workflows/plan` with JSON `{ description: string }`

### Error Handling
- Visual feedback (red border on empty input)
- Alert on API failure
- Button state management (disabled/enabled)

### Extraction Notes
- **Page-specific**: Yes, only needed on dashboard
- **Initialization**: Runs once on DOM ready (implicit via script placement)
- **Can combine with**: No other dashboard scripts

---

## 3. plans.html (Lines 141-187)

### Script Location
- **Lines**: 141-187
- **Type**: Page-specific UI interactions

### Functionality
Handles expand/collapse of plan items and file viewing in side popup.

### Code Structure
```javascript
const expandedPlans = new Set();       // Track expanded state

function togglePlan(planId) { ... }    // Toggle expand/collapse
function openFile(planId, filename) { ... }  // Open file in SidePopup
function expandAll() { ... }           // Expand all plans
function collapseAll() { ... }         // Collapse all plans
```

### DOM Dependencies
- `#files-{planId}` - Expandable content containers
- `#expand-icon-{planId}` - Arrow icons
- `.plan-item[data-plan-id]` - Plan list items

### External Dependencies
- **SidePopup** (from base.html) - Used in `openFile()`

### Jinja2 Variables
- `{{ plan.id }}` - Used in onclick handlers as string parameter

### API Calls
- `GET /api/plans/{planId}/files/{filename}` via SidePopup.loadUrl()

### CSS Class Manipulations
- `.expanded` on file containers
- `.rotated` on expand icons

### Extraction Notes
- **Page-specific**: Yes, only needed on plans page
- **Dependencies**: Requires SidePopup from base.html
- **Global functions**: togglePlan, openFile, expandAll, collapseAll must be global for onclick handlers
- **Jinja2 handling**: planId is passed as string literal in onclick, no runtime Jinja2 needed

---

## 4. plan_detail.html (Lines 68-103)

### Script Location
- **Lines**: 68-103
- **Type**: Page-specific workflow actions

### Functionality
Provides functions to start build and review workflows.

### Code Structure
```javascript
async function startBuild(planPath) {
    // POST to /api/workflows/build
    // Redirect to run page
}

async function startReview(planPath) {
    // POST to /api/workflows/review
    // Redirect to run page
}
```

### DOM Dependencies
- None directly (called via onclick)

### External Dependencies
- None (vanilla JS, fetch API)

### Jinja2 Variables
- `{{ plan.file }}` - Passed as string parameter in onclick handlers

### API Calls
- `POST /api/workflows/build` with JSON `{ plan_path: string }`
- `POST /api/workflows/review` with JSON `{ plan_path: string, refresh_docs: false }`

### Error Handling
- Console.error and alert on failure

### Extraction Notes
- **Page-specific**: Yes, only needed on plan detail page
- **Global functions**: startBuild, startReview must be global for onclick handlers
- **Jinja2 handling**: planPath is passed as string literal in onclick, no runtime Jinja2 needed

---

## 5. runs.html (Lines N/A)

### Script Location
- **None** - This template has no inline JavaScript

### Extraction Notes
- No JavaScript to extract

---

## 6. run_detail.html (Lines 129-190)

### Script Location
- **Lines**: 129-190
- **Type**: Page-specific real-time updates

### Functionality
Handles SSE (Server-Sent Events) for real-time run progress updates.

### Code Structure
```javascript
const runStatus = '{{ run.status }}';
const runId = '{{ run.id }}';

if (runStatus === 'running' || runStatus === 'pending') {
    const eventSource = new EventSource('/api/runs/' + runId + '/events');

    eventSource.onmessage = function(e) {
        // Parse event JSON
        // Update status badge
        // Update progress bar
        // Update current step
        // Append event to log
    };

    eventSource.onerror = function() {
        // Close connection on error
    };
}
```

### DOM Dependencies
- `#status-badge` - Status badge element
- `#progress-bar` - Progress bar element
- `#progress-percent` - Progress percentage text
- `#current-step` - Current step text
- `#events-log` - Events log container

### External Dependencies
- EventSource API (native browser SSE)

### Jinja2 Variables
- `{{ run.status }}` - **RUNTIME REQUIRED** - Initial run status
- `{{ run.id }}` - **RUNTIME REQUIRED** - Run ID for SSE endpoint

### API Calls
- SSE connection to `/api/runs/{runId}/events`

### CSS Class Manipulations
- Status badge classes: `bg-green-100 text-green-800`, `bg-red-100 text-red-800`
- `.fade-in` on new event entries

### Extraction Notes
- **Page-specific**: Yes, only needed on run detail page
- **Jinja2 handling**: **REQUIRES DATA ATTRIBUTES** - runStatus and runId must be injected
- **Recommended approach**: Add `data-run-status` and `data-run-id` to a container element

---

## Summary Table

| Template | Script Lines | Functions/Objects | Dependencies | Jinja2 Vars | Extraction Complexity |
|----------|-------------|-------------------|--------------|-------------|----------------------|
| base.html | 160-236 | SidePopup (module) | None | None | Low - standalone |
| dashboard.html | 199-240 | form submit handler | None | None | Low - self-contained |
| plans.html | 141-187 | togglePlan, openFile, expandAll, collapseAll | SidePopup | plan.id (string literal) | Low - needs global fns |
| plan_detail.html | 68-103 | startBuild, startReview | None | plan.file (string literal) | Low - needs global fns |
| runs.html | N/A | None | N/A | N/A | N/A |
| run_detail.html | 129-190 | SSE handler | EventSource | run.status, run.id | Medium - needs data attrs |

---

## Recommended Extraction Strategy

### 1. Create External JS Files

```
.orchestrator/server/static/js/
├── side-popup.js         # SidePopup module from base.html
├── dashboard.js          # Dashboard form handler
├── plans.js              # Plans page interactions
├── plan-detail.js        # Plan detail workflow actions
└── run-detail.js         # Run detail SSE handler
```

### 2. Handle Jinja2 Variables

For `run_detail.html`, add data attributes to the page container:

```html
<div id="run-detail-page"
     data-run-status="{{ run.status }}"
     data-run-id="{{ run.id }}">
```

Then in JS:
```javascript
const container = document.getElementById('run-detail-page');
const runStatus = container.dataset.runStatus;
const runId = container.dataset.runId;
```

### 3. Script Loading Order

In `base.html`:
```html
<script src="/static/js/side-popup.js"></script>
{% block scripts %}{% endblock %}
```

In page templates:
```html
{% block scripts %}
<script src="/static/js/dashboard.js"></script>
{% endblock %}
```

### 4. Shared Code Identification

- **SidePopup**: Used by plans.html (openFile function)
- **No other cross-page dependencies identified**

### 5. Potential Shared Utilities

Could extract common patterns:
- `escapeHtml()` - Currently in SidePopup, could be standalone utility
- API fetch wrapper - Common pattern across dashboard, plan-detail

---

## Total Lines of JavaScript to Extract

| File | Lines |
|------|-------|
| base.html | ~76 lines |
| dashboard.html | ~41 lines |
| plans.html | ~47 lines |
| plan_detail.html | ~35 lines |
| run_detail.html | ~61 lines |
| **Total** | **~260 lines** |
