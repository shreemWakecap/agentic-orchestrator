---
description: SDLC Review phase - code review for recent changes
argument-hint: [file-or-commit (optional)]
---

# Review

Perform code review on recent changes or specified files. Ensures code quality before completion.

## Variables

TARGET: $1

## Instructions

- If TARGET is a file path, review that file
- If TARGET is a commit hash, review that commit
- If no TARGET, review uncommitted changes via `git diff`
- Check `.orchestrator/experts/` for domain-specific review criteria
- Focus on correctness, security, and maintainability
- Be constructive with feedback

## Workflow

1. **Identify Scope**
   - Parse TARGET to determine what to review
   - If empty, use `git diff` for uncommitted changes
   - If commit, use `git show <commit>`
   - If file, read the file directly

2. **Load Domain Expertise**
   - Check `.orchestrator/registry.json` for relevant experts
   - Load anti-patterns and review criteria from expertise files

3. **Code Quality Review**
   - Logic correctness
   - Error handling
   - Edge cases
   - Code clarity

4. **Security Review**
   - Input validation
   - Injection vulnerabilities
   - Sensitive data exposure
   - Authentication/authorization issues

5. **Pattern Compliance**
   - Follows existing codebase patterns
   - Consistent naming conventions
   - Proper documentation

6. **Compile Feedback**
   - Categorize by severity
   - Provide specific locations
   - Suggest fixes

## Report

```
Code Review Complete

Target: <what was reviewed>
Files: <count>

Issues Found:
- Critical: <count>
- Major: <count>
- Minor: <count>

<if issues>
Details:
1. [<severity>] <file>:<line>
   <description>
   Fix: <suggestion>
</if>

Verdict: <APPROVED / NEEDS CHANGES>

<if approved>
Ready for: commit/merge
</if>
```
