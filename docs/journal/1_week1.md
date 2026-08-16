# Week 1 Technical Documentation

Arcane Loop's ask is specific: prove the agent can navigate a traditional
MUD before it ever touches the live world, player data, or proprietary game
systems. Week 0 answered a narrower question, which architecture can even
hold a MUD session. Week 1 built the purpose-built loop that question
pointed to (`week1_baseline/ruby/00_config` through `12_context`, see
`ITERATIONS.md`) and this entry is about the first time that loop actually
had to prove itself against a live server, not a plan.

## Technical Goal
Take the finished baseline agent (`boukensha`, step 11's TUI build) and
run it against a live CircleMUD/tbaMUD instance for real: connect as a
character, read room text, move with intent, and reach a concrete
in-world destination, the Donation Room, without hand-holding beyond an
initial goal and some general navigation knowledge. This is the scenario's
own gate before Week 2's memory/judgment work is allowed to start.

## Technical Uncertainty
- Whether the baseline's own session-handling code (`mud_manager`,
  instructor-provided shared scaffolding under `week0_explore/`) would
  hold up under a real, messy live session, reconnects, an idle character,
  a server-side duplicate-login kick, rather than the clean single-shot
  connects it had only been smoke-tested against.
- Whether a stateless, memory-less single task run (`Boukensha.run`, no
  REPL, no conversation carried between turns) could use a general,
  web-sourced CircleMUD navigation guide accurately enough to reach a
  named destination, given the guide explicitly wasn't written for this
  exact server and stock CircleMUD forks vary in their room layouts.

## Technical Hypotheses
- I expected the agent-loop and tool-calling side to be solid, since
  steps 00-10 were already built and reviewed, but expected the live
  socket-handling path to be the weak point, since it had never been
  exercised against a real, long-lived, occasionally-interrupted
  connection before today.
- I expected the navigation guide to be directionally useful but not
  exactly correct for this server, and expected the real test to be
  whether the agent noticed the mismatch and adapted, rather than whether
  the guide was perfectly accurate.

## Technical Observations

**The stale-socket bug.** The first live connect attempt produced a
self-contradictory state: `mud_status` reported "disconnected," but
`mud_connect` refused with "error: already open," and every gameplay
command failed with "not connected." I didn't trust the agent's own
prose summary of this, per the pre-week lesson about verifying against
raw transcripts, so I pulled the actual tool-call/tool-result pairs
straight from the session's JSONL log (`~/.boukensha/sessions/*.jsonl`):

```
tool_call  mud_status    {}
tool_result mud_status    disconnected
tool_call  mud_connect   {}
tool_result mud_connect   error: already open
```

That confirmed it wasn't a hallucination. Reading `mud_manager/session.rb`
found the actual cause: the reader thread's `ensure` block set
`@closed = true` on any remote-side disconnect but never cleared `@socket`.
`open?` (`@socket && !@closed`) correctly reported false, but `open`'s
own guard (`raise Error, "already open" if @socket`) checked the stale
socket instead, so once the remote end dropped the connection once, the
session was permanently wedged until the whole process restarted.
`lsof -nP -iTCP:4000` during a live drop showed why a real disconnect kept
happening at all, Colima forwards container ports through its own SSH
mux, an extra hop that can reset a connection independent of anything in
CircleMUD or the boukensha code. Fix, in the shared `mud_manager` file:

```ruby
ensure
  @buffer_mu.synchronize do
    @closed = true
    @socket = nil          # was missing; left a dead socket in place
    @buffer_cv.broadcast
  end
end
```

**A second, unrelated regression.** Once the socket bug was fixed, the
very next attempt failed cleanly with `400: system: Input should be a
valid array`, an Anthropic API schema requirement that step 09's own
notes had already found and fixed. Steps 10, 11, and 12 had all silently
regressed back to sending `system` as a raw string. Same one-line fix
(`payload[:system] = [{ type: "text", text: context.system }]`) applied
to both `11_tui` and `12_context`.

**A password typo.** After both code fixes, the next failure was a clean,
correctly-reported "Wrong password" from CircleMUD itself, not a code
bug. `~/.boukensha/settings.yaml` had `password: hellworld` where the
character was actually created with `helloworld`. Worth noting only
because it's a good example of the fixes actually working: real,
distinguishable errors were reaching the surface instead of the earlier
wedge, which was the whole point of the socket fix.

**A clean connect, finally.**

<a href="images/week1-tui-launch.png"><img src="images/week1-tui-launch.png" alt="boukensha TUI launched against 11_tui, config resolved to ~/.boukensha, MUD reachable at localhost:4000" width="700"></a>

**The navigation run.** With the environment actually working, I ran a
single stateless `Boukensha.run` call (Claude Sonnet 4.6, no REPL, no
memory beyond that one call) with a task built from a general CircleMUD
player's guide: start at the Temple of Midgaard, head toward Market
Square, then find the Donation Room, verifying real exits at every step
rather than trusting the guide blindly. The full run, pulled from
`~/.boukensha/sessions/20260816T161312Z-f5eee397.jsonl`:

- 21 iterations, 72 seconds wall time (12:13:12-12:14:24), 123,381 input
  / 2,648 output tokens, $0.41 total.
- The guide was only partly right for this server. It suggested the
  Donation Room sits roughly northwest of Market Square; the agent
  explored west along Main Street instead (Magic Shop, a dead-end at the
  West Gate, the Bakery), hit several dead ends, then backtracked to
  Market Square and north through Temple Square, and found the Donation
  Room was actually east from the Temple of Midgaard itself, one room off
  the starting point the whole time.
- The agent caught the mismatch itself rather than looping on the wrong
  direction: it called `check exits` and `look <direction>` before most
  moves, and each wrong guess resolved in one or two turns, not a stall.
- On arrival, an in-game NPC ("a kind soul") commented on the character
  wandering without a light source and handed over a candle, an
  unscripted, server-side signal that the agent had wandered into unlit
  territory unequipped, exactly the kind of player-experience detail
  Arcane Loop is asking this agent to eventually notice and report on.
- `log_viz` (`week1_baseline/log_viz`, pointed at `~/.boukensha/sessions`
  via `LOG_VIZ_SESSIONS_DIR`) rendered the full transcript, tool calls,
  costs, and raw ANSI-colored MUD output, in the browser, its first real
  exercise since being built in step 6.

## Technical Conclusions
- The baseline's agent loop, tool registry, and logging held up fine
  under real play once the two code bugs were fixed, neither of those
  bugs was in the agentic loop itself. Both were in connection-lifecycle
  edge cases (a thread not clearing shared state, a system-prompt format
  regression) that only a live run against a real, occasionally-flaky
  server would surface. Config- and demo-level testing across steps 00-10
  had never actually exercised a live connection long enough to hit
  either one.
- A stale/wedged session and a distinguishable server error (wrong
  password, or a real API rejection) look completely different once the
  socket bug is fixed. Before the fix, everything downstream looked like
  the same contradictory mess; after, each failure pointed straight at
  its actual cause. That difference alone was worth the fix.
- A general, not-server-specific navigation guide was good enough to
  direct a memory-less agent to a real destination, but only because the
  agent treated it as a hint and verified against actual room text rather
  than trusting it outright. A version of this agent that blindly
  followed the guide's directions would have wandered the same
  Main-Street dead ends without ever recovering.
- This closes the loop on Week 0's takeaway. Every architecture there
  could connect; this purpose-built loop is the first one I've actually
  watched navigate a real destination end to end, hit real obstacles, and
  adapt instead of looping.

## Key Takeaway
Getting into the MUD was never the hard part, for any architecture, in
any week. What Week 1 actually tested was whether a purpose-built loop
could survive the boring, unglamorous failure modes of a real connection,
a thread that doesn't clean up shared state, an API contract that
regressed between steps, a typo in a config file, and still come out the
other side navigating correctly. It did, but only after those failures
were run down with real evidence (raw JSONL logs, `lsof`, actual source
reads) instead of guessed at. Judging whether a player is confused,
blocked, bored, or overpowered is still entirely out of scope here, the
agent can now reliably get somewhere and tell me if the map didn't match
reality. Whether it can tell me a player would have given up by that
point is Week 2's question.
