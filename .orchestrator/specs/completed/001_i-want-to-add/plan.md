# Plan: 001_i-want-to-add

Request: I want to add functionalitiy to move the plan from pending status to the buildung ot run and show the progress on the portal ... the portal should have all the functionalities to manage the plans adn implemenetation ultrathink
Created: 2026-01-17T16:02:27.817321
Status: pending

---

GOAL: Portal provides full plan lifecycle management with real-time build progress and status transitions

CONTEXT:
- FastAPI app in `.orchestrator/portal/app.py` with Jinja2 templates and SSE for real-time updates
- Plans stored in `.orchestrator/specs/{pending,in-progress,completed,failed}/` with state in `specs/state/`
- BuildState dataclass tracks step-level progress, files created/modified, and can_resume status
- JavaScript modules use IIFE pattern with global exposure (PlanList, BuildProgress, SidePopup, OrchestratorUtils)
- Existing SSE endpoint `/api/runs/{run_id}/events` streams build events in real-time
- BuildingWorkflow already handles plan state transitions internally (pending → building → completed/failed)

STEPS:
1. Add plan status transition API endpoint
   ACTION: modify
   DO: Add POST `/api/plans/{plan_id}/start-build` endpoint that validates plan is in pending state, calls the build workflow, and returns run_id for progress tracking
   IN: .orchestrator/portal/app.py, .orchestrator/actions/building.py
   OUT: .orchestrator/portal/app.py
   DONE: Endpoint responds to POST requests, starts build for pending plans, returns {"run_id": "..."} on success
   NEEDS: none

2. Add plan management API endpoints
   ACTION: modify
   DO: Add DELETE `/api/plans/{plan_id}` to delete plans, PUT `/api/plans/{plan_id}/move` to move between states (pending/failed), and GET `/api/plans/{plan_id}/state` to get build state details
   IN: .orchestrator/portal/app.py
   OUT: .orchestrator/portal/app.py
   DONE: DELETE removes plan directory, PUT moves plan between state folders, GET returns BuildState JSON
   NEEDS: 1

3. Enhance plans list template with action buttons
   ACTION: modify
   DO: Add "Start Build" button for pending plans, "Retry" button for failed plans, "Delete" button for all plans, and status badges with icons in the expandable section of each plan item
   IN: .orchestrator/portal/templates/plans.html, .orchestrator/portal/templates/base.html
   OUT: .orchestrator/portal/templates/plans.html
   DONE: Each plan row shows contextual action buttons based on state, clicking triggers appropriate API calls
   NEEDS: 2

4. Create plan management JavaScript module
   ACTION: create
   DO: Create PlanManager module with functions: startBuild(planId), deletePlan(planId), movePlan(planId, targetState), refreshPlanList(), and showConfirmDialog for delete confirmation
   IN: .orchestrator/portal/static/js/plan-list.js, .orchestrator/portal/static/js/common.js
   OUT: .orchestrator/portal/static/js/plan-manager.js
   DONE: Module exports functions, handles API calls with error handling, updates UI on success
   NEEDS: 3

5. Add real-time progress widget to dashboard
   ACTION: modify
   DO: Create a "Live Builds" section on dashboard showing all running builds with progress bars, current step, and elapsed time. Auto-refresh via polling or SSE
   IN: .orchestrator/portal/templates/dashboard.html, .orchestrator/portal/static/js/build-progress.js
   OUT: .orchestrator/portal/templates/dashboard.html
   DONE: Dashboard shows active builds with real-time progress bars that update without page refresh
   NEEDS: 1

6. Create dashboard live updates JavaScript
   ACTION: modify
   DO: Add initLiveBuilds() function to dashboard.js that polls `/api/runs` for active runs and updates progress bars, or connects via SSE for real-time updates
   IN: .orchestrator/portal/static/js/dashboard.js, .orchestrator/portal/static/js/build-progress.js
   OUT: .orchestrator/portal/static/js/dashboard.js
   DONE: Active runs section auto-updates every 2 seconds with current progress and step info
   NEEDS: 5

7. Add run list API endpoint with filtering
   ACTION: modify
   DO: Add GET `/api/runs` endpoint that returns all active_runs with optional status filter query param, add running/completed/failed counts
   IN: .orchestrator/portal/app.py
   OUT: .orchestrator/portal/app.py
   DONE: Endpoint returns {"runs": [...], "counts": {"running": N, "completed": N, "failed": N}}
   NEEDS: none

8. Enhance plan detail page with build controls
   ACTION: modify
   DO: Add "Start Build" button for pending plans that shows progress inline, "Resume Build" for paused plans showing what step failed, and step-by-step progress visualization
   IN: .orchestrator/portal/templates/plan_detail.html, .orchestrator/portal/static/js/plan-detail.js
   OUT: .orchestrator/portal/templates/plan_detail.html
   DONE: Plan detail shows build controls, clicking Start Build shows inline progress with SSE updates
   NEEDS: 4

9. Create step progress visualization component
   ACTION: modify
   DO: Add visual step-by-step progress display showing completed/in-progress/pending steps with checkmarks, spinners, and descriptions. Include expandable step details
   IN: .orchestrator/portal/static/js/plan-detail.js, .orchestrator/portal/templates/plan_detail.html
   OUT: .orchestrator/portal/static/js/plan-detail.js
   DONE: Steps render as visual checklist with real-time status updates during build
   NEEDS: 8

10. Add build state API endpoint
    ACTION: modify
    DO: Add GET `/api/plans/{plan_id}/build-state` endpoint that reads and returns the BuildState from specs/state/{plan_id}.state.json including step-level progress
    IN: .orchestrator/portal/app.py
    OUT: .orchestrator/portal/app.py
    DONE: Endpoint returns full BuildState JSON with completed_steps, failed_steps, step_states, and progress percentage
    NEEDS: 7

11. Update plans list JavaScript with script tags
    ACTION: modify
    DO: Update plans.html to include plan-manager.js script and wire up event handlers for the new action buttons (start build, delete, retry)
    IN: .orchestrator/portal/templates/plans.html
    OUT: .orchestrator/portal/templates/plans.html
    DONE: Plans page loads plan-manager.js, buttons have onclick handlers that call PlanManager functions
    NEEDS: 4

12. Add toast notification system
    ACTION: create
    DO: Create lightweight toast notification component for showing success/error messages without alerts. Position bottom-right, auto-dismiss after 3 seconds
    IN: .orchestrator/portal/static/js/common.js, .orchestrator/portal/templates/base.html
    OUT: .orchestrator/portal/static/js/toast.js
    DONE: Toast module with show(message, type) function, CSS animations, auto-dismiss
    NEEDS: none

13. Integrate toast notifications in base template
    ACTION: modify
    DO: Add toast container div to base.html, include toast.js script, expose global showToast function
    IN: .orchestrator/portal/templates/base.html, .orchestrator/portal/static/js/toast.js
    OUT: .orchestrator/portal/templates/base.html
    DONE: base.html has toast container, toast.js loaded, window.showToast available
    NEEDS: 12

14. Add keyboard shortcuts for plan management
    ACTION: modify
    DO: Add keyboard shortcuts: 'b' to start build on selected plan, 'd' for delete with confirmation, 'r' to refresh list. Show shortcut hints in UI
    IN: .orchestrator/portal/static/js/plan-manager.js, .orchestrator/portal/templates/plans.html
    OUT: .orchestrator/portal/static/js/plan-manager.js
    DONE: Keyboard shortcuts work when plan is selected, small hint text shows available shortcuts
    NEEDS: 11

VERIFY:
- Navigate to /plans, click "Start Build" on a pending plan, see run_id returned and progress visible
- Dashboard shows "Live Builds" section with real-time progress bars for running builds
- Delete a plan from plans list, confirm it's removed from the filesystem
- Start build from plan detail page, see step-by-step progress update in real-time
- Resume a paused build, see it continue from the failed step
- Toast notifications appear for success/error actions without blocking UI
