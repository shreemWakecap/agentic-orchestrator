# Plan: 001_in-the-sync-to

Request: in the sync to remote we create a new branch, commit changes, and open a PR... I want to use the gh cli to marge that create PR then pull the changes to developmenet or the main branch
Created: 2026-01-17T16:36:17.013118
Status: pending

---

GOAL: Sync workflow merges the created PR and pulls changes back to the base branch after successful PR creation

CONTEXT:
- Syncing workflow in `.orchestrator/actions/syncing.py` creates branch, commits, pushes, and creates PR via `gh pr create`
- The workflow uses `_run_gh()` helper for GitHub CLI commands and `_run_git()` for git commands
- After PR creation, workflow returns to base branch but doesn't merge or pull - PR is left open
- SyncResult dataclass already tracks `pr_url` and `pr_number` which are needed for merge operation

STEPS:
1. Add merge PR method to SyncingWorkflow
   ACTION: modify
   DO: Add `_merge_pr()` method that uses `gh pr merge {pr_number} --merge --delete-branch` to merge the created PR and delete the sync branch on remote
   IN: .orchestrator/actions/syncing.py
   OUT: .orchestrator/actions/syncing.py
   DONE: Method `_merge_pr` exists that accepts pr_number and calls gh pr merge with --merge and --delete-branch flags
   NEEDS: none

2. Add pull changes method to SyncingWorkflow
   ACTION: modify
   DO: Add `_pull_changes()` method that runs `git pull origin {base_branch}` to fetch and merge the remote changes into the local base branch
   IN: .orchestrator/actions/syncing.py
   OUT: .orchestrator/actions/syncing.py
   DONE: Method `_pull_changes` exists that accepts base_branch and runs git pull origin
   NEEDS: none

3. Add Step 7 to merge the PR after creation
   ACTION: modify
   DO: After successful PR creation in execute(), add Step 7/8 that calls `_merge_pr(pr_number)` to merge the PR. Update step numbering from 6 to 8 total steps. Handle merge failures gracefully with error message
   IN: .orchestrator/actions/syncing.py
   OUT: .orchestrator/actions/syncing.py
   DONE: execute() has Step 7 that prints "Merging pull request..." and calls _merge_pr(), with steps_completed tracking "merge_pr"
   NEEDS: 1

4. Add Step 8 to pull changes back to base branch
   ACTION: modify
   DO: After successful merge, add Step 8/8 that calls `_pull_changes(base_branch)` to pull the merged changes. Ensure local branch is on base_branch before pulling
   IN: .orchestrator/actions/syncing.py
   OUT: .orchestrator/actions/syncing.py
   DONE: execute() has Step 8 that prints "Pulling changes to {base_branch}..." and calls _pull_changes(), with steps_completed tracking "pull"
   NEEDS: 2, 3

5. Update step count in console output
   ACTION: modify
   DO: Update all step printouts to reflect 8 total steps instead of 6 (Step 1/8, Step 2/8, etc.)
   IN: .orchestrator/actions/syncing.py
   OUT: .orchestrator/actions/syncing.py
   DONE: All console.print statements show "Step X/8" format for all 8 steps
   NEEDS: 3, 4

6. Update CLI help text for sync command
   ACTION: modify
   DO: Update the sync command description in CLI help to indicate it creates a PR, merges it, and pulls changes back
   IN: .orchestrator/cli.py
   OUT: .orchestrator/cli.py
   DONE: Help text for sync command mentions "merge PR and pull changes" functionality
   NEEDS: none

VERIFY:
- Run: `python .orchestrator/cli.py sync` with uncommitted changes
- Expect: Creates branch, commits, pushes, creates PR, merges PR, pulls changes to base branch
- Verify: PR is closed/merged on GitHub and local branch has the merged commit
