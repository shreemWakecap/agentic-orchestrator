# orchistrator

Headless workflow runner that drives Claude Code step-by-step:
Plan → Implement → Test → Review → Iterate

Artifacts:
- orchistrator/runs/<run-id>/

Run:
- npm --prefix orchistrator install
- npm --prefix orchistrator run build
- node orchistrator/dist/index.js "your goal here"
