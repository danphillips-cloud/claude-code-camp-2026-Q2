# Bouneksha

## Build
gem build boukensha.gemspec
gem install boukensha-0.13.0.gem

## Shared settings.yaml

`settings.yaml` lives at `BOUKENSHA_DIR` root, alongside `.env`, `models/`,
and `prompts/`, and is required before any profile can register real
tools. Minimal working example, confirmed against a live MUD:

```yaml
tasks:
  player:
    provider: anthropic
    model: claude-sonnet-4-6
    allow:
      - look
      - examine
      - check
      - move
      - flee
      - set_position
      - track
      - attack
      - skill_strike
      - consider
      - say
      - tell
      - channel_say
      - get_item
      - drop_item
      - put_item
      - equip_item
      - consume_item
      - cast_spell
      - use_magic_item
      - shop
      - practice
      - save_character
      - send_raw
      - poll
      - mud_status

tools:
  room_survey:
    allow:
      - check
      - look
      - poll
  navigation:
    allow:
      - move

mud:
  host: localhost
  port: 4000

mcp_servers:
  mud:
    command: mud-manager
    args: [--mcp]
    prefix: tbamud
```

Two permission blocks here, not one, and missing either fails silently
rather than loudly:

- `tasks.player.allow` gates the LLM's own tool calls. Default-deny: no
  `allow:` list means the agent gets zero real tools, and instead of
  erroring, it writes a fluent, fabricated session and reports success.
  Nothing in the console output looks wrong when this happens.
- `tools.<hook_name>.allow` (`room_survey`, `navigation`, matching the
  framework's internal hook names) is a separate permissions slice, read
  independently of `tasks.player.allow`, governing the framework's own
  background calls (`player_bootstrap`, `position_refresh`,
  `async_poll`). Missing this one doesn't break a run, the framework
  degrades gracefully around it, but it produces a steady stream of
  `UnknownToolError`s in the session log for calls the agent never made.

`observability.otel` is optional, only needed to point at an OTLP
collector for tracing:

```yaml
observability:
  otel:
    enabled: true
    capture_content: false
    env:
      OTEL_SERVICE_NAME: boukensha
      OTEL_EXPORTER_OTLP_ENDPOINT: http://localhost:4318
      OTEL_EXPORTER_OTLP_PROTOCOL: http/protobuf
      OTEL_TRACES_EXPORTER: otlp
```

# Player profiles

Boukensha keeps shared configuration in `BOUKENSHA_DIR` and player state in
`BOUKENSHA_DIR/profiles/<name>`. Every launch must select an existing profile:

```sh
boukensha --list-profiles
boukensha --profile Andrew
BOUKENSHA_PROFILE=Dummy boukensha
```

Create a profile directory and `profile.yaml` before launching it:

```yaml
player:
  name: Dummy
  password_env: MUD_PASSWORD_DUMMY
  persona: cautious-explorer
  gender: n
  class: warrior

overrides:
  task:
    provider:
    model:
  mud:
    host:
    port:
```

Keep `MUD_PASSWORD_DUMMY` and provider keys in the shared `.env`; never put a
password in `profile.yaml`. Move existing `knowledge.sqlite3`, `sessions/`,
`journal/`, `manager/`, and `telnet/` into the current player's profile.
Shared `settings.yaml`, `.env`, `models/`, and `prompts/` remain at the root.

Runtime exceptions intentionally absorbed by the agent are appended as JSONL
to the active profile's `error.log` (for example,
`.boukensha/profiles/Dummy/error.log`). Records include the exception class,
message, Ruby backtrace, and available session/operation/trace identifiers.
Logging is best-effort and never replaces the concise terminal error.
