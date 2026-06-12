# CodeGraph reference

## Contents

- Installing and upgrading
- Project lifecycle (init, index, sync, status, uninit, unlock)
- `scripts/cg.py` complete reference
- Plain CLI equivalents (and their freshness caveat)
- `codegraph affected` — test impact for CI and hooks
- Native MCP server alternative
- Supported languages
- Troubleshooting
- Embedding as a library

## Installing and upgrading

```bash
# macOS / Linux — self-contained build, no Node.js required
curl -fsSL https://raw.githubusercontent.com/colbymchenry/codegraph/main/install.sh | sh

# Windows (PowerShell)
irm https://raw.githubusercontent.com/colbymchenry/codegraph/main/install.ps1 | iex

# Or via npm (any Node >= 20)
npm i -g @colbymchenry/codegraph
```

The installer puts `codegraph` on PATH but does not modify the current shell — open a new shell, or set `CODEGRAPH_BIN` to the binary path for `cg.py`.

```bash
codegraph upgrade            # update in place (detects bundle vs npm install)
codegraph upgrade --check    # just report whether an update exists
codegraph upgrade <version>  # pin a specific version
```

`upgrade` only exists in releases **newer than 0.9.9** — if it reports `unknown command`, update by re-running the install command above instead (the installer always fetches the latest release).

## Project lifecycle

| Command | Purpose | Flags |
|---|---|---|
| `codegraph init [path]` | Create `.codegraph/` and build the initial index (indexing runs by default; the old `-i` flag is accepted but deprecated) | `-v` verbose |
| `codegraph index [path]` | Full (re-)index | `-f` force re-index, `-q` quiet |
| `codegraph sync [path]` | Incremental update since last index | `-q` quiet (for git hooks) |
| `codegraph status [path]` | File/node/edge counts, SQLite backend, journal mode, pending-sync list | `-j` JSON |
| `codegraph uninit [path]` | Delete `.codegraph/` (removes CodeGraph from the project) | `-f` skip prompt |
| `codegraph unlock [path]` | Remove a stale lock file blocking indexing | |

The index lives entirely in `.codegraph/` (SQLite + daemon socket). Indexing skips dependency/build/cache dirs (`node_modules`, `vendor`, `dist`, `.venv`, `Pods`, …), everything in `.gitignore`, and files > 1 MB. There is no config file; to exclude more, use `.gitignore`; to force-include a default-excluded dir, add a negation like `!vendor/`.

## `scripts/cg.py` complete reference

One-shot MCP call routed through CodeGraph's shared per-project daemon (auto-spawned, lingers ~5 min after the last client). The daemon runs the file watcher and reconciles the index on connect, so answers are freshness-checked — prefer `cg.py` over the plain CLI for queries.

`cg.py` below = `python3 <skill-folder>/scripts/cg.py` by absolute path (`python` on Windows). Common flags on every subcommand: `--project PATH` (default: cwd) · `--timeout SECONDS` (default 120) · `--raw` (raw JSON-RPC result).

```bash
cg.py setup
    # Bootstrap, idempotent, cross-platform (macOS/Linux/Windows): installs the
    # codegraph CLI when missing (npm if available, else the official shell or
    # PowerShell installer) and runs `codegraph init` when .codegraph/ is
    # missing. The only cg.py subcommand that touches the network or system.
cg.py explore "<query>" [--max-files N]
    # Query = natural-language question OR bag of symbol/file names.
    # Returns verbatim source of relevant symbols grouped by file + call paths.
cg.py node [SYMBOL] [--file F] [--line N] [--no-code] [--offset N] [--limit N] [--symbols-only]
    # SYMBOL alone: source + caller/callee trail (body included by default;
    #   every overload's body when the name is ambiguous; pin with --file/--line).
    # --file alone: read the file like Read (<n> + tab + line, --offset/--limit, 2000-line cap)
    #   plus a note of which files depend on it. --symbols-only: structure, no source.
    # Version note: server-side file mode needs CodeGraph > 0.9.9. On older
    #   servers cg.py detects this and reads the file locally itself (same
    #   numbered lines; the dependents note is replaced by "unavailable"),
    #   and --offset/--limit alongside a SYMBOL are ignored with a warning.
cg.py search <query> [--kind function|method|class|interface|type|variable|route|component] [--limit N]
cg.py callers <symbol> [--limit N]
cg.py callees <symbol> [--limit N]
cg.py impact <symbol> [--depth N]          # default depth 2
cg.py files [--path DIR] [--pattern GLOB] [--format tree|flat|grouped] [--max-depth N]
cg.py status
```

Environment: `CODEGRAPH_BIN` overrides the binary (may include arguments, e.g. `CODEGRAPH_BIN="node /path/to/dist/bin/codegraph.js"`; on Windows backslash paths are fine — quote the value if the path has spaces: `CODEGRAPH_BIN="\"C:\Tools My\codegraph.exe\""`).

Exit codes: `0` ok · `1` the tool reported an error (e.g. not initialized, symbol not found) · `2` setup error (binary missing, server died) · `3` timeout.

## Plain CLI equivalents (and their freshness caveat)

`query` (= search), `callers`, `callees`, `impact`, `files`, `status` also exist as direct CLI commands with `-j/--json` output — handy for scripting:

```bash
codegraph query UserService --kind class --json
codegraph callers handleLogin --limit 30
codegraph impact buildContext --depth 3 --json
codegraph files --filter src/ --format flat
```

**Caveat:** the plain CLI opens the SQLite index as-is — no watcher, no catch-up sync. After editing files (or a `git pull`), run `codegraph sync` first or the answers may be stale. `cg.py` does not have this problem (the daemon reconciles on connect). `explore` and `node` have no CLI equivalent — they exist only via MCP, i.e. `cg.py`.

## `codegraph affected` — test impact for CI and hooks

Traces import dependencies transitively to find which test files are affected by changed source files.

```bash
codegraph affected src/utils.ts src/api.ts          # files as args
git diff --name-only | codegraph affected --stdin   # pipe from git
codegraph affected src/auth.ts --filter "e2e/*"     # custom test-file glob
```

Flags: `--stdin` · `-d/--depth N` (traversal depth, default 5) · `-f/--filter GLOB` (what counts as a test file, default auto-detect) · `-j/--json` · `-q/--quiet` (paths only).

Pre-push hook / CI example:

```bash
AFFECTED=$(git diff --name-only HEAD | codegraph affected --stdin --quiet)
[ -n "$AFFECTED" ] && npx vitest run $AFFECTED
```

## Native MCP server alternative

`codegraph install` wires CodeGraph's MCP server directly into agents (Claude Code, Cursor, Codex CLI, opencode, Gemini CLI, Antigravity, Kiro): the agent then gets `codegraph_*` as native tools with the same capabilities as `cg.py`, no script needed. Prefer that for permanent setups; this skill's `cg.py` covers the same ground with zero agent configuration. `codegraph uninstall` reverses it. Non-interactive: `codegraph install --target=claude --yes`, `--print-config <agent>` to preview.

If the MCP server IS configured (`codegraph_*` tools visible), use those tools directly instead of `cg.py` — same daemon, one less process hop.

## Supported languages

Full support: TypeScript/JavaScript (`.ts .tsx .js .jsx .mjs`), Python, Go, Rust, Java, C#, PHP, Ruby, C, C++, Swift, Kotlin, Scala, Dart, Lua, Luau, Svelte, Vue, Liquid, Pascal/Delphi. Partial: Objective-C (`.mm` may parse incompletely). Framework-aware routing (`route` nodes linking URLs to handlers): Django, Flask, FastAPI, Express, NestJS, Laravel, Drupal, Rails, Spring, Gin/chi/gorilla, Axum/actix/Rocket, ASP.NET, Vapor, React Router, SvelteKit, Vue/Nuxt. Cross-language bridges: Swift ↔ ObjC, React Native (legacy bridge, TurboModules, Fabric/Paper views, native→JS events), Expo Modules.

## Troubleshooting

- **"CodeGraph not initialized"** — run `codegraph init` in the project root.
- **First `cg.py` call slow / times out** — daemon startup + catch-up sync after big external changes. `cg.py` already retries once on a fresh connection automatically; if it still times out, raise the budget with `--timeout 300`. Subsequent calls are fast.
- **Missing symbols** — wait ~2 s for the watcher debounce or run `codegraph sync`; check the file's language is supported and not `.gitignore`'d or default-excluded.
- **`database is locked`** — `codegraph status` should show `Journal: wal`; if not, the project sits on a filesystem where WAL can't enable (network shares, WSL2 `/mnt`) — move it to a local disk. Pre-0.9 installs: upgrade.
- **Stale lock blocking indexing** — `codegraph unlock`.
- **Watcher unavailable (sandboxes, `CODEGRAPH_NO_DAEMON=1`)** — run `codegraph sync` manually before querying.
- **Windows + WSL sharing one checkout** — give each side its own index dir via `CODEGRAPH_DIR` (e.g. `.codegraph-win`).
- Env knobs: `CODEGRAPH_WATCH_DEBOUNCE_MS` (default 2000, clamp 100–60000), `CODEGRAPH_DAEMON_IDLE_TIMEOUT_MS` (default 300000), `CODEGRAPH_NO_WATCH=1`, `CODEGRAPH_DIR`.

## Embedding as a library

The npm package exports a programmatic API (`CodeGraph.init/open`, `indexAll`, `searchNodes`, `getCallers/getCallees`, `getImpactRadius`, `buildContext`, `watch`) for embedding in your own Node 22.5+ process — see the project README's "Library Usage" section.
