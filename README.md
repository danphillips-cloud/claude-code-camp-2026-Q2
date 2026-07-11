# Claude Code Camp 2026 Q2 — Prep

## Project scenario

You're an AI Engineer at Arcane Loop, a video game studio running a free
text adventure MUD since 2016. A recent expansion + viral streamer brought a
wave of new players, but retention has dropped. Suspected cause: friction in
the player journey.

**Task:** build a Player Journey Agent that plays the MUD like a real user —
maps the world, tracks progression paths, and reports where players get
confused, blocked, bored, or overpowered.

CircleMUD is the test environment — Arcane Loop wants proof the agent can
navigate a traditional MUD before it gets access to the live world, player
data, or proprietary systems.

For repo rules and folder structure, see `CLAUDE.md`.

## Stack decisions

**Model:** Claude Code (flat-rate subscription) as the brain for week 1 —
predictable cost on an agentic loop that makes many calls. Keep the local
`qwen3-coder:30b` in reserve to run the same agent in week 2 as a
cost/capability comparison — that experiment is basically the point of the
course.

**Containers:** Docker CLI + Colima. Watch Colima memory allocation if the
30B model is running locally at the same time — don't double-book RAM on a
24GB machine.

**Cloud (AWS/GCP):** stay local by default — the MUD, memory layer, and loop
are all free to run on a Mac. Only reach for cloud if free credits show up
(Bedrock/Vertex both support Claude Code) or to test a bigger open model than
24GB allows — spot/preemptible, auto-stop when idle, billing alert set
before touching it.
