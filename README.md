# Claude Code Camp 2026 Q2

## Project scenario

You're an AI Engineer at Arcane Loop, a video game studio running a free
text adventure MUD since 2016. A recent expansion and a viral streamer
brought a wave of new players, but retention has dropped. Suspected
cause: friction somewhere in the player journey.

**Task:** build a Player Journey Agent that plays the MUD like a real
user, maps the world, tracks progression paths, and reports where
players get confused, blocked, bored, or overpowered.

CircleMUD is the test environment. Arcane Loop wants proof the agent can
navigate a traditional MUD before it gets access to the live world,
player data, or proprietary systems.

## Status

**Week 0** explored the provided MUD sandbox: CircleMUD in Docker, the
`mud_manager` Ruby gem for session handling, a parser that turns
CircleMUD's world files into JSON, and a preview dashboard for browsing
that data.

**Week 1** built `Boukensha`, the agent itself, in thirteen small steps
(`week1_baseline/ruby/`, see `ITERATIONS.md`): an agentic loop, tool
registry, five swappable LLM backends, structured logging, a DSL, a CLI
binary, and context management. Proved it end to end: given only a
general player's guide and no scripted path, the agent navigated a live
MUD it had never seen, for $0.09 and 25 seconds. Full write-up in
`docs/journal/1_week1.md`.

**Week 2** (module 1, observability) found something more useful than
the lesson asked for: the agent can produce a fluent, completely
convincing report of a session that never happened, and a clean-looking
OpenTelemetry trace won't catch it, because execution telemetry
(duration, status) doesn't encode whether the content was real. Found
and fixed two permission bugs that caused it, decided a plain structured
session log beats trace visualization for this job, and pulled the
useful parts of tracing (call duration, hook vs. model origin) into that
log instead of running a separate dashboard. Full write-up in
`docs/journal/2_baseline.md`.

## Repo layout

- `week0_explore/`: MUD sandbox, world parser, preview dashboard
- `week1_baseline/`: the Boukensha agent, built step by step in Ruby
- `week2_capable/`: the reference framework (permissions, lifecycle
  hooks, MCP tool server), used and extended rather than rebuilt from
  scratch
- `docs/journal/`: dated technical write-ups, one per week, with the
  actual evidence: session logs, screenshots, real numbers

## Stack

**Model:** Claude Sonnet 4.6 via the Anthropic API directly, not the
Claude Code subscription, since real per-token cost tracking mattered
here. `log_viz` reads it straight from each session's logged API usage,
not an estimate: $0.09 for a navigation run, $0.47 for a longer
exploration run. The backend layer also supports Ollama and Ollama
Cloud, that was the original plan for a week 2 cost and capability
comparison against a local model, but week 2 turned into the
observability module instead. That comparison hasn't happened.

**Containers:** Docker CLI + Colima. Used for the CircleMUD sandbox since
week 0, and for OpenTelemetry (Jaeger, Tempo, Grafana) in week 2, since
removed after the observability findings, see `docs/journal/2_baseline.md`
for why.

**Cloud (AWS/GCP):** still local-only. Nothing here has needed it.
