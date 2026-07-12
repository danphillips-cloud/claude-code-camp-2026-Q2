# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repo state

This repo is at the scaffolding stage: no application code, dependencies, or
build/lint/test tooling exist yet (folders are placeholders, kept via
`.gitkeep`). There is nothing to build or run yet — don't invent commands or
architecture that aren't there. Once `mud_manager/` and the week1/week2
agents have real code, update this file with actual build/lint/test commands
and the agentic-loop architecture.

This repo is manually graded (Claude Code Camp 2026 Q2). The rules below are
auto-fail conditions — follow them exactly, do not "clean up" or restructure
around them.

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

If a `CLAUDE.local.md` is present (gitignored, not part of this repo's
history), it holds additional personal workflow notes and takes precedence
for anything it covers.
