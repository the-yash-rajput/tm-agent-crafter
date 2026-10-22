---
description: List, switch, add or remove Agent Crafter workspaces (host + API key)
argument-hint: "[name] | add <url> <api_key> [name] | remove <name>"
allowed-tools: Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/crafter_workspace.py:*), Bash(printf:*)
---

Manage Agent Crafter workspaces with `${CLAUDE_PLUGIN_ROOT}/scripts/crafter_workspace.py`.
Arguments: `$ARGUMENTS`

Map the arguments to exactly one script call and run it:

| Arguments | Command |
|---|---|
| *(empty)* | `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/crafter_workspace.py list` |
| `<name>` | `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/crafter_workspace.py use <name>` |
| `add <url> <api_key> [name]` | `printf '%s\n' '<api_key>' \| python3 ${CLAUDE_PLUGIN_ROOT}/scripts/crafter_workspace.py add <url> [name]` |
| `remove <name>` | `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/crafter_workspace.py remove <name>` |

Rules:
- For `add`, the key goes in on stdin exactly as shown, never as a script argument. Do not repeat
  the key anywhere in your reply; the script prints a masked form.
- `add` with a URL but no key: don't ask for the key in chat. Tell the user to run
  `! python3 ${CLAUDE_PLUGIN_ROOT}/scripts/crafter_workspace.py add <url> [name]`, which prompts for it hidden.
- After `add`, mention once that a key typed into a slash command stays in this chat's transcript,
  and that the `!` form above avoids that.
- Show the script's output as-is. On a switch, say the next tool call goes to the new workspace.
  No restart is needed.
- Anything else: show the usage table above.
