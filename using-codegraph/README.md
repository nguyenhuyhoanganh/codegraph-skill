# using-codegraph — Agent Skill

An [Agent Skill](https://agentskills.io) that teaches a coding agent to query
[CodeGraph](https://github.com/colbymchenry/codegraph) — a 100% local
tree-sitter knowledge graph of your codebase — instead of burning tokens on
grep/file-read exploration loops. No MCP server configuration needed: the
bundled `scripts/cg.py` talks to CodeGraph directly.

This file is for humans installing the skill; agents read `SKILL.md`.

## Prerequisites (per machine)

1. **Python 3** (preinstalled on macOS/Linux; on Windows install from python.org and use `python` instead of `python3`)
2. **CodeGraph CLI**:
   ```bash
   npm i -g @colbymchenry/codegraph
   # or, without Node.js:
   curl -fsSL https://raw.githubusercontent.com/colbymchenry/codegraph/main/install.sh | sh
   ```

Then index each project once: `cd your-project && codegraph init`
(the agent will offer to do this itself if you skip it).

## Install the skill

Copy this folder (keeping the name `using-codegraph`) into your agent's skills directory:

| Agent | Personal (all projects) | Project-level |
|---|---|---|
| Claude Code | `~/.claude/skills/using-codegraph/` | `<project>/.claude/skills/using-codegraph/` |
| Cline | `~/.cline/skills/using-codegraph/` | `<project>/.cline/skills/using-codegraph/` |
| Other SKILL.md-compatible agents | see your agent's docs for its skills directory | |

The skill follows the open [Agent Skills specification](https://agentskills.io/specification),
so any agent adopting that standard can use it unchanged. For agents without
skills support, point their rules/instructions file at `SKILL.md` and they can
follow it like any other documentation.

## What's inside

```
using-codegraph/
├── SKILL.md                 # the skill: when/how the agent should query CodeGraph
├── references/REFERENCE.md  # full CLI reference, flags, troubleshooting (loaded on demand)
├── scripts/cg.py            # one-shot CodeGraph query client (Python 3, stdlib only)
└── README.md                # this file
```

Everything runs locally; no data leaves the machine (network is used only for
the one-time CLI install/upgrade). License: MIT, matching CodeGraph itself.

## Known limitations

- Tested on macOS against CodeGraph 0.9.9 (Claude Code as the host agent); Windows is untested.
- The first query in a freshly opened project is slower (daemon startup + index catch-up).
- Very rarely a query can hit a daemon re-sync window and stall; `cg.py` retries on a fresh
  connection automatically.
