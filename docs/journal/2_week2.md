# Week 2 Technical Documentation

Week 1 answered whether Boukensha could navigate a live MUD on its own.
Week 2's first module, "OTel and Error Logs," asks a different question:
once the agent is actually running, can existing observability tooling
(OpenTelemetry, Jaeger, Grafana Tempo) make its execution legible — and if
not, is a purpose-built alternative view worth building instead of relying
on the existing linear JSONL transcript (`week1_baseline`'s `log_viz`)?

## Technical Goal
Stand up the instructor-provided OpenTelemetry stack
(`week2_capable/observability/`), run Boukensha against it with tracing
enabled, and inspect the resulting traces in both Jaeger and Grafana
Tempo. Then prototype an alternative "Story view" for session data and
compare it against the existing linear transcript, to decide which tool —
trace visualizers, a new narrative view, or the transcript already built
in week1 — actually communicates what the agent did and why.

## Technical Uncertainty
- Whether Jaeger/Tempo's trace visualizations can communicate an agent's
  *decision-making* (why it chose one action over another), or only its
  *execution* (span timing, hierarchy, error status) — those are
  different kinds of information and OTel is built for the second.
- Whether a purpose-built "Story view" over the same JSONL data the
  transcript already uses can close that gap, or whether a strictly
  chronological transcript is actually the more legible format regardless
  of how the data is re-laid-out.
- A smaller, setup-level uncertainty: whether the week2 scaffold (new
  profile-based config system, new Gemfile dependencies including
  Go-backed native gems for the TUI) would install and run cleanly on
  this machine, or reproduce/extend the platform issues week1's bundler
  setup hit.

## Technical Hypotheses
- Expect OTel tracing to be genuinely useful for performance/diagnostic
  questions (span durations, error status, call hierarchy) but to fall
  short of explaining the agent's actual reasoning, since GenAI semantic
  conventions capture metadata (model, token counts) rather than the
  content of a decision.
- Expect the "Story view" prototype to read more naturally than raw spans
  but still lose specific execution detail the linear transcript
  preserves, since narrative grouping and exact chronological order are
  in tension by construction.
- Expect the week2 dependency setup to hit the same class of problem week1
  did (missing platform entry in `Gemfile.lock` forcing a source build
  instead of using a precompiled native gem), rather than a genuinely new
  category of failure — Ruby/Bundler platform resolution, not the
  specific gem, was the actual fragile point in week1.

## Technical Observations
Environment setup for Module 1, before any lesson steps could run:

- Boukensha's config moved to a per-player profile system since week1
  (`boukensha/README.md`): created
  `~/.boukensha/profiles/Dummy/profile.yaml` reusing week1's `dummy`
  MUD account, moved the plaintext password out of `settings.yaml` into
  `~/.boukensha/.env` (`MUD_PASSWORD_DUMMY`) per the new convention
  ("never put a password in profile.yaml"). `boukensha --list-profiles`
  confirmed `Dummy` resolves.
- `bundle install` in `week2_capable/boukensha` failed on `ntcharts`, a
  Go-backed native extension gem, with `Could not find libntcharts.a for
  platform darwin_arm64`. Root cause: `Gemfile.lock`'s `PLATFORMS` list
  only had `ruby` and `x86_64-linux`, so Bundler resolved the source gem
  and tried to compile it locally instead of pulling the precompiled
  `arm64-darwin` variant that rubygems.org actually has for `ntcharts
  0.1.2`. This is the same root cause as a bundler issue from week1 (a
  missing lockfile platform forcing a source build), just surfacing on a
  different gem this time. Fix matched the hypothesis: `bundle lock
  --add-platform arm64-darwin` then `bundle install` succeeded (29 gems
  installed clean, no further platform-specific failures).
- Added the `observability.otel` block to `~/.boukensha/settings.yaml`
  per `observability/README.md` (`enabled: true`, endpoint
  `http://localhost:4318`, protocol `http/protobuf`).
- Started the `jaeger` docker-compose profile
  (`week2_capable/observability/docker-compose.yml`): `docker ps` confirms
  `observability-collector-jaeger-1` and `observability-jaeger-1` both
  running and healthy.

A stale `~/.boukensharc` left over from week1 (`boukensha_path` pointing
at `week1_baseline/ruby/12_context`) was overriding week2's own bundled
lib entirely — `BoukenshaLoader.resolve` checks `BOUKENSHA_PATH`/rc file
before falling back to the gem's bundled lib, so `bin/boukensha` was
loading week1's old code and failing with a `mud_manager` `LoadError`.
Removed the rc file (it lives outside the repo, in `$HOME`, so this has
no effect on anything the instructor would see in the graded repo).

Boukensha's tool architecture also changed since week1: it now ships no
tools of its own and gets everything through MCP
(`mcp_servers.mud` in `settings.yaml`, spawning the `mud-manager` binary
from the `mud_manager` gem with `--mcp`). The gem installed on this
machine was a stale, empty `0.1.0` stub; built and installed week2's real
`0.3.0` from `week2_capable/mud_manager/mud_manager.gemspec`.

**1.2 — ran Boukensha against the live stack** (`--profile Dummy
--no-tui`, piped stdin, same task framing as week1: "go from the Temple
of Midgaard to the Donation Room"). This run surfaced a real bug, and my
first read of it was wrong — corrected below rather than silently
edited, per this project's own contemporaneous-documentation standard.

**What I first thought happened:** I set `mcp_servers.mud.prefix:
circlemud`, but several internal modules (`lib/boukensha/mud/hooks.rb`,
`room_survey.rb`, `navigation/execute_route_tool.rb`) hardcode the
literal string `"tbamud__"` regardless of the configured prefix — despite
`config.rb`'s own comment implying the prefix is freely chosen. I assumed
this explained the `tbamud__check`/`tbamud__look` `UnknownToolError`s and
that the agent's navigation (visible in the console as `look`, `go
north`, `go west`, etc.) was working through some other, unprefixed tool
path. I corrected `prefix: tbamud` and moved on.

**What actually happened:** the prefix was never the real problem. The
session JSONL (`~/.boukensha/profiles/Dummy/sessions/20260823T140625Z-b2d6cd0f.jsonl`)
shows exactly one `chat claude-sonnet-4-6` call for the whole turn
(`iteration: 1`, `reason: completed`) and **zero** `tool_call`/`tool_result`
records after it. The "navigation" I watched scroll by in the console —
multiple rooms, multiple moves — was never real tool execution. Claude
generated it as plain text in a single response, formatting it to look
like a tool-call transcript, because **no real tools were available to
call**: the startup banner read `servers: mud (0)` the entire time.

Root cause, found in `lib/boukensha.rb:507`:

> Build the Permissions for a task from its `allow:` block. Default-deny:
> a task with no `allow:` block may call NOTHING.

`settings.yaml`'s `tasks.player` block had `provider`/`model` but no
`allow:` list, so `task_permissions` returned `Permissions.deny_all` —
every one of the 26 tools `mud-manager --list-tools` actually advertises
(`look`, `move`, `check`, `attack`, …) was rejected at registration,
independent of prefix. The `tbamud__check` prefix fix was real but
incidental; it would have produced the identical `servers: mud (0)` and
the identical hallucinated-navigation behavior either way, since nothing
was ever going to be registered under any prefix. Added the missing
`allow:` block (all 26 tool names from `mud-manager --list-tools`) and
confirmed the fix for free, without spending an API call: the startup
banner alone (before any chat request) now reads `servers: mud (26)`,
zero errors.

This is a materially bigger finding than the lesson's own scope. When an
agent has no usable tools, this build doesn't fail loudly or refuse the
turn — it silently produces a fluent, plausible-looking fabricated
session and the framework accepts it as `reason: completed`. Nothing in
the console output, and nothing about the *shape* of the response, gave
this away; only cross-referencing the JSONL's `tool_call` records against
what the terminal displayed did. Flagged here rather than as a GitHub
issue for now (one-line settings fix, not a code defect — the framework
behaved exactly as `deny_all` says it will), but it's a real
methodological lesson: a text transcript that *looks* like it did
something is not evidence that it did.

**1.3, first pass — Jaeger trace inspection of the flawed (zero-tools)
run**, corroborated against both the Jaeger
API directly and Dan's own screenshots from the browser (search results:
![Jaeger search results for the boukensha
trace](images/week2-jaeger-search-results.png); trace detail waterfall:
![Jaeger trace waterfall showing 7 spans across invoke_agent, iteration,
and their children](images/week2-jaeger-trace-waterfall.png)) — same
trace, same 7 spans, same 4 errors from both sources, independently.

Span hierarchy for trace `4cc8e4760af750f73439933efe468ee1` (`session.id
20260823T140625Z-b2d6cd0f`), confirming "one trace = one top-level turn"
as documented:

```
invoke_agent player                    16,895,970 µs (~16.9s)
├─ player_bootstrap                        1,230 µs  [ERROR]
│  └─ execute_tool check                   1,160 µs  [ERROR]
└─ iteration                           16,893,656 µs (~16.9s)
   ├─ position_refresh                     2,710 µs  [ERROR]
   │  └─ execute_tool look                 2,641 µs  [ERROR]
   └─ chat claude-sonnet-4-6           16,889,456 µs (~16.9s)
```

What's legible from this, cleanly and immediately: total turn duration,
that the LLM call (`chat claude-sonnet-4-6`) is 99.97% of the wall-clock
time, exactly which two calls errored and why (`otel.status_code:
ERROR`, plus the full exception message and Ruby stacktrace attached to
each errored span — `No tool registered as 'tbamud__check'`,
`registry.rb:31`), and GenAI-convention attributes on the tool spans
(`gen_ai.tool.name`, `boukensha.mud_calls`, `session.id`,
`boukensha.tool.initiator: hook`).

What's NOT legible from the trace alone, and is exactly the gap this
whole finding demonstrates: nothing in the span tree indicates that the
`chat` span's 16.9 seconds produced a wholly fabricated response instead
of a real one. Span timing and error status describe *execution*, not
*content* — a 16.9-second successful-looking `chat` span looks
identical whether the model did real work or invented a transcript.
Confirming that required the JSONL's structured `tool_call` records, not
anything Jaeger surfaces. This is the clearest evidence yet for the
lesson's own pre-stated conclusion (section 2 framing): OTel traces
diagnostics and timing well, but not the actual content of what an agent
decided or produced.

**Smaller, unrelated legibility finding from the same session** (![Jaeger
400 error for a malformed trace
URL](images/week2-jaeger-invalid-trace-id.png)): navigating directly to
`localhost:16686/trace/bokensha` (a typo'd URL, not a real trace ID —
missing the "u" in "boukensha") doesn't get a friendly "trace not found."
It surfaces a raw Go error straight through to the browser: `HTTP Error:
strconv.ParseUint: parsing "bokensha": invalid syntax`, `400 Bad Request`,
full JSON error body included. Not a Jaeger bug, and not something the
lesson is directly asking about, but it's a minor data point for the same
2.3 question: Jaeger's happy path (searching by service/session.id) is
fine, its error path leaks implementation details instead of explaining
what a trace ID is supposed to look like.

**1.3, second pass — a genuinely successful run, and a second permission
bug found in the process.** Switched the observability stack from the
`jaeger` docker-compose profile to `compare` (fans every trace out to
both Jaeger and Tempo simultaneously — needed for 1.4 to show the *same*
trace in both UIs). Before re-running, went looking for why the
`tbamud__check`/`look`/`poll` hook errors happened at all, since the
`allow:` fix should have covered it.

Found it in `lib/boukensha/mud/hooks.rb`'s own comments and
`lib/boukensha.rb:462`: the framework's internal hooks
(`player_bootstrap`, `position_refresh`, the async poll) run through a
**separate** permissions slice from the player's own tools —
`tools.room_survey.allow` and `tools.navigation.allow` in `settings.yaml`,
read via `cfg.dig(:tools, tool_name, :allow)`, completely independent of
`tasks.player.allow`. Our settings only had the latter. Added both slices
(`room_survey: [check, look, poll]`, `navigation: [move]`). This one I
did *not* re-verify live before the next run — the hook errors are
cosmetic (framework degrades gracefully around them, per the class
comment "must degrade to the behaviour it had before this existed, never
to a dead REPL"), and a live re-check would have meant a third paid API
call just to confirm a non-blocking error stopped appearing. Flagged as
unverified rather than claimed as fixed.

Re-ran the same task ("go from the Temple of Midgaard to the Donation
Room"). This time it was real: **7 LLM iterations** (`chat
claude-sonnet-4-6` × 7, vs. 1 in the first run), and the JSONL's
`tool_call`/`tool_result` pairs split cleanly by `initiator`:

| initiator | tools called | result |
|---|---|---|
| `hook` | `check`, `look` (×7, `position_refresh`), `poll` (×7, `async_poll`) | all `ok: false` — same missing-permission-slice bug, still present as expected |
| `model` | `look`, `send_raw` (×2), `check`, `move` | all `ok: true` — real execution |

The model's own final summary ("one step East… a kind soul… handed us a
candle") matches the real room layout and an NPC detail week1's journal
also recorded independently — corroborating evidence this was a genuine
navigation, not a repeat of the hallucination. Trace:
`a3dfc59b79ba0c6c8c22bbe6f92f763f` (`session.id
20260823T143010Z-e211344d`), 58 spans total — full hierarchy pulled via
Jaeger's API:

```
invoke_agent player                                24,039,985 µs (~24.0s)
├─ player_bootstrap                                    1,479 µs  [ERROR: no tool 'tbamud__check']
│  └─ execute_tool check                               1,401 µs  [ERROR]
├─ iteration (×6, one per LLM call)
│  ├─ position_refresh                          ~6–12k µs each  [ERROR: no tool 'tbamud__look']
│  │  └─ execute_tool look                                       [ERROR]
│  ├─ chat claude-sonnet-4-6                  1.79s – 4.09s each
│  ├─ async_poll                                  ~7–10k µs each  [ERROR: no tool 'tbamud__poll']
│  │  └─ execute_tool poll                                        [ERROR]
│  └─ execute_tool {look|send_raw|check|move}      15k – 3.1M µs  [ok — real, model-initiated]
│     └─ after_tool                                    ~2–7k µs
```

(6 `iteration` spans hold all 7 chat calls — the 7th iteration's children
weren't fully captured in this excerpt; the pattern above holds
consistently across the ones inspected.)

Legible from this trace, cleanly: exactly which subsystem is broken (the
hook slice, every single time, same error) versus which is working (every
model-initiated call, every time) — laid entirely side by side, same
shape, opposite outcome, single trace. That contrast is something Jaeger
surfaces better than the JSONL does on its own: seeing the two
`execute_tool look` spans (one under `position_refresh`, `[ERROR]`; one
directly under `iteration`, healthy, `tool=look`) sitting next to each
other in the same waterfall makes the "two separate registries" bug
obvious at a glance in a way that scanning JSONL line-by-line did not.

**1.4 — same trace in Grafana Tempo.** Confirmed two ways: via Grafana's
Tempo datasource proxy API (identical trace ID, 58 spans in Tempo exactly
matching Jaeger's 58), and visually, side by side, in Dan's own browser —
Jaeger's waterfall (![Jaeger trace waterfall showing the room_survey span
with its logged UnknownToolError
exception](images/week2-jaeger-run2-waterfall-room-survey-error.png))
and Grafana Explore's Tempo view (![Grafana Explore Tempo view of the
same trace, same span
tree](images/week2-tempo-run2-waterfall.png)) render the identical span
tree — `player_bootstrap`, `position_refresh`, `async_poll`, all 58
spans, same names, same durations, same error markers. The `compare`
profile's fan-out works exactly as documented.

The two UIs present the same data with real differences in emphasis:
Jaeger's timeline is denser (fits more of the tree on screen without
scrolling) and its span detail panel shows the full exception log inline
without an extra click (visible directly: `exception.message = No tool
registered as 'tbamud__look'`, with the stacktrace one expand away).
Tempo/Grafana's view groups by duration more legibly (each span's ms/s
figure sits right in the row label) and adds filter toggles (`Critical
path`, `Errors`, `High latency`) Jaeger doesn't have in the same spot.
Neither surfaces anything the other doesn't — same underlying OTLP data,
different UI conventions for scanning it.

## 2. Evaluate the Trace Visualizations

**2.1 — Jaeger's execution timeline** and **2.2 — Tempo's, on the same
trace**: both walked through in detail above (1.3, 1.4) rather than
repeated here — same trace, same 58 spans, same errors, two UI
conventions for scanning the identical waterfall. Not re-narrating; see
those sections for the specifics (span durations, the
`position_refresh`/`async_poll` error pattern, the side-by-side
comparison screenshots).

**2.3 — what's useful vs. still difficult to understand**, the lesson's
actual question, answered from real evidence rather than assumed:

*Useful, and immediately so:* total turn duration; exactly which calls
failed and why, with the full exception and stacktrace attached to the
span itself (no cross-referencing a separate log needed); the shape of
the agent loop laid out spatially — bootstrap once, then one `iteration`
per LLM round-trip, each with its fixed internal structure
(`position_refresh` → `chat` → `async_poll` → the model's actual tool
call); and, this session's clearest example, spotting a *structural* bug
at a glance — two `execute_tool look` spans with the same name sitting
in different branches of the same tree, one erroring every time, one
succeeding every time, made the "two separate tool registries" root
cause obvious in a way that scanning JSONL line-by-line did not.

*Still difficult, and this is the real finding of the week:* the trace
cannot tell you whether an agent's output was genuine. The first run's
16.9-second `chat` span looked, by every metric OTel captures (duration,
status, GenAI attributes), identical to a real successful call — and it
was actually a complete fabrication, the model narrating a fictional
session in text because it had zero working tools. Nothing in span
timing or status distinguishes "the model did the thing" from "the model
wrote a paragraph describing having done the thing." That distinction
only existed in the JSONL's structured `tool_call`/`tool_result` records,
which is a different data source than what either trace UI shows.

Matching this against the lesson's own pre-stated conclusion — that
Jaeger/Tempo give valuable diagnostics and performance information but
don't communicate the agent's decision-making — the hands-on result
agrees, but with a sharper edge than the lesson states it: it's not just
that the trace doesn't show *why* the agent decided something. It doesn't
show *whether* the agent decided anything real at all. Execution
telemetry and content verification are answering two different
questions, and this week's actual bug is proof, not a hypothetical.

## 3. Experiment with Alternative Session Views

**3.1 — built a minimal "Story view" prototype**, per `plan.md`'s own
scoping ("doesn't need to be a full app... recommend throwaway"): a
~60-line Python script reading the same JSONL format `log_viz` parses,
grouping by iteration and narrating only model-initiated tool calls and
the assistant's own text, with hook-initiated framework noise
(`position_refresh`/`async_poll`, the still-not-fully-fixed room_survey
bug) collapsed into a single footnote count rather than interleaved.
Deliberately kept outside `week2_capable/` (scratchpad, not committed) —
the lesson's own conclusion is to abandon this direction, so it isn't
polished or kept as production code. Run against the real run-2 session
(`20260823T143010Z-e211344d`, the successful navigation):

```
--- Iteration 1 ---
  [plan] Sure! Let me start by looking at the current room to get my bearings.
  agent called tbamud__look(target=room, preposition=at) -> OK
    result: You do not see that here. ...
--- Iteration 2 ---
  [plan] Let me check where I am properly:
  agent called tbamud__look(preposition=at, target=room) -> OK
    result: You do not see that here. ...
--- Iteration 3 ---
  agent called tbamud__look(preposition=north, target=room) -> OK
    result: At the northern end of the temple hall is a statue and a huge altar. ...
--- Iteration 4 ---
  [plan] Good — I can confirm I'm in the Temple of Midgaard. Let me look at the room properly and check exits.
  agent called tbamud__send_raw(command=look) -> OK
  agent called tbamud__check(kind=exits) -> OK
--- Iteration 5 ---
  [plan] The Donation Room is right to the east! Let me head there now.
  agent called tbamud__move(direction=east) -> OK
--- Iteration 6 ---
  agent called tbamud__send_raw(command=look) -> OK
--- Iteration 7 ---
  agent said: "We've arrived! 🎉 Here's a summary of the journey:"
--- 14 internal framework hook errors omitted from narrative above ---
```

**3.2 — compared against `log_viz`'s existing transcript**, not
described from memory but actually run: started `log_viz`
(`week1_baseline/log_viz`, Sinatra, `bundle exec ruby bin/log_viz`)
pointed at `LOG_VIZ_SESSIONS_DIR=~/.boukensha/profiles/Dummy/sessions`,
fetched the rendered page for the same session
(`http://localhost:4568/sessions/20260823T143010Z-e211344d`). Real
differences, not assumed ones:

- `log_viz` shows every one of the 14 hook errors inline, one line each
  (`⚙ tbamud__look() error`, `⚙ tbamud__poll() error`, `⚙
  tbamud__check() error`), interleaved between real events in strict
  chronological order. The Story view collapsed all 14 into one footnote.
- `log_viz` carries real performance data the Story view completely
  omits: per-turn cost (`$0.0114`, `$0.0116`, `$0.0119`...), context
  usage (`3.4k/60.0k`, `7.0k/60.0k`...), and a session-total cost/token
  table by task/provider/model (`$0.0905` total, `27.0k in / 628 out`
  across 7 iterations). None of that exists in the Story view prototype
  as built.
- Both correctly reconstruct the same narrative arc (two failed `look`
  attempts, a self-correction, exits check, the move east, arrival) —
  neither lost or fabricated any step Session data actually contains.

**3.3 — do the new layouts improve readability?** Yes, for one specific
purpose, and no for others. The Story view is more legible *as a
narrative* — the self-correction arc (fumbled `look at room` twice,
corrected via `look north`, confirmed via `check exits`) is immediately
visible without mentally filtering 14 interleaved error lines. But
"improves readability" isn't a single axis: for reconstructing what
happened narratively, Story view wins; for actually debugging why
something failed, or checking cost/performance, `log_viz`'s linear view
is strictly more complete — it hides nothing, the Story view hides the
same 14 errors it would take to diagnose the room_survey bug this whole
session pivoted on, and drops all cost/token data outright.

## 4. Review the Results

**4.1 — side by side**, above (3.1/3.2), same session, both real
renderings, not synthesized.

**4.2 — where important detail is still hard to follow.** In the Story
view: the collapsed hook-error footnote is a real information loss —
if this session's actual finding (the room_survey permissions bug) had
to be *discovered* rather than already known going in, the Story view's
own design would have hidden the exact evidence that led to it. In
`log_viz`'s linear view: nothing is hidden, but the reader has to do the
narrative-reconstruction work themselves — 14 error lines interleaved
with 7 iterations of real content requires active filtering that the
Story view does automatically.

**4.3 — does the new interface improve the overall debugging
experience?** No, not as built, and the comparison shows a real reason
why rather than just agreeing with the lesson's pre-stated answer:
`log_viz` already carries cost, timing, and full error visibility that a
narrative layer would have to explicitly re-add, not just format
differently. A "story" is a compression of the same event stream, and
this session's own throughline — a bug only found by cross-referencing
exact tool-call/result pairs against `initiator` and `ok` fields — is
exactly the kind of thing a narrative compression is built to smooth
over. The hands-on result agrees with the lesson's conclusion, on real
evidence: the linear transcript stays the better tool for debugging,
though the Story view's narrative framing is not without any value —
it would make a reasonable *second* view (e.g., a summary tab) layered
on top of `log_viz`'s existing detail, not a replacement for it.

## 5. Decide the Next Direction

**5.1 — keep OpenTelemetry for diagnostics/performance.** Real
infrastructure now exists to point to: the `docker-compose` profiles
(`debug`/`jaeger`/`tempo`/`compare`), the `observability.otel` settings
block, and two real traces that found and confirmed two separate
permission bugs this session — this isn't a hypothetical capability, it
already found something.

**5.2 — return to the linear session view (`log_viz`) for understanding
agent behavior.** Confirmed directly in 3.2/4.3: it's more complete than
the Story view alternative, and completeness is what let this session
actually diagnose the hallucination and the permissions bugs.

**5.3 — shift focus back to gameplay/judgment features.** Per this
session's own scope conversation: `week2_capable/` is the instructor's
own reference implementation, not a required checklist — we've covered
the two "Capabilities" items (permissions `allow:`, lifecycle hooks) that
matter most directly to this lesson's own thread, with real evidence
(two found-and-fixed bugs) rather than a shallow pass. `mud_monitor`
(the unified observability dashboard) and the optimization items
(RoomParser, BERT candidate extraction) are explicitly out of scope for
this pass — week3 territory, not revisited here.

**Follow-up — observability stack removed (2026-08-23, same session).**
After writing 5.1–5.3 above, watched two clips from the instructor's own
next-lesson video (screenshots, searched "otel" in the transcript) saying
almost exactly what 2.3's finding already implied: "what I want to see
doesn't necessarily fit in that trace and span information and requires
me to make this custom view... am I going to add that model stuff right
now? No, I'm just going to ignore it for now... we have error logging and
we do have performance stuff if we want to use it later." That's
independent corroboration of this entry's own 2.3 finding, not new
evidence on its own — but it prompted revisiting 5.1 itself rather than
just noting the coincidence.

`week2_capable/observability/` (the Jaeger/Tempo/Grafana docker-compose
stack: collector configs, `docker-compose.yml`, Grafana provisioning) has
been removed from the repo (`git rm -r week2_capable/observability`).
Reasoning, checked directly rather than assumed:

- Every field Jaeger's UI actually proved useful for in 2.3 (span
  duration, the hook-vs-model distinction that exposed the tool-registry
  bug, per-call trigger phase) is already present, verbatim, in the JSONL
  session log `log_viz` was already parsing — `duration_ms`, `initiator`,
  `trigger` on every `tool_call`/`tool_result` record. It was being
  discarded by `log_viz/lib/log_viz/session.rb`'s parser, not missing
  from the data.
- Surfaced those three fields into `log_viz` instead: `session.rb` (new
  `tool_initiator`/`tool_duration_ms`/`tool_trigger` struct fields),
  `session.erb` (hook/model badges + a duration badge per tool call),
  `style.css` (distinct colors for `hook` vs `model`). Verified against
  the real week2 session (`20260823T143010Z-e211344d.jsonl`) with an
  actual server render (`curl` against a running `log_viz` instance),
  confirming badges like `hook · before_turn` and `1ms` appear in the
  rendered HTML — not just claimed to work.
- Net effect: the diagnostic value OTel/Jaeger provided this session
  (2.3) is now available in the one view already established as more
  complete for understanding agent behavior (5.2), without running a
  second stack (4 containers: collector, Jaeger, Tempo, Grafana)
  alongside it.
- This does **not** remove OTel instrumentation itself —
  `observability.otel` stays `enabled: true` in `settings.yaml`; only the
  local visualization backends are gone. The emission path is still there
  to point a collector at later if a genuinely trace-shaped question comes
  up that JSONL can't answer (e.g. cross-service latency).

This supersedes 5.1 rather than silently replacing it: 5.1 was a real
conclusion from the evidence available at that point in the session; this
follow-up is a separate, later decision made with additional information
(the instructor's own reversal, plus directly confirming the
data-already-exists/rendering-gap) that changes what actually stays in
the repo.

## Technical Conclusions

All three hypotheses from the top of this entry held, with more nuance
than assumed going in:

- OTel is genuinely useful for diagnostics (confirmed: found two real
  permission bugs via span/error inspection) but does not — cannot —
  reveal decision *content*, up to and including whether a "successful"
  16.9-second LLM call was real or entirely fabricated. This is a
  sharper finding than "doesn't show reasoning": it doesn't show whether
  reasoning happened at all.
- The Story view read more naturally for narrative reconstruction, exactly
  as hypothesized, but lost real diagnostic value (cost data, complete
  error visibility) that the hypothesis didn't anticipate — narrative
  framing and information completeness turned out to be in real tension,
  not just a stylistic tradeoff.
- The week2 dependency setup did hit the same class of problem as
  week1 (missing `Gemfile.lock` platform entry), confirming that
  hypothesis directly — though the actual blocking issues this session
  (default-deny permissions, the separate `room_survey`/`navigation`
  permission slice) were new uncertainties, not anticipated by any of the
  hypotheses above. Worth noting as new uncertainty spun off for later:
  is there a third, undiscovered permission slice anywhere else in this
  framework that would silently degrade the same way?

Next steps: the `room_survey`/`async_poll` hook errors are diagnosed but
not re-verified live (noted in 1.3, second pass) — a future session
should confirm the fix actually clears them. `mud_monitor` and the
optimization/knowledge-graph work stay explicitly deferred to week3.

## Key Takeaway

An observability trace can tell you exactly how long something took and
exactly that it errored — it cannot tell you whether an agent's
apparent success was real, and this week proved that with an actual bug,
not a thought experiment.
