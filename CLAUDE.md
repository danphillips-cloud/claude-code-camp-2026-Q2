# Claude Code Camp 2026 Q2 — Repo Rules

This repo is manually graded. The rules below are auto-fail conditions —
follow them exactly, do not "clean up" or restructure around them.

## Hard constraints

- Repo name must be exactly `claude-code-camp-2026-Q2` (casing counts).
- Repo must be public.
- Fresh init only — never forked/cloned from the example repo.
- Do not rename top-level folders or drop new files at the top level.
- `.boukensha` is a marker file — leave it alone (likely grader-checked).
- `.gitignore` must be in place *before* the first `git add` — never commit
  `node_modules` or similar.

## Folder structure (do not restructure)

```
claude-code-camp-2026-Q2/
├── .boukensha              # marker file, just leave it
├── .gitignore
├── week0_explore/
│   ├── docs/shred/*.md     # scratch/working notes — keep, don't delete
│   ├── mud_manager/        # the agent that operates the MUD
│   ├── infrastructure/     # docker-compose etc. for the MUD sandbox
│   └── CHALLENGE.md
├── week1_baseline/         # basic working agent
├── week2_capable/          # specialized loop + memory
└── docs/
    └── plans/              # plan files the agent executes against
```

See `README.md` for the project scenario, task, and stack decisions.
