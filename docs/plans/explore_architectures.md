## Explore Agent Archtectures

A an issue many professionals have is knowing which model to use and when. may models have overlapping features which can cause confusing results or or leading to higher API useage and costs.

## 1. An agent file with referened files eg. AGENT.md, @~/docs/*.MD









Observations:
- Claude Code will read local files, not pertaining to theloop
- the Agent ended up creating temps to create a socket connection and execute commands, we should be persisting a common interface for the MUD eg. mud_manager 
- When it creates a rigid script and fails to log in it starts going off task looking for config files, its obvious that its script to login and interface is flawed, a mud_manager would remove this obstacle for small models. 



The RESET!
I used /clear
- using Haiku is stuggled, then I gave it the research doc and it wants to make telnet tools, kept wantint to make a ruby tool