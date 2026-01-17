# Plan: 001_i-want-to-have

Request: I want to have the sync-remote button which runs the sync.remote action and push to git 
Created: 2026-01-17T15:47:10.994884
Status: pending

---

GOAL: Dashboard has a "Sync Remote" button that triggers the sync-remote workflow and pushes changes to git

CONTEXT:
- Portal uses FastAPI with Jinja2 templates and Tailwind CSS for styling
- API endpoint `/api/workflows/sync-remote` already exists in `.orchestrator/portal/app.py:267-286`
- Dashboard template at `.orchestrator/portal/templates/dashboard.html` has a "Quick Actions" section with plan creation form
- JavaScript patterns in `dashboard.js` show async fetch POST to API with redirect to run detail page
- SyncingWorkflow in `.orchestrator/actions/syncing.py` commits changes and creates PRs with AI-generated messages

STEPS:
1. Add Sync Remote button to Quick Actions section
   ACTION: modify
   DO: Add a "Sync Remote" button next to the "Create Plan" form in the Quick Actions section. Button should have purple/indigo styling to differentiate from the blue Create Plan button, include a git sync icon, and be styled consistently with Tailwind CSS classes used elsewhere
   IN: .orchestrator/portal/templates/dashboard.html
   OUT: .orchestrator/portal/templates/dashboard.html
   DONE: Dashboard template contains a button with id="sync-remote-btn" or similar identifiable selector, styled with Tailwind classes
   NEEDS: none

2. Add JavaScript handler for Sync Remote button
   ACTION: modify
   DO: Add click event handler for the Sync Remote button that sends POST request to `/api/workflows/sync-remote`, shows loading state ("Syncing..."), handles success by redirecting to `/runs/{run_id}`, and handles errors with alert message. Follow existing pattern from plan form submission
   IN: .orchestrator/portal/static/js/dashboard.js
   OUT: .orchestrator/portal/static/js/dashboard.js
   DONE: File contains function that handles sync-remote button click, calls the API endpoint, and redirects on success
   NEEDS: 1

VERIFY:
- Run: Start portal with `python -m actions.portal` and navigate to dashboard
- Expect: "Sync Remote" button visible in Quick Actions section
- Run: Click "Sync Remote" button (with uncommitted changes in repo)
- Expect: Button shows "Syncing..." state, then redirects to run detail page showing sync workflow progress
