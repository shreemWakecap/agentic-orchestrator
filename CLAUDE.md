# Self-Evolving SDLC System

A minimal, self-improving development system that grows expertise as it encounters new technology stacks.

## How It Works

This system uses Claude Code directly with specialized agents for each SDLC phase:

```
/plan  ->  /build  ->  /test  ->  /review
   |                                    |
   +-------- feedback loop -------------+
```

When encountering unfamiliar code, use `/meta` to create a new domain expert that improves future interactions.

## SDLC Commands

| Command | Purpose |
|---------|---------|
| `/plan "description"` | Create implementation plan in `.specs/` |
| `/build .specs/name.md` | Implement the plan |
| `/test [spec-path]` | Run tests, validate implementation |
| `/review [target]` | Code review on changes |
| `/meta "domain"` | Create new domain expert |

## Directory Structure

```
.
├── .claude/
│   ├── settings.json      # Auto-permissions configured
│   ├── agents/            # SDLC agents
│   │   ├── meta-expert.md # Creates domain experts
│   │   ├── build-agent.md # Implements code
│   │   ├── tester.md      # Writes/runs tests
│   │   ├── reviewer.md    # Code review
│   │   └── scout-report-suggest.md
│   └── commands/          # Slash commands
│       ├── plan.md
│       ├── build.md
│       ├── test.md
│       ├── review.md
│       └── meta.md
├── .orchestrator/
│   ├── experts/           # Generated expertise (YAML)
│   └── registry.json      # Expert registry
├── .specs/                # Implementation plans
└── scripts/
    └── setup.ps1          # Windows setup
```

## The Meta-Expert Pattern

The key innovation is **self-evolving expertise**:

1. When you encounter React code but have no React expert:
   ```
   /meta "React frontend patterns"
   ```

2. This creates:
   - `.orchestrator/experts/react/expertise.yaml` - actionable knowledge
   - `.claude/commands/experts/react/question.md` - ask questions
   - `.claude/commands/experts/react/self-improve.md` - keep expertise current

3. Future SDLC phases can now use React expertise:
   ```
   /experts:react:question "How do I add a new route?"
   /experts:react:self-improve  # After codebase changes
   ```

## Quick Start

```powershell
# Setup (Windows)
./scripts/setup.ps1

# Start Claude Code
claude

# Example workflow
/plan "Add user authentication with JWT"
/build .specs/add-user-authentication.md
/test .specs/add-user-authentication.md
/review
```

## Engineering Rules

### Read files completely
- When reading a file, read ALL of it (in chunks if needed)
- Use `wc -l <filename>` to get line counts for large files

### Use Astral UV for Python
- Always `uv run python ...`, never raw python
- Use `uv add <package>` for new dependencies

### Git discipline
- Do NOT commit unless explicitly asked
- Review changes with `/review` before committing

### Expertise maintenance
- Run `/experts:<domain>:self-improve` after significant codebase changes
- Keep expertise files under 500 lines - concise and actionable
