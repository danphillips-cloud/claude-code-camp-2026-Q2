# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repo state

`week0_explore/` now has real instructor-provided scaffolding (CircleMUD
docker infra, the `mud_manager` Ruby gem, the world-data parser, and the
preview dashboard) — see the folder structure below. `week1_baseline/` and
`week2_capable/` are still placeholders (`.keep` only): no application
code, dependencies, or build/lint/test tooling exists there yet. Don't invent
commands or architecture for those folders that aren't there. Once the
week1/week2 agents have real code, update this file with actual
build/lint/test commands and the agentic-loop architecture.

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
│   ├── docs/shred/*.md            # scratch/working notes — keep, don't delete
│   ├── mud_manager/               # Ruby gem: telnet session mgmt + MUD command primitives
│   ├── infrastructure/            # docker-compose etc. for the MUD sandbox
│   ├── circlemud-world-parser/    # parses CircleMUD world files (wld/mob/obj/shp/zon) to JSON
│   ├── preview/                   # web dashboard for browsing parsed world data
│   ├── bin/convert-world          # wires the parser to produce preview data
│   ├── HOW_TO_PLAY.md
│   └── CHALLENGES.md
├── week1_baseline/         # basic working agent
├── week2_capable/          # specialized loop + memory
└── docs/                   # top-level technical documentation artifacts
    └── plans/              # plan files the agent executes against
```

See `README.md` for the project scenario, task, and stack decisions.

If a `CLAUDE.local.md` is present (gitignored, not part of this repo's
history), it holds additional personal workflow notes and takes precedence
for anything it covers.
