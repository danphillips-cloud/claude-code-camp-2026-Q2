# Plan: Move subagents from filesystem loading to `AgentDefinition`

**Status:** DRAFT — for Dan's review before implementation.
**Dir:** `week0_explore/explore_architecture/03b_subagent_sdk/`
**Date:** 2026-07-22

---

## 1. What's here today

`03b_subagent_sdk` currently has **no SDK harness code**. The subagents exist
only as Markdown files that the Claude Code CLI auto-discovers from the
filesystem:

```
.claude/
├── settings.local.json          # tool allowlist (references claude_agent_sdk, not yet installed)
└── agents/
    ├── mud-player.md            # subagent #1 — YAML frontmatter + Markdown body
    ├── mud-agent.md            # subagent #2 — YAML frontmatter + Markdown body
    ├── scripts/mud.py          # 418-line persistent MUD connection daemon (a TOOL)
    └── data/
        ├── player.md           # persistent character state (MEMORY)
        └── world.md           # persistent world knowledge (MEMORY)
```

**How the filesystem mechanism works:** Claude Code scans `.claude/agents/*.md`. (never go local, stay in /claude-code-camp-2026-Q2/week0_explore/explore_architecture/03b_subagent_sdk)
Each file's frontmatter `name`/`description` registers a dispatchable subagent;
the Markdown body becomes that subagent's system prompt. This is convention, not
code — nothing in this folder calls the SDK.

**Key distinction for this migration:** only the two `*.md` files are *subagent
definitions*. `scripts/mud.py` (a CLI tool the agent shells out to) and
`data/*.md` (memory the agent reads/writes) are **not** subagent definitions and
stay exactly where they are.

## 2. What we're changing (and why)

Replace filesystem auto-discovery of the two agents with explicit
`AgentDefinition` objects passed to the Claude Agent SDK. After this change the
agents are defined **in Python code**, and the SDK — not the CLI's folder
scan — owns them.

Verified API (from `code.claude.com/docs/en/agent-sdk/python`, fetched
2026-07-22 — note fields are **camelCase**):

```python
@dataclass
class AgentDefinition:
    description: str                 # required — when to dispatch this agent
    prompt: str                      # required — the system prompt
    tools: list[str] | None = None   # allow-list; omit = inherit all
    disallowedTools: list[str] | None = None
    model: str | None = None         # "opus" | "sonnet" | "haiku" | "inherit" | full id
    skills: list[str] | None = None
    memory: Literal["user","project","local"] | None = None
    mcpServers: list[str | dict] | None = None
    initialPrompt: str | None = None
    maxTurns: int | None = None
    background: bool | None = None
    effort: EffortLevel | int | None = None
    permissionMode: PermissionMode | None = None
```

Passed via:

```python
options = ClaudeAgentOptions(agents={"mud-player": AgentDefinition(...), ...})
async for message in query(prompt=..., options=options): ...
```

## 3. File layout

Flattened to match the instructor's reference repo
(`omenking/.../03b_subagent_sdk`): `agents/`, `data/`, and `scripts/` sit at the
top level, there is no `.claude/`, and the harness is `scripts/run_agent.py`.

```
03b_subagent_sdk/
├── PLAN.md                # this file
├── summary.md             # journal write-up (Dan's voice)
├── requirements.txt       # claude-agent-sdk==0.2.126
├── .venv/                 # local install — gitignored
├── .gitignore             # ignores .venv/, .mud-session/, __pycache__
├── agents/                # agent-definition prompts (loaded by run_agent.py)
│   ├── mud-player.md
│   └── mud-agent.md
├── data/                  # KEEP — memory
│   ├── player.md
│   └── world.md
└── scripts/
    ├── mud.py             # KEEP — the tool
    └── run_agent.py       # SDK harness: build_agents() + query() loop
```

**Prompt storage:** each agent's system prompt stays a plain `agents/*.md` file,
loaded at startup. The *subagent definition* lives in code (`AgentDefinition` in
`run_agent.py`); the markdown just keeps ~200 lines of prose out of the script.
This mirrors the reference (`agents/play-mud.md` + `scripts/run_agent.py`).

**Difference from the reference:** the reference ships a single `play-mud` agent;
this keeps both `mud-player` and `mud-agent` per §6.5. Everything else matches.

## 4. Translation mapping (per agent)

| `.md` source | → | `AgentDefinition` field |
|---|---|---|
| frontmatter `description:` | → | `description=` (verbatim) |
| Markdown body (below `---`) | → | `prompt=` (loaded from `agents/*.md`) |
| implied tool use (Bash for mud.py; Read/Write/Edit for memory) | → | `tools=["Bash","Read","Write","Edit"]` |
| — | → | `model="inherit"` (keep whatever main model runs) |

Both agents need `Bash` (to run `python3 scripts/mud.py …`) and
`Read`/`Write`/`Edit` (to persist `data/player.md` + `data/world.md`). We scope
`tools` to exactly those four rather than inheriting everything.

## 5. `main.py` shape (draft)

```python
import asyncio
from pathlib import Path
from claude_agent_sdk import query, ClaudeAgentOptions
from agents import build_agents           # returns dict[str, AgentDefinition]

AGENT_DIR = Path(__file__).parent / ".claude" / "agents"   # so mud.py + data/ resolve

async def main(goal: str):
    options = ClaudeAgentOptions(
        agents=build_agents(),
        allowed_tools=["Bash", "Read", "Write", "Edit"],
        permission_mode="acceptEdits",      # matches current interactive posture; see §6
        cwd=str(AGENT_DIR),                  # so "python3 scripts/mud.py" + "data/…" work
        setting_sources=[],                  # do NOT re-load .claude/agents/*.md from disk
        model="opus",
    )
    async for message in query(prompt=goal, options=options):
        print(message)

if __name__ == "__main__":
    import sys
    asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else "play the MUD"))
```

`setting_sources=[]` is the critical line: it tells the SDK **not** to load the
filesystem `.claude/agents/*.md`, so the only source of the subagents is our
`AgentDefinition` code. That's the whole point of the migration and how we prove
it worked.

`cwd=AGENT_DIR` preserves the working-dir assumption baked into the prompts
(`python3 scripts/mud.py`, `data/player.md`). Alternative: rewrite the prompts to
use absolute paths and drop `cwd`. Proposal: keep `cwd` — smaller, safer change.

## 6. Decisions (resolved with Dan 2026-07-22)

1. **Stale path bug in both prompt bodies.** They reference
   `…/03_subagent_sdk/.claude/agents/data/…` but this folder is
   `03b_subagent_sdk`. **→ Fix to `03b_` while extracting the prompts.**
2. **Old `.md` files → KEEP, but RENAMED so they no longer auto-load and are
   easy to find/remove later.** Rename in place, staying in the folder:
   `mud-player.md` → `mud-player.md.retired`,
   `mud-agent.md` → `mud-agent.md.retired`. Dropping the `.md` extension means
   the CLI folder-scan ignores them; `.retired` flags them for Dan's later
   review/removal. (Redundant with `setting_sources=[]`, but belt-and-suspenders
   and keeps the source-of-truth text around.)
3. **Everything stays inside `03b_subagent_sdk/` — no writes or cwd outside this
   folder.** Concretely:
   - venv at `03b_subagent_sdk/.venv` (not global, not the parser's `.venv`).
   - `cwd` set to `.claude/agents` **inside** 03b so `python3 scripts/mud.py` and
     `data/*.md` resolve; never an absolute path pointing elsewhere.
   - `permission_mode="acceptEdits"` + scoped `allowed_tools=["Bash","Read",
     "Write","Edit"]`; `setting_sources=[]`.
   - **One external write remains, inherited from the tool, not introduced here:**
     `mud.py`'s daemon writes its session log to `${TMPDIR}/mud-session/` (system
     temp), not into 03b. That's existing `mud.py` behavior. Flagging it because
     it's the one thing that touches outside 03b — leave as-is, or I can point it
     at `03b_subagent_sdk/.mud-session/` via the daemon's session dir. **Default:
     leave as-is unless you say otherwise.**
4. **SDK not installed → INSTALL it,** into `03b_subagent_sdk/.venv` (keeps it out
   of every other directory per #3). `requirements.txt` pins `claude-agent-sdk`.
   This is implementation step 1.
5. **One agent or two? → KEEP BOTH** (`mud-player` generic, `mud-agent`
   CircleMUD-specific) for a faithful 1:1 port. Collapsing is a separate change.

**`.gitignore` note:** add `.venv/` and `.mud-session/` (if used) for this
folder so the install artifacts never get committed.

## 7. Implementation steps (after you approve)

1. Create `03b_subagent_sdk/.venv`, `requirements.txt` (`claude-agent-sdk`),
   `.gitignore` (`.venv/`), then `pip install` — all inside 03b (§6.3, §6.4).
2. Extract both `.md` bodies → `prompts/mud_player.md`, `prompts/mud_agent.md`
   (strip frontmatter, fix the `03_` → `03b_` path bug).
3. Rename the old agent files → `mud-player.md.retired`, `mud-agent.md.retired`
   (§6.2).
4. Write `agents.py` — `build_agents()` returning the two `AgentDefinition`s.
5. Write `main.py` — options + `query()` loop, `setting_sources=[]`, `cwd` inside 03b.
6. Write `README.md` — `python3 main.py "reach level 7"` usage.
7. **Verify** (§8).

## 8. How we'll verify it works

- **Static:** `python3 -c "from agents import build_agents; print(build_agents().keys())"`
  → prints both agent names, no import error.
- **Negative control:** temporarily rename `.claude/agents/*.md`; harness still
  runs → proves agents come from code, not disk.
- **End-to-end:** `python3 main.py "look around and tell me where dummy is"` →
  harness dispatches the subagent, which runs `mud.py start`/`send "look"` and
  reports the room. Confirms tools, cwd, and permissions all wired correctly.

## 9. Summary (written out to `summary.md`)

This is the content now living in `03b_subagent_sdk/summary.md`, in Dan's voice.
It uses the four headings Dan asked for: Technical Goal, Technical Uncertainty,
Technical Hypotheses, Technical Observations. It covers the work from first
exploration through the verified end-to-end run.

---

### Technical Goal

I moved the two MUD subagents in `03b_subagent_sdk` off filesystem loading and
onto the Claude Agent SDK. In `03a` the Claude Code CLI finds the agents by
scanning `.claude/agents/*.md`. Here I define the same two agents, `mud-player`
and `mud-agent`, in Python and hand them to the SDK through
`ClaudeAgentOptions(agents=...)`. The definitions live in `agents.py` as
`AgentDefinition` objects. The `mud.py` tool and the `data/*.md` memory files do
not change. Everything stays inside `03b_subagent_sdk`.

### Technical Uncertainty

I did not know the exact `AgentDefinition` contract from memory. Which fields
exist, which are required, and the fact that `AgentDefinition` uses camelCase
while `ClaudeAgentOptions` uses snake_case all had to be checked against the
current docs and the installed package.

I also did not know how to stop the SDK from reading the on-disk agent files. If
it kept scanning `.claude/agents/`, I would load each agent twice and the code
would not be the real source.

The prompts assume a working directory. They call `python3 scripts/mud.py` and
read `data/player.md` by relative path. I was not sure that survived under the SDK
or needed absolute paths.

Last, I wanted the SDK installed without polluting other folders and without
breaking a fresh clone.

### Technical Hypotheses

I expected the two `.md` files to map straight onto `AgentDefinition`. The
frontmatter description becomes `description`, the Markdown body becomes `prompt`,
and I scope `tools` to the four the agents actually use: Bash, Read, Write, Edit.

I expected `setting_sources=[]` to stop the filesystem load and make the code the
only source of the agents.

I expected `cwd` pointed at the in-folder `.claude/agents` to keep the tool and
memory paths working with no prompt rewrites, past fixing one wrong path.

I expected a gitignored `.venv` plus a version-pinned `requirements.txt` to give a
clone-and-run setup without committing machine-specific binaries.

### Technical Observations

The docs and the installed package agree. `claude-agent-sdk==0.2.126` ships
`AgentDefinition` with camelCase fields, `description` and `prompt` required, and
everything else optional. `ClaudeAgentOptions` carries `agents`, `allowed_tools`,
`permission_mode`, `cwd`, and `setting_sources`.

The SDK was not installed anywhere on this machine at the start. `import
claude_agent_sdk` failed with `ModuleNotFoundError`, and the allowlist entries
that referenced it never resolved. I installed it into `03b_subagent_sdk/.venv`
and pinned 0.2.126.

Both prompt bodies pointed at `.../03_subagent_sdk/...` but the folder is
`03b_subagent_sdk`. I fixed the path while lifting the prompts into `prompts/*.md`.

`build_agents()` loads both agents. Each prompt is non-empty at roughly 9.7k
characters, tools scoped to the four, model set to inherit, and no stale `03_`
path remains.

The end-to-end run confirmed the wiring. I renamed the old `.md` files to
`.md.retired` before running, so the run doubled as the negative control. The SDK
still registered `mud-player` and `mud-agent` from code, dispatched `mud-agent`,
and the subagent ran `mud.py start`, `send "look"`, and `stop` from the correct
working directory. It reported the room "A Nexus" with exits north, east, south,
and west, then disconnected clean. No error, 24 seconds, about 23 cents.

---

**Status:** Implemented, restructured, and verified 2026-07-22. Built first, then
flattened the folders to match the instructor's reference repo (see §3): `agents/`,
`data/`, `scripts/` at the top level, no `.claude/`, harness at
`scripts/run_agent.py`. Re-ran §8 verification on the flat layout: static check
loads both agents, and the end-to-end run dispatched `mud-agent` (room "A Nexus",
exits n/e/s/w, clean disconnect, no error, ~24s, $0.23). With no `.claude/` present
at all, the agents can only come from code.

Open items for Dan: (1) reference uses a single `play-mud` agent, this keeps both
per §6.5 — say the word to collapse; (2) the `${TMPDIR}/mud-session/` write from
§6.3 (leave as-is, or redirect into `03b_subagent_sdk/.mud-session/`).
