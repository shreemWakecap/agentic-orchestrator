---
description: Create a new domain expert for a technology stack
argument-hint: [domain description]
---

# Meta Expert

Create a new domain expert that the SDLC system can use. Experts provide specialized knowledge for Plan/Build/Test/Review cycles.

## Variables

DOMAIN_DESCRIPTION: $1

## Instructions

- IMPORTANT: If no DOMAIN_DESCRIPTION provided, stop and ask what domain to create an expert for
- Analyze the codebase to understand the technology
- Create an expertise.yaml with actionable knowledge
- Create question and self-improve commands for the expert
- Register the expert in the registry

## Workflow

1. **Parse Domain**
   - Extract the technology/framework name from DOMAIN_DESCRIPTION
   - Convert to kebab-case for directory names (e.g., "React frontend" -> "react")

2. **Explore Codebase**
   - Use Glob to find relevant files
   - Read key files to understand patterns
   - Identify architecture and conventions

3. **Create Expertise File**
   - Write `.orchestrator/experts/<domain>/expertise.yaml`
   - Include: overview, key_files, patterns, anti_patterns, testing, common_tasks
   - Keep under 500 lines

4. **Create Expert Commands**
   - Create `.claude/commands/experts/<domain>/question.md`
   - Create `.claude/commands/experts/<domain>/self-improve.md`

5. **Update Registry**
   - Add entry to `.orchestrator/registry.json`

6. **Verify**
   - Read created files to ensure they're valid YAML/markdown

## Report

```
Expert Created: <domain>

Files:
- .orchestrator/experts/<domain>/expertise.yaml
- .claude/commands/experts/<domain>/question.md
- .claude/commands/experts/<domain>/self-improve.md

Registry: Updated

Commands Available:
- /experts:<domain>:question "How do I..."
- /experts:<domain>:self-improve

Key Patterns Identified:
- <pattern 1>
- <pattern 2>

The SDLC system can now leverage <domain> expertise.
```
