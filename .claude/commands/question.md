---
description: Ask questions about the codebase, architecture, or implementation details
argument-hint: [question...]
---

# Question

Ask questions about the codebase and get informed answers based on code exploration. This command explores relevant files, analyzes patterns, and provides detailed explanations.

## Variables

QUESTION: $ARGUMENTS

## Instructions

- **IMPORTANT**: If no `QUESTION` is provided, STOP and ask the user what they want to know
- Explore the codebase to find relevant information
- Read key files to understand context
- Provide concrete answers with file references
- Include code snippets where helpful
- Don't make changes—this is read-only exploration

## Workflow

1. **Parse the question**: Understand what information is being requested
2. **Identify search strategy**:
   - Keywords to grep for
   - File patterns to glob
   - Directories to explore
3. **Explore the codebase**:
   - Use Glob to find relevant files
   - Use Grep to search for patterns
   - Read key files for context
4. **Analyze findings**:
   - Understand code structure and flow
   - Identify relevant functions, classes, components
   - Note connections between files
5. **Formulate answer**:
   - Provide clear, direct answer
   - Reference specific files and line numbers
   - Include code snippets as evidence
   - Suggest follow-up exploration if needed

## Question Types

### Architecture Questions
- "How is the app structured?"
- "What's the data flow for X?"
- "How do modules communicate?"

### Implementation Questions
- "How does feature X work?"
- "Where is Y implemented?"
- "What calls function Z?"

### Pattern Questions
- "What patterns are used for error handling?"
- "How is state managed?"
- "What's the testing approach?"

### Location Questions
- "Where is the API defined?"
- "Which file handles authentication?"
- "Where are the database models?"

## Report

```
Question: <QUESTION>

Answer:
<Clear, direct answer to the question>

Key Files:
- `path/to/file1.ts:L45` - <why this file is relevant>
- `path/to/file2.ts:L120` - <why this file is relevant>

Code Reference:
```<language>
// path/to/file.ts:45-60
<relevant code snippet>
```

Additional Context:
- <Related information>
- <Patterns observed>
- <Connections to other parts of codebase>

Related Questions You Might Ask:
- <follow-up question 1>
- <follow-up question 2>
```

## Examples

### Example 1: Location Question

**Question**: "Where is user authentication handled?"

**Answer**:
User authentication is handled in `src/auth/` with these key files:
- `src/auth/login.ts:L23` - Login endpoint handler
- `src/auth/middleware.ts:L45` - JWT validation middleware
- `src/auth/tokens.ts:L12` - Token generation and verification

### Example 2: Implementation Question

**Question**: "How does the caching layer work?"

**Answer**:
The caching layer uses Redis with a facade pattern:
- `src/cache/client.ts` - Redis connection wrapper
- `src/cache/facade.ts:L34` - Cache get/set with TTL
- Cache keys are namespaced by feature (e.g., `user:123:profile`)

## Notes

- This is READ-ONLY—no files will be modified
- For complex exploration, multiple search iterations may be needed
- Use `/orch-plan` if you want to implement changes based on findings
