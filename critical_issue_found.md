Critical Issues Found

     Issue 1: /recover Endpoint Parameter Mismatch (CRITICAL)

     Problem: Frontend sends action in request body, but endpoint expects it as query parameter.

     # plans.py line 643-645 - Expects QUERY parameter
     async def recover_plan(
         plan_id: str,
         action: str,  # <-- Query parameter (no Body/schema annotation)

     // dashboard.js, plan-recovery.js - Sends in BODY
     body: JSON.stringify({ action: action })  // WRONG!

     Result: action is always None, causing "Invalid action 'None'" error.

     ---
     Issue 2: /resume-build Doesn't Update Plan Status

     Problem: When resuming, plan stays in "paused"/"failed" state while build runs.

     # plans.py lines 125-187 - Missing status update
     async def resume_plan_build(...):
         # ... validation ...
         # NO STATUS UPDATE TO "building"!
         background_tasks.add_task(run_building_workflow_resume, ...)

     ---
     Issue 3: Frontend Error Handling Uses Wrong Property

     Problem: FastAPI returns detail, but JS looks for error.

     // dashboard.js line 1059
     throw new Error(errorData.error || 'Recovery failed');  // Should be .detail

     ---
     Issue 4: RecoverPlanRequest Schema Not Used

     Problem: Schema exists in requests.py but endpoint doesn't use it.

     ---
     Fixes Required

     Fix 1: Update /recover Endpoint (CRITICAL)

     File: .orchestrator/portal/routes/plans.py

     Change: Use RecoverPlanRequest schema for body parsing

     # BEFORE (line 642-650):
     @router.post("/{plan_id}/recover", response_model=WorkflowStartResponse)
     async def recover_plan(
         plan_id: str,
         action: str,  # Query param - WRONG
         background_tasks: BackgroundTasks,
         ...
     )

     # AFTER:
     from portal.schemas.requests import RecoverPlanRequest

     @router.post("/{plan_id}/recover", response_model=WorkflowStartResponse)
     async def recover_plan(
         plan_id: str,
         request: RecoverPlanRequest,  # Body param - CORRECT
         background_tasks: BackgroundTasks,
         ...
     )
     # Then use: action = request.action

     ---
     Fix 2: Update /resume-build to Set Plan Status

     File: .orchestrator/portal/routes/plans.py

     Add before background_tasks.add_task (around line 180):
     # Update plan status to building before starting
     plan_repo.update_status(plan_id, "building")

     ---
     Fix 3: Fix Frontend Error Handling

     File: .orchestrator/portal/static/js/dashboard.js

     Change line 1061:
     // BEFORE:
     throw new Error(errorData.error || 'Recovery failed');

     // AFTER:
     throw new Error(errorData.detail || errorData.error || 'Recovery failed');

     Also fix in: plan-recovery.js (similar pattern)

     ---
     Fix 4: Add Error Handling to /recover Endpoint

     File: .orchestrator/portal/routes/plans.py

     Wrap database operations in try/catch (lines 682-696):
     if action == "restart":
         try:
             build_state = build_state_repo.get(plan_id)
             if build_state:
                 build_state_repo.clear(plan_id)
             plan_repo.update_status(plan_id, "pending")
         except Exception as e:
             raise HTTPException(status_code=500, detail=f"Failed to reset plan: {str(e)}")

     ---
     Fix 5 (Already Done): workflow_runner.py

     File: .orchestrator/portal/services/workflow_runner.py

     Lines 235-238: ✅ Already fixed - removed invalid resume=True parameter.

     ---
     Files to Modify

     | File                                            | Changes                                                                            |
     |-------------------------------------------------|------------------------------------------------------------------------------------|
     | .orchestrator/portal/routes/plans.py            | Fix /recover to use schema, add status update to /resume-build, add error handling |
     | .orchestrator/portal/static/js/dashboard.js     | Fix error property name                                                            |
     | .orchestrator/portal/static/js/plan-recovery.js | Fix error property name                                                            |

     ---
     Implementation Order

     1. Fix /recover endpoint - Use RecoverPlanRequest schema (CRITICAL)
     2. Fix /resume-build - Add status update to "building"
     3. Fix error handling - Use detail property in JS
     4. Add try/catch - Error handling in /recover

     ---
     Previous Fix (Completed): Resume Build TypeError

     Overview (For Reference)

     Comprehensive improvements to the agentic-orchestrator build system:
     1. Add Extended Thinking to Claude CLI invocations
     2. Improve State Persistence to prevent data loss on pause/interruption
     3. Fix Race Conditions in parallel execution
     4. Improve UI/UX for pause/resume feedback
     5. Enhance Recovery Mechanisms

     ---
     Phase 1: Extended Thinking Support

     Files to Modify

     - .orchestrator/core/config.py - Add ThinkingConfig dataclass
     - .orchestrator/core/agent.py - Add --thinking CLI flags (lines 474-490, 624-642)
     - .orchestrator/workflows/building.py - Pass thinking params to agents

     Implementation

     1.1 Add ThinkingConfig (config.py)
     @dataclass(frozen=True)
     class ThinkingConfig:
         enabled: bool = False
         budget: int = 10000  # Token budget
         timeout_multiplier: float = 1.5

     1.2 CLI Flags (agent.py)
     - Add thinking_enabled: bool param to run() and run_agentic()
     - Append --thinking --thinking-budget {budget} when enabled
     - Multiply timeout by timeout_multiplier

     ---
     Phase 2: Database Schema Migration

     New Migration File

     .orchestrator/db/migrations/versions/002_extended_state.sql

     New Table: goal_verification_state
     CREATE TABLE goal_verification_state (
         plan_id TEXT PRIMARY KEY,
         goal TEXT,
         original_request TEXT,
         verification_attempt INTEGER DEFAULT 0,
         missing_items_json TEXT,
         completion_percentage INTEGER DEFAULT 0,
         goal_achieved INTEGER DEFAULT 0,
         verify_commands_json TEXT,
         FOREIGN KEY (plan_id) REFERENCES plans(plan_id) ON DELETE CASCADE
     );

     Extend build_states
     ALTER TABLE build_states ADD COLUMN execution_mode TEXT DEFAULT 'sequential';
     ALTER TABLE build_states ADD COLUMN current_wave_index INTEGER DEFAULT 0;
     ALTER TABLE build_states ADD COLUMN thinking_enabled INTEGER DEFAULT 0;

     Extend step_states
     ALTER TABLE step_states ADD COLUMN retry_history_json TEXT;
     ALTER TABLE step_states ADD COLUMN full_output TEXT;
     ALTER TABLE step_states ADD COLUMN thinking_tokens_used INTEGER DEFAULT 0;

     ---
     Phase 3: State Persistence Improvements

     Files to Modify

     - .orchestrator/db/repositories/build_state.py - Add new methods
     - .orchestrator/workflows/building.py - Update _save_state(), _load_state()

     New Repository Methods

     build_state.py:
     - save_goal_context(plan_id, goal_context) - Persist goal verification state
     - get_goal_context(plan_id) - Load goal context
     - add_step_retry_history(plan_id, step_id, error, duration) - Track retries
     - save_step_full_output(plan_id, step_id, output) - Save up to 5000 chars
     - batch_update_step_states(plan_id, updates) - Atomic batch updates

     BuildState Dataclass Updates

     Add fields: execution_mode, current_wave_index, thinking_enabled

     ---
     Phase 4: Race Condition Fixes

     Changes to building.py

     4.1 Add Threading Lock
     def __init__(self, ...):
         self._save_state_lock = threading.Lock()

     4.2 Thread-Safe Save
     def _save_state(self, ...):
         with self._save_state_lock:
             # existing save logic

     4.3 Atomic Wave Completion
     def _complete_wave(self, wave_results):
         with self._save_state_lock:
             for step, result in wave_results:
                 # update step states
             self._save_state()  # Single save after all updates

     ---
     Phase 5: UI/UX Improvements

     Files to Modify

     - .orchestrator/portal/static/js/build-progress.js - Thinking indicator
     - .orchestrator/portal/static/js/plan-detail.js - Wave progress display
     - .orchestrator/portal/static/js/plan-recovery.js - Retry history display

     Features

     - Purple "Extended thinking active" indicator during thinking
     - Wave progress: "Wave 2/5 (3 steps in parallel)"
     - Execution mode indicator (Sequential / Parallel Waves / Coordinated)
     - Retry count and backoff info in recovery UI

     ---
     Phase 6: Recovery Mechanism Improvements

     Files to Modify

     - .orchestrator/portal/services/recovery_service.py - Use goal context
     - .orchestrator/portal/services/auto_recovery.py - Honor retry backoff
     - .orchestrator/workflows/building.py - Parallel resume from correct wave

     Changes

     - get_recoverable_plans() includes goal_context and wave state
     - _is_in_backoff() checks retry history before auto-pausing
     - execute() uses persisted goal context instead of re-extracting
     - Parallel builds resume from current_wave_index

     ---
     Implementation Order

     | Phase | Description               | Dependencies |
     |-------|---------------------------|--------------|
     | 1     | Extended Thinking Support | None         |
     | 2     | Database Schema Migration | None         |
     | 3     | State Persistence         | Phase 2      |
     | 4     | Race Condition Fixes      | Phase 3      |
     | 5     | UI/UX Improvements        | Phase 2      |
     | 6     | Recovery Mechanisms       | Phase 3, 5   |

     ---
     Critical Files

     | File                                                        | Changes                                  |
     |-------------------------------------------------------------|------------------------------------------|
     | .orchestrator/core/config.py                                | Add ThinkingConfig                       |
     | .orchestrator/core/agent.py                                 | Add thinking CLI flags                   |
     | .orchestrator/workflows/building.py                         | State persistence, locking, resume logic |
     | .orchestrator/db/repositories/build_state.py                | New persistence methods                  |
     | .orchestrator/db/migrations/versions/002_extended_state.sql | New migration                            |
     | .orchestrator/portal/static/js/build-progress.js            | Thinking indicator                       |
     | .orchestrator/portal/static/js/plan-detail.js               | Wave progress                            |
     | .orchestrator/portal/static/js/plan-recovery.js             | Retry history                            |
     | .orchestrator/portal/services/recovery_service.py           | Goal context                             |
     | .orchestrator/portal/services/auto_recovery.py              | Backoff honoring                         |

     ---
     Backward Compatibility

     - Database: Uses ALTER TABLE ADD COLUMN with defaults
     - Config: ThinkingConfig.enabled defaults to False
     - API: New parameters have defaults, existing code unchanged




https://github.com/davila7/claude-code-templates

===================================
Dashboard displays Plans, Questions, and Statistics prominently at the top with Sync section moved lower and collapsible by default

Revamp the dashboard layout to prioritize high-value content sections. Reorder the dashboard to display Plans, Questions, and Statistics sections prominently at the top as primary content areas. Move the Sync section to a less prominent position (lower on the page or collapsed by default) since it's used less frequently. Apply UX best practices including clear visual hierarchy, appropriate whitespace, and logical content grouping to improve scannability and user workflow efficiency.



===================================

Users can scout individual files or paths on demand, with scouting allowed for any accessible project file

Enhance the knowledge scouting functionality to support targeted file scouting. Allow users to specify individual files or paths to scout rather than only bulk-scanning entire directories. Remove the restriction that limits scouting to files within the .orchestrator directory, enabling scouting of any accessible file in the project. The scouting process should accept a file path parameter and process that single file on demand.


GOAL: Users can scout individual files or paths on demand, with scouting allowed for any accessible project file

CONTEXT:
- Scouting workflow in `.orchestrator/workflows/scouting.py` currently only supports full/quick bulk scans
- Scout agent in `.orchestrator/agents/scout.md` outputs KEY: VALUE format with PROJECT_TYPE:, STRUCTURE: markers
- Knowledge is persisted via KnowledgeStore in `.orchestrator/core/knowledge_store.py` using SQLite database
- CLI dispatcher in `.orchestrator/cli.py` routes `scout` command to `workflows/scouting.py:run()`
- Current architecture has no file path restriction mechanism to enforce .orchestrator-only scouting
- Planning workflow in `.orchestrator/workflows/planning.py` integrates with knowledge store for context

STEPS:
1. Add file scout agent definition
2. Add file knowledge data model
3. Extend KnowledgeRepository for file-level storage
4. Create database migration for file_knowledge table
5. Extend KnowledgeStore with file operations
6. Add file scouting mode to ScoutingWorkflow
7. Update agent output markers for file-scout
8. Update CLI to accept file path argument
9. Update CLI help text for scout command