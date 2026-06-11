---
name: using-codegraph
description: Use when exploring or modifying a codebase — answering "how does X work", "what calls Y", "what would break if I change Z", tracing a flow from X to Y, locating a symbol, or reading source files. Queries CodeGraph, a local pre-built tree-sitter knowledge graph (SQLite), answering structural questions in one call instead of a grep/glob/file-read loop. Also covers installing CodeGraph, building or refreshing the .codegraph/ index, and finding tests affected by a diff.
license: MIT
compatibility: Requires Python 3 and the codegraph CLI (auto-installable; network needed only for that one-time install). Agent-agnostic — any agent that can run shell commands.
---

# Using CodeGraph

## Overview

CodeGraph is a pre-computed SQLite knowledge graph of every symbol, edge, and file in the project (tree-sitter parsed, 20+ languages, 100% local). One query returns the verbatim source of the relevant symbols PLUS who calls them and what a change would affect — structure you would otherwise re-derive with dozens of grep/file-read calls. Reads are sub-millisecond; the index lags file writes by ~1-2 s via a file watcher.

Reach for it BEFORE and while writing or editing code — not just for questions: edit with the blast radius in view.

All queries go through one script bundled in this skill's `scripts/` folder (it rides CodeGraph's shared daemon, so results are always freshness-checked and the first call's startup cost is amortized across the session):

```bash
python3 scripts/cg.py <tool> ... [--project PATH]   # --project defaults to cwd; use `python` on Windows
```

**MANDATORY: read [references/EXAMPLES.md](references/EXAMPLES.md) in full BEFORE running your first `cg.py` command in this conversation.** It shows each command's real output and the exact action to take on it. Do not skip it because the table below "looks clear" — the table only tells you WHICH command to run; the examples define HOW to use what comes back. Running commands without having read it counts as misusing this skill.

## Setup — once per project

If `.codegraph/` exists in the project root, skip this — start querying. Otherwise run the bundled bootstrapper yourself (don't make the user do it):

```bash
python3 scripts/cg.py setup [--project PATH]
```

Idempotent, works on macOS/Linux/Windows. It installs the codegraph CLI if missing (via npm, or the official installer when npm is absent — that's the only step needing network), then runs `codegraph init` if the index is missing (one-time; seconds on small repos, a few minutes on huge ones). Any query that finds something missing prints the same fix, so you can also just query and follow the error.

## Tool selection by intent

| Question | Command |
|---|---|
| Almost anything: "how does X work", architecture, a bug, "what/where is X", surveying an area | `cg.py explore "<question or symbol names>"` — **PRIMARY, call FIRST; usually the ONLY call needed** |
| "How does X reach/become Y?" — a flow or path | `cg.py explore "X Y"` naming the symbols that span the flow — it surfaces the call path among them, including dynamic-dispatch hops (callbacks, React re-render, JSX children) grep can't follow |
| Read a source file (any time you'd use your file-read tool) | `cg.py node --file src/auth/session.ts` — same line-numbered source a file-read tool gives you (`--offset`/`--limit` work too), plus which files depend on it |
| One symbol you're about to read or edit | `cg.py node MySymbol` — verbatim source + caller/callee trail; for an overloaded name returns EVERY definition's body in one call |
| "Where is the symbol named X?" (location only) | `cg.py search X` |
| "What calls this?" / "What does this call?" | `cg.py callers X` / `cg.py callees X` |
| "What would changing this break?" | `cg.py impact X` (before a refactor) |
| "What's in this project / directory?" | `cg.py files [--path src/]` |
| "Is the index ready / healthy?" | `cg.py status` |
| Which test files does this diff affect? | `git diff --name-only \| codegraph affected --stdin` (plain CLI) |

`explore` accepts a natural-language question OR a bag of symbol/file names (`"AuthService loginUser session.ts"`). Treat the source it returns as already read — do NOT re-open those files.

## Common chains

- **Flow / "how does X reach Y"**: ONE `explore` with the symbol names spanning the flow. Don't reconstruct the path with `search` + `callers`.
- **Onboarding / understanding an area**: ONE `explore` is usually the whole answer; follow up with `node` on a specific symbol only if something is still unclear.
- **Refactor planning**: `search` → `callers` → `impact`. The blast-radius answer comes from `impact`, not from walking callers manually.
- **Debugging a regression**: `callers` of the suspected symbol; widen with `impact` if an unexpected call appears.

## Staleness — trust the banner, don't guess

When a response starts with `⚠️ Some files referenced below were edited since the last index sync…`, the listed files are pending re-index: read those specific files directly with your file-read tool. Every file NOT in the banner is fresh — keep trusting CodeGraph. `cg.py status` lists pending files under "Pending sync".

## Anti-patterns

- **Don't re-verify CodeGraph results with grep.** They come from a full AST parse; re-checking is slower, less accurate, and wastes context.
- **Don't grep first** for a symbol by name — `search` returns kind + location + signature in one call.
- **Don't loop `node` over many symbols** — one `explore` returns them all grouped by file. `node` is for a single symbol.
- **If your agent can spawn subagents (e.g. Claude Code's Explore/Task agents): don't delegate exploration to them** — a subagent greps/reads files and bypasses the index. CodeGraph IS the pre-built index; answer directly with it. (Single-loop agents like Cline: ignore, this can't happen.)
- **Don't open an indexed source file with your file-read tool** — `cg.py node --file` serves the same bytes faster with the blast radius attached.

## When NOT to use

- Literal text searches (string contents, comments, log messages) → grep is the right tool.
- Files CodeGraph doesn't index (configs, docs, lockfiles, anything .gitignore'd) → your file-read tool.
- Correctness validation → still the compiler / test suite / linter's job; CodeGraph supplements them with structural context.

## Limitations

- A tool reporting "not initialized" means `.codegraph/` is missing — run `codegraph init` (Setup above).
- Cross-file resolution is best-effort name matching; ambiguous calls may return multiple candidates.
- The first `cg.py` call in a project pays daemon startup + a catch-up sync (seconds; longer right after large external changes like a `git pull`). Later calls are fast.

## Reference

- [references/EXAMPLES.md](references/EXAMPLES.md) — worked examples: each command's real output and what to do with it (read this if unsure how to use a command or interpret its result).
- [references/REFERENCE.md](references/REFERENCE.md) — everything else: full `cg.py` flags, the plain CLI (`init`/`index`/`sync`/`affected`/`upgrade`/…) and its freshness caveat, `codegraph affected` CI recipes, supported languages, the native MCP-server alternative (`codegraph install`), and troubleshooting (lock errors, WAL, missing symbols, daemon).
