# codegraph-skill

An [Agent Skill](https://agentskills.io) (open `SKILL.md` standard) that teaches coding agents —
Claude Code, Cline, and any other skills-compatible agent — to query
[CodeGraph](https://github.com/colbymchenry/codegraph), a 100% local tree-sitter knowledge graph
of your codebase, instead of burning tokens on grep/file-read exploration loops.

One `cg.py explore` call returns the verbatim source of the relevant symbols, the call paths
between them, and the blast radius of a change — no MCP server configuration required.

## The skill

Everything lives in [`using-codegraph/`](using-codegraph/):

```
using-codegraph/
├── SKILL.md                 # the skill: when/how the agent should query CodeGraph
├── references/REFERENCE.md  # full CLI reference, flags, troubleshooting (loaded on demand)
├── scripts/cg.py            # one-shot CodeGraph query client (Python 3, stdlib only)
└── README.md                # install guide for humans
```

Validated against the spec with `skills-ref validate` ✅

## Quick install

```bash
git clone https://github.com/nguyenhuyhoanganh/codegraph-skill
# Claude Code (all projects):
cp -r codegraph-skill/using-codegraph ~/.claude/skills/using-codegraph
# Cline (all projects):
cp -r codegraph-skill/using-codegraph ~/.cline/skills/using-codegraph
```

The only prerequisite is Python 3 — the rest self-bootstraps on macOS, Linux,
and Windows: `python3 using-codegraph/scripts/cg.py setup` (the agent runs this
itself) installs the CodeGraph CLI and builds the project index if missing.
Details in [`using-codegraph/README.md`](using-codegraph/README.md).

## License

MIT — same as CodeGraph itself.
