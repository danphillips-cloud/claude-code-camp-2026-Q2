# Pre-Week 0 Notes — MUD Bakery Exploration Session

## Technical Goal
Player Journey Agent goal: find the bakery in the MUD and list its menu.
Connect directly to `nc localhost 4000`, log in with `dummy` / `helloworld`,
and play turn-by-turn: send movement commands, read room descriptions, and
navigate toward the bakery from in-room text clues. Reading world data files
or the parser output to shortcut the answer isn't allowed.

## Technical Uncertainty
Whether an agent can reliably drive an interactive MUD session over raw `nc`,
with no persistent connection, ANSI-coded output, and touchy login timing,
well enough to navigate and read game state on its own. And whether that
reliability holds across model sizes: a smaller model reasoning its way
through broken timing and a rigid login script is a different problem than a
more capable model doing the same.

## Technical Hypotheses
A more capable model (Sonnet) would be able to hand-roll its way around `nc`'s
timing and login quirks well enough to play the MUD directly. A smaller model
(Haiku) would struggle with the raw protocol and be tempted to shortcut
through the filesystem instead of actually playing it out.

## Technical Observations

### Agent memory: `world.md` / `player.md`
The loop persists everything it learns between turns in two files instead of
re-exploring from scratch on every reconnect. `data/world.md` holds the room
map and shop data:

```
- **Main Street (west side)** — exits: n, e, s, w. N -> **The Bakery**. S -> Armory (unvisited). E -> Market Square.
- **The Bakery** — exits: s only. Baker NPC here. Sign on counter (unread).

## Shops
### The Bakery (accessed via Main Street west of Market Square, then north)
`list` output:
| # | Available | Item | Cost |
|---|-----------|------|------|
| 1 | Unlimited | A danish pastry | 7 |
| 2 | Unlimited | A bread | 14 |
| 3 | Unlimited | A waybread | 71 |
```

`data/player.md` holds current status, checked at the start of every loop:

```
# Player State
- Name: dummy
- Current location: The Bakery
- Status: hungry, thirsty (not yet resolved)
- Last goal completed: locate the bakery and read its menu
```

The full room-by-room map (11 rooms, exits, NPCs) and the list of unexplored
branches (Guild of Thieves, Temple Square, General Store, Armory, etc.) are
in `world.md` itself rather than repeated here.

### Driving the agent over `nc`
Plain `nc localhost 4000` doesn't handle the login prompt or ANSI-coded
output cleanly on its own. What worked, at least for this step, was a fresh
shell command per move: reconnect, replay the full login, then send one
movement command, each separated by `sleep` delays timed to the login and
movement prompts:

```
(sleep 2; printf 'dummy\r\n'; sleep 1.5; printf 'helloworld\r\n'; sleep 1.5; \
 printf '\r\n'; sleep 1; printf '\r\n'; sleep 1; printf 'e\r\n'; sleep 1; \
 printf 'look\r\n'; sleep 1.2) | nc -w 12 localhost 4000
```

This re-sends the login on every single move rather than holding one
connection open, which only works because the server resumes the character
at its last location on reconnect (see below). I have a screenshot of this
pattern for one step, not confirmation it was identical for every move in
the route.

![One of Sonnet's sleep-timed nc pipes, replaying login before a single move](images/sonnet-bakery2.png)

I'm not sure this is the most efficient way to drive the MUD, replaying the
full login on every move is wasteful, but for now it works.

### Agent behavior around the interface
- The agent connected over telnet instead of `nc`, ignoring the CLAUDE.md instructions for the session. I corrected it back to `nc localhost 4000`.
- The agent proposed a Python socket script to work around unreliable `nc` login timing, instead of fixing the timing itself.
- The agent wrote a Python script to load the parsed world-data JSON directly (`shops.json`) to find the bakery's room, and separately read raw object files (`obj/1.json`, room 3009's shop data) to get its menu — both times shortcutting around actual play rather than typing `list` in the game. I shut both down.

![The agent writing a Python heredoc to load shops.json directly instead of playing](images/claude-cheats2.png)

- Claude Code read local files that had nothing to do with the loop it was running.
- The agent wrote throwaway scripts to open a socket connection and run commands by hand instead of using a persistent interface.
- When its login script failed, the agent went hunting through config files instead of questioning the script itself.

### Haiku vs. Sonnet
Haiku 4.5 could not reliably drive the MUD over plain `nc`. It choked on ANSI
color codes and login timing, then repeatedly gave up on direct play instead
of fixing the approach — see the filesystem-shortcut behavior above.

![Haiku stuck on ANSI codes and login timing, proposing it abandon nc for the dashboard or filesystem](images/haiku-tries.png)

Sonnet used the same reconnect-and-replay pattern shown above at least once.
It got from the Dark Alley through Common Square and Market Square to the
bakery without getting stuck, and read the menu back from the game itself.

Haiku's failure mode was giving up on the interface and reaching for the
filesystem. Sonnet's success came from scripting the timing around the
interface instead of avoiding it.

## Technical Conclusions
The hypothesis held. That's a scaffolding problem, not a raw capability gap
I have to just accept: I need one persistent interface to the MUD, something
like `mud_manager`, instead of every run inventing its own login and socket
handling.

![Testing the mud_manager gem as a persistent interface instead of a hand-rolled login script](images/claude-mud-manager1.png)

That leaves a new uncertainty for next week: whether a `mud_manager`
interface actually closes the gap for a smaller model, or whether Haiku
would still find some other way to sidestep genuine play. I haven't tested a
model against `mud_manager` yet, only against raw `nc`.

Other conclusions from this session:
- Room-description-based navigation is enough signal for a Player Journey Agent. No external map is needed.
- Picking the right model for a task is a real problem. Models overlap in what they can do, and that overlap produces inconsistent results and burns API budget I don't need to spend.

Next steps: build `mud_manager` as the shared connection/command interface,
then re-run the same "find the bakery" task on Haiku against it to see
whether the failure mode goes away.

## Key Takeaway
The bottleneck wasn't model intelligence, it was interface scaffolding. Sonnet
solved the timing problem by scripting around `nc`; Haiku gave up and reached
for the filesystem instead. A shared `mud_manager` primitive removes the need
for either model to solve MUD login and timing from scratch every run, which
is a better lever than just picking a bigger model.
