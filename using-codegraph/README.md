# using-codegraph — Agent Skill

An [Agent Skill](https://agentskills.io) that teaches a coding agent to query
[CodeGraph](https://github.com/colbymchenry/codegraph) — a 100% local
tree-sitter knowledge graph of your codebase — instead of burning tokens on
grep/file-read exploration loops. No MCP server configuration needed: the
bundled `scripts/cg.py` talks to CodeGraph directly.

This file is for humans installing the skill; agents read `SKILL.md`.

## Prerequisites (per machine)

**Python 3** is the only hard prerequisite (preinstalled on macOS/Linux; on
Windows install from python.org and use `python` instead of `python3`).

Everything else is self-bootstrapping: the agent (or you) runs

```bash
python3 scripts/cg.py setup
```

which installs the CodeGraph CLI if missing (via npm, or the official
installer — works on macOS, Linux, and Windows) and builds the project index
(`codegraph init`) if missing. Idempotent — safe to run any time. Manual
install, if you prefer: `npm i -g @colbymchenry/codegraph`, then
`codegraph init` in each project.

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
