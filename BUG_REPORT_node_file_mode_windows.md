# Bug report: `cg.py node --file` ("file mode") fails on Windows/arm64 too — CodeGraph 0.9.9

## Summary

Independent confirmation of the bug already filed in `BUG_REPORT_node_file_mode.md`
(found on Linux/aarch64), reproduced from scratch on Windows/arm64 while
dogfooding `using-codegraph` end-to-end against the sample project
`best-practices/` (Spring Boot backend + React/TS frontend).

Every documented `cg.py` subcommand worked correctly **except**
`cg.py node --file <path>` (no `SYMBOL`) — the "read a whole file instead of
`Read`" mode documented in `SKILL.md`'s tool-selection table and in
`references/EXAMPLES.md` Scenario 5. It fails every time with:

```
Error: symbol must be a non-empty string
```

## Environment

| Item | Value |
|---|---|
| Date | 2026-06-12 |
| OS | Windows 11 Pro, build 10.0.26200 |
| Arch | `win32 arm64` (`process.platform`/`process.arch`) |
| Shell | PowerShell / bash (via Claude Code) |
| Python | 3.14.6 (`python`, no `python3` on PATH) |
| Node | v24.16.0 |
| npm | 11.13.0 |
| `npm config get prefix` | `C:\Users\huyho\AppData\Roaming\npm` |
| CodeGraph CLI | `0.9.9`, installed via `npm i -g @colbymchenry/codegraph` (pulls in `@colbymchenry/codegraph-win32-arm64`) |
| `codegraph upgrade --check` | `error: unknown command 'upgrade'` (matches the other report — 0.9.9 has no `upgrade` command) |

## Steps taken

1. Cloned `codegraph-skill` and `best-practices`
   (https://github.com/nguyenhuyhoanganh/best-practices, Spring Boot 3.5 +
   React 19/TS) side by side under one workspace.
2. Ran `python codegraph-skill/using-codegraph/scripts/cg.py setup --project best-practices`.
   - `codegraph` was not on PATH, so `cg.py` auto-installed it via
     `npm i -g @colbymchenry/codegraph` (resolved to `0.9.9`), then ran
     `codegraph init`.
   - Index built successfully: 146 files, 1,897 nodes, 3,202 edges,
     `.codegraph/` ≈ 4.11 MB, backend `node:sqlite`, journal `wal`.
3. Read `SKILL.md`, `references/EXAMPLES.md`, `references/REFERENCE.md`, and
   `scripts/cg.py` to enumerate every documented subcommand/flag.
4. Exercised each one against `best-practices`:
   - `status` — correct file/node/edge breakdown by kind and language.
   - `explore "how does the best practice approval flow work"` — correct
     flow + blast radius + verbatim source with line numbers.
   - `explore "AuthService useAuth authStore"` (symbol bag) — correct.
   - `explore "<the same question translated into Vietnamese>"` — did not
     error, but (as `SKILL.md` itself warns) result quality for prose in
     another language is luck-of-the-match since the matcher is
     identifier-based, not NL.
   - `search BestPracticeService`, `search best-practices --kind route` — correct.
   - `node BestPracticeService` (a class) — correct: returns a structural
     outline (members + signatures), not the full body, as documented for
     container kinds.
   - `node approve` (2 overloads, a method) — correct: returns both full
     bodies + trails.
   - `node BestPractice --no-code` (2 definitions) — correct: lists both
     without bodies.
   - `node BestPractice --file "axon-frontend/src/types/index.ts"`
     (SYMBOL **+** `--file` to pin an overload) — **correct**, returns the
     pinned definition's body.
   - `callers approve`, `callees approve` — correct, including the
     "aggregated across N symbols named X" note.
   - `impact BestPracticeService --depth 2` — correct, 72 affected symbols
     grouped by file.
   - `files --path axon-frontend/src --format tree|flat[--max-depth N]` —
     correct (minor cosmetic note below).
   - `codegraph affected <file>` (plain CLI) — correct, reported no test
     files affected.
   - `node TotallyFakeSymbolXYZ` — correct, clean
     `Symbol "..." not found in the codebase` message.
5. Ran the one remaining documented mode —  **`node` with `--file` and NO
   `SYMBOL`** (Scenario 5 in `references/EXAMPLES.md`, and the "Read a source
   file" row of `SKILL.md`'s tool table):

   ```
   python cg.py node --file axon-backend/src/main/java/com/axon/bestpractice/BestPracticeService.java \
       --offset 60 --limit 15 --project best-practices
   ```

   and also the bare form without `--offset`/`--limit`. **Both fail.**

## The clearest issue: `cg.py node --file <path>` (no SYMBOL) is broken

Output (and with `--raw`, identical on both invocations):

```
Error: symbol must be a non-empty string
```

```json
{
  "content": [
    { "type": "text", "text": "Error: symbol must be a non-empty string" }
  ],
  "isError": true
}
```

### Root cause (traced into the installed package)

`C:\Users\huyho\AppData\Roaming\npm\node_modules\@colbymchenry\codegraph\node_modules\@colbymchenry\codegraph-win32-arm64\lib\dist\mcp\tools.js`:

- The `codegraph_node` tool's `inputSchema` declares `required: ['symbol']`.
- `handleNode(args)` calls `this.validateString(args.symbol, 'symbol')` as its
  **first** statement and returns an error result immediately if `args.symbol`
  is missing or empty. There is no code path that inspects `args.file` first
  or supports a "file-only" read mode at all.

`cg.py`'s `tool_arguments()` correctly omits `symbol` from the JSON-RPC
params when only `--file` is given (per its `{k: v for k, v in params.items()
if v is not None}` filter) — which matches what `SKILL.md` documents — but
CodeGraph 0.9.9's `codegraph_node` simply does not accept that shape. This is
the same root cause already documented for Linux/aarch64 in
`BUG_REPORT_node_file_mode.md`, now confirmed independently on Windows/arm64
with a fresh `npm i -g @colbymchenry/codegraph` install (so it isn't a
stale-binary or platform-specific issue — both native packages,
`codegraph-win32-arm64` and presumably `codegraph-linux-arm64`, ship the same
`0.9.9` `tools.js`).

### Impact

Any agent that follows `SKILL.md` / `references/EXAMPLES.md` Scenario 5
("Find and read a specific file" → `cg.py node --file <path>
[--offset/--limit]`) hits this error on every call and must fall back to its
normal file-read tool — silently defeating that part of the skill's value
proposition (and burning a call + an error round-trip first).

## Other minor observations

- `files --format tree --path axon-frontend/src --max-depth 2`: the header
  still reports the *total* file count (`## Project Structure (20 files)`)
  even though the tree itself is truncated to directory names only at depth 2
  with zero file leaves shown — slightly confusing, but likely intentional
  depth-limiting behavior rather than a bug.
- `node <SYMBOL> --file <path>` (i.e. `--file` used to **pin** an already-named
  symbol, as opposed to file-only mode) works correctly — the bug is
  specific to the `--file`-without-`SYMBOL` invocation shape.

---

## Resolution cross-reference (2026-06-12)

This run independently confirms the root cause already established in
`BUG_REPORT_node_file_mode.md` — and adds two valuable data points:

1. **Third platform, second install path.** Windows/arm64 via
   `npm i -g @colbymchenry/codegraph` reproduces byte-identical behavior to
   Linux/aarch64 via the standalone installer: the failure lives in the
   published `0.9.9` `tools.js` (`required: ['symbol']`,
   `validateString(args.symbol)` first), not in any platform, shell, or
   install-method difference. The trace into
   `@colbymchenry/codegraph-win32-arm64/lib/dist/mcp/tools.js` matches the
   `v0.9.9` git tag exactly.
2. **The run used the pre-fix skill.** The raw server error surfacing
   directly (and `--raw` echoing the server's `isError` result) is only
   possible in `cg.py` *before* commit `1d526d4` on this branch — the fixed
   version never sends a symbol-less `codegraph_node` call to the server; it
   detects the missing capability via `tools/list` and reads the file locally.
   So this report describes `main` (pre-fix) behavior and does not indicate a
   gap in the fix.

### What the same commands produce after the fix (this branch)

Re-verified against the published 0.9.9 release (scratch-HOME install,
official installer; macOS — Windows itself not re-run, but the code paths
involved are platform-neutral: same-connection MCP `tools/list` + local file
read with `os.path` handling for both `/` and `\`):

```
$ python cg.py node --file axon/sub/svc.ts --offset 3 --limit 4 --project <proj>
**axon/sub/svc.ts** — 15 lines · dependents unavailable on this CodeGraph version (needs a release newer than 0.9.9)

3	export function approve(id: string) { return check(id); }
...
(lines 3–6 of 15 — pass `offset`/`limit` for another range, ...)
```

- exit 0; works for nested forward-slash paths and bare basenames
  (resolved through `codegraph_files`).
- One follow-up gap this report exposed **was** fixed on this branch: the
  local fallback used to ignore `--raw`; it now emits the same
  `{"content":[{"type":"text",...}]}` result shape a server file-mode call
  returns.

### Minor observations — triage

- `files --format tree --max-depth N` header showing the total file count
  over a depth-truncated tree: upstream CLI cosmetic behavior (same in
  `v0.9.9` sources), not a skill defect — no action here.
- Vietnamese-prose `explore` being "luck of the match": expected and already
  documented in `SKILL.md` ("matches code identifiers, not prose; query with
  the symbol names the question implies").
