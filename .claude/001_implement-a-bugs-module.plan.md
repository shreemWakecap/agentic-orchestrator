# Plan: 001_implement-a-bugs-module

Request: Implement a Bugs module for tracking and analyzing application bugs. Users can submit bug descriptions or unexpected behaviors, and the system will explore the relevant codebase area, generate a detailed explanation of what's happening and why, and persist this analysis to the database. Provide a bugs list view with the ability to view individual bug details. Support actions including delete, re-evaluate (re-run the analysis), and mark as not a bug. Add a "Create fix plan" action that integrates with the existing plan creation workflow, extending the plans table to include an optional Bug ID reference column for linking plans to their originating bugs.
Created: 2026-01-21T17:42:50.165295
Status: pending

---

GOAL: Portal has a Bugs module for submitting bug reports, viewing analysis results, and creating fix plans linked to bugs

CONTEXT:
- FastAPI app in `.orchestrator/portal/app.py` using APIRouter pattern with routers registered via `include_router()`
- Repositories follow pattern: interface in `interfaces.py`, implementation in `repositories/`, factory function in `db/__init__.py`
- Services in `portal/services/` are injected via `portal/dependencies.py` using FastAPI Depends
- Page routes in `pages.py` render Jinja2 templates from `portal/templates/`
- Database migrations in `.orchestrator/db/migrations/versions/` with sequential numbering (006 next)
- Plans table in `001_initial_schema.sql` has columns: plan_id, status, goal, request, raw_content, context_json, verify_json
- Questions module (003_questions_module.sql) provides pattern for status-based entities with related analysis data

STEPS:
1. Create bugs database migration
   ACTION: create
   DO: Create migration with bugs table (bug_id, title, description, relevant_area, status, analysis_text, source_files_json, created_at, updated_at) and alter plans table to add optional bug_id foreign key column
   IN: .orchestrator/db/migrations/versions/003_questions_module.sql, .orchestrator/db/migrations/versions/001_initial_schema.sql
   OUT: .orchestrator/db/migrations/versions/006_bugs_module.sql
   DONE: Migration file exists with valid SQL creating bugs table and adding bug_id column to plans
   NEEDS: none

2. Create bug repository interface
   ACTION: modify
   DO: Add IBugRepository interface with methods: create_bug, get_bug, list_bugs, update_bug, delete_bug, get_bug_with_analysis, update_analysis
   IN: .orchestrator/db/repositories/interfaces.py
   OUT: .orchestrator/db/repositories/interfaces.py
   DONE: IBugRepository interface defined with all CRUD and analysis methods
   NEEDS: 1

3. Create bug repository implementation
   ACTION: create
   DO: Implement BugRepository class with all CRUD operations following QuestionRepository pattern, include methods for creating bugs, updating status, storing analysis results, and linking to plans
   IN: .orchestrator/db/repositories/questions.py
   OUT: .orchestrator/db/repositories/bugs.py
   DONE: BugRepository class exists with all interface methods implemented using Database transaction pattern
   NEEDS: 2

4. Export bug repository from repositories package
   ACTION: modify
   DO: Add BugRepository import and export to repositories __init__.py, add IBugRepository to interface exports
   IN: .orchestrator/db/repositories/__init__.py
   OUT: .orchestrator/db/repositories/__init__.py
   DONE: BugRepository and IBugRepository exported in __all__ list
   NEEDS: 3

5. Add bug repository factory function to db package
   ACTION: modify
   DO: Add get_bug_repository() factory function following existing pattern, add BugRepository to imports and __all__ exports
   IN: .orchestrator/db/__init__.py
   OUT: .orchestrator/db/__init__.py
   DONE: get_bug_repository function exists and BugRepository in __all__
   NEEDS: 4

6. Update plan repository for bug linking
   ACTION: modify
   DO: Add bug_id parameter to create method, add get_plans_by_bug_id method, add update_bug_id method
   IN: .orchestrator/db/repositories/plans.py
   OUT: .orchestrator/db/repositories/plans.py
   DONE: PlanRepository has bug_id support in create and new query/update methods for bug linking
   NEEDS: 1

7. Create bug service
   ACTION: create
   DO: Create BugService class with methods for bug lifecycle management, codebase analysis integration (using CodebaseExplorerService), re-evaluation triggering, and plan creation orchestration
   IN: .orchestrator/portal/services/question_service.py, .orchestrator/portal/services/plan_service.py
   OUT: .orchestrator/portal/services/bug_service.py
   DONE: BugService class exists with submit_bug, analyze_bug, get_bug_detail, mark_not_bug, reanalyze_bug, create_fix_plan methods
   NEEDS: 5, 6

8. Add bug service to dependencies
   ACTION: modify
   DO: Add get_bug_repo dependency provider and get_bug_service dependency provider following existing patterns
   IN: .orchestrator/portal/dependencies.py
   OUT: .orchestrator/portal/dependencies.py
   DONE: get_bug_repo and get_bug_service functions exist and return properly configured instances
   NEEDS: 7

9. Create bugs API routes
   ACTION: create
   DO: Create APIRouter with endpoints: POST /api/bugs (submit), GET /api/bugs (list), GET /api/bugs/{bug_id} (detail), DELETE /api/bugs/{bug_id}, POST /api/bugs/{bug_id}/reanalyze, POST /api/bugs/{bug_id}/not-a-bug, POST /api/bugs/{bug_id}/create-plan
   IN: .orchestrator/portal/routes/questions.py, .orchestrator/portal/routes/plans.py
   OUT: .orchestrator/portal/routes/bugs.py
   DONE: Router exists with all endpoints using BugService via dependency injection
   NEEDS: 8

10. Export bugs router from routes package
    ACTION: modify
    DO: Add bugs router import and export to routes __init__.py
    IN: .orchestrator/portal/routes/__init__.py
    OUT: .orchestrator/portal/routes/__init__.py
    DONE: bugs_router imported and exported in __all__
    NEEDS: 9

11. Register bugs router in app
    ACTION: modify
    DO: Import bugs_router and register with app.include_router(bugs_router)
    IN: .orchestrator/portal/app.py
    OUT: .orchestrator/portal/app.py
    DONE: bugs_router imported and registered with app
    NEEDS: 10

12. Add bugs page route
    ACTION: modify
    DO: Add /bugs page route for list view and /bugs/{bug_id} for detail view, inject BugService, render bugs templates
    IN: .orchestrator/portal/routes/pages.py
    OUT: .orchestrator/portal/routes/pages.py
    DONE: Page routes /bugs and /bugs/{bug_id} exist with proper template rendering
    NEEDS: 8

13. Create bugs list template
    ACTION: create
    DO: Create bugs.html template with list view showing all bugs, status badges, action buttons (delete, re-evaluate, mark not a bug, create plan), and bug submission form
    IN: .orchestrator/portal/templates/questions.html, .orchestrator/portal/templates/plans.html
    OUT: .orchestrator/portal/templates/bugs.html
    DONE: Template exists with bug list, status indicators, action buttons, and submission form
    NEEDS: none

14. Create bug detail template
    ACTION: create
    DO: Create bug_detail.html template showing full bug information, analysis results with source file references, and action buttons including create fix plan link
    IN: .orchestrator/portal/templates/plan_detail.html, .orchestrator/portal/templates/questions.html
    OUT: .orchestrator/portal/templates/bug_detail.html
    DONE: Template exists with bug details, analysis display, source files, and action buttons
    NEEDS: none

15. Create bugs JavaScript module
    ACTION: create
    DO: Create bugs.js with functions for submitting bugs, handling actions (delete, reanalyze, mark not bug, create plan), and refreshing bug list
    IN: .orchestrator/portal/static/js/questions.js
    OUT: .orchestrator/portal/static/js/bugs.js
    DONE: JavaScript module exists with all bug interaction functions
    NEEDS: none

VERIFY:
- Run: python -c "from db import get_bug_repository; r = get_bug_repository(); print('Repository OK')"
- Run: curl -X POST http://localhost:8000/api/bugs -H "Content-Type: application/json" -d '{"title":"Test bug","description":"Button does not work"}'
- Run: curl http://localhost:8000/api/bugs
- Run: curl http://localhost:8000/bugs (should render HTML page)
- Check bugs table exists: sqlite3 .orchestrator/db/orchestrator.db ".schema bugs"
- Check plans has bug_id: sqlite3 .orchestrator/db/orchestrator.db ".schema plans"