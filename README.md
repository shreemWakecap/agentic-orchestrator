# Self-Evolving SDLC System

A minimal, self-improving development system that grows expertise as it encounters new technology stacks. Uses Claude Code directly - no custom backend, no API wrapper, no complexity.

## Quick Start

```powershell
# Run setup (Windows)
./scripts/setup.ps1

# Start Claude Code
claude

# Plan a feature
/plan "Add user authentication with JWT"

# Build the plan
/build .specs/add-user-authentication.md

# Test the implementation
/test .specs/add-user-authentication.md

# Review the code
/review
```

## SDLC Flow

```
/plan  ─────>  /build  ─────>  /test  ─────>  /review
   │                                              │
   └──────────── feedback loop ───────────────────┘
```

## The Meta-Expert Pattern

When encountering unfamiliar code, create a domain expert:

```bash
/meta "React frontend patterns"
```

This creates:
- `.orchestrator/experts/react/expertise.yaml` - actionable knowledge
- `.claude/commands/experts/react/question.md` - ask questions
- `.claude/commands/experts/react/self-improve.md` - keep expertise current

Future SDLC cycles can leverage this expertise. The system grows smarter over time.

## Structure

```
.
├── .claude/
│   ├── settings.json    # Auto-permissions
│   ├── agents/          # SDLC agents (build, test, review, meta-expert)
│   └── commands/        # Slash commands (plan, build, test, review, meta)
├── .orchestrator/
│   ├── experts/         # Generated expertise (YAML)
│   └── registry.json    # Expert registry
├── .specs/              # Implementation plans
├── scripts/
│   └── setup.ps1        # Windows setup
├── CLAUDE.md            # Engineering rules
└── README.md            # This file
```

## Commands Reference

| Command | Description |
|---------|-------------|
| `/plan "description"` | Create implementation plan in `.specs/` |
| `/build path/to/spec.md` | Implement the plan |
| `/test [spec-path]` | Run tests, validate implementation |
| `/review [target]` | Code review on changes |
| `/meta "domain"` | Create new domain expert |

## Philosophy

- **No API wrappers** - Use Claude Code directly
- **No custom backends** - Everything is .claude/ configuration
- **Self-improving** - The meta-expert creates domain experts as needed
- **Minimal footprint** - Just 4 directories, ~15 files

## License

MIT
