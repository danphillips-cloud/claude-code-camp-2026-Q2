#!/usr/bin/env python3
"""run_agent.py - drive the MUD subagents via the Claude Agent SDK.

Registers the subagents in code with `AgentDefinition` instead of relying on
Claude Code's filesystem discovery of `.claude/agents/*.md`. `setting_sources=[]`
is what stops the SDK re-reading any on-disk agent files, so this code is the
only source of the agents. Each agent's system prompt is still loaded from a
plain markdown file under `agents/` so the prose stays out of this script.

Usage:
    python scripts/run_agent.py "reach level 7"
    python scripts/run_agent.py            # defaults to "play the MUD"
"""

import asyncio
import os
import sys

from claude_agent_sdk import AgentDefinition, ClaudeAgentOptions, query

# scripts/ sits one level below the project root. The prompts assume the root as
# the working directory: `scripts/mud.py` and `data/*.md` resolve from there, and
# everything stays inside 03b_subagent_sdk.
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AGENTS_DIR = os.path.join(PROJECT_ROOT, "agents")

# Both agents shell out to scripts/mud.py (Bash) and persist state to the two
# data/*.md memory files (Read/Write/Edit). Scope the tools to exactly that.
MUD_TOOLS = ["Bash", "Read", "Write", "Edit"]

# Verbatim from the original .claude/agents/*.md frontmatter `description:`.
MUD_PLAYER_DESCRIPTION = (
    "Play a text MUD (Multi-User Dungeon) with persistent goal tracking and "
    "autonomous gameplay. Use this whenever the user wants to play, explore, log "
    "into, or work toward longer-term objectives in a MUD (tbaMUD/CircleMUD/"
    "DikuMUD on localhost:4000 or other host:port). Trigger when the user gives a "
    'goal like "reach level 7", "defeat the goblin king", "map the forest", or '
    "just says \"play the MUD\" - this agent will autonomously work toward the "
    "goal using memory from previous sessions (player stats, world layout, "
    "completed tasks). Also use for one-off commands, exploration, or NPC "
    "interaction."
)

MUD_AGENT_DESCRIPTION = (
    "Play CircleMUD (localhost:4000) with persistent goal tracking and autonomous "
    'gameplay, continuing the existing "dummy" character\'s saved progress. Use '
    "this whenever the user wants to play, explore, log into, or work toward "
    "longer-term objectives in the CircleMUD instance. Trigger when the user gives "
    'a goal like "reach level 7", "find the minotaur", "map the forest", or just '
    "says \"play the MUD\" - this agent will autonomously work toward the goal "
    "using memory from previous sessions (world layout, completed tasks). Also use "
    "for one-off commands, exploration, or NPC interaction."
)


def _load_prompt(name: str) -> str:
    with open(os.path.join(AGENTS_DIR, name)) as f:
        return f.read()


def build_agents() -> dict[str, AgentDefinition]:
    """Return the subagents keyed by name, ready for ClaudeAgentOptions(agents=...)."""
    return {
        "mud-player": AgentDefinition(
            description=MUD_PLAYER_DESCRIPTION,
            prompt=_load_prompt("mud-player.md"),
            tools=MUD_TOOLS,
            model="inherit",
        ),
        "mud-agent": AgentDefinition(
            description=MUD_AGENT_DESCRIPTION,
            prompt=_load_prompt("mud-agent.md"),
            tools=MUD_TOOLS,
            model="inherit",
        ),
    }


async def run(goal: str) -> None:
    options = ClaudeAgentOptions(
        agents=build_agents(),
        allowed_tools=MUD_TOOLS,
        permission_mode="acceptEdits",
        cwd=PROJECT_ROOT,
        setting_sources=[],  # do NOT load any .claude/agents/*.md from disk
        model="opus",
    )

    async for message in query(prompt=goal, options=options):
        print(message)


def main() -> None:
    goal = sys.argv[1] if len(sys.argv) > 1 else "play the MUD"
    asyncio.run(run(goal))


if __name__ == "__main__":
    main()
