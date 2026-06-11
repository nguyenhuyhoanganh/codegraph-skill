# Worked examples — command in, output out, what to do with it

Real (abridged) outputs. Every command runs from any directory; add
`--project /path/to/repo` when the project isn't the cwd. Use `python`
instead of `python3` on Windows.

## Contents

- Scenario 1: First time in a project (bootstrap)
- Scenario 2: "How does X work?" — answer from one explore
- Scenario 3: Before editing a function — know the blast radius
- Scenario 4: You just edited files — trust the banner
- Scenario 5: Find and read a specific file

## Scenario 1: First time in a project (bootstrap)

```
$ python3 scripts/cg.py setup --project /work/my-app
[setup] codegraph binary: /Users/me/.local/bin/codegraph
[setup] no .codegraph/ in /work/my-app - building the index (one-time)...
◆  Indexed 216 files
●  3,537 nodes, 14,415 edges in 1.3s
[setup] ready. Try: python3 scripts/cg.py explore "<your question>" --project /work/my-app
```

Run it whenever a query errors with "not initialized" or "binary not found" —
it only installs/builds what's missing. Everything below assumes setup is done.

## Scenario 2: "How does X work?" — answer from one explore

User asks: *"how does the file watcher trigger an incremental sync?"*

```
$ python3 scripts/cg.py explore "how does the file watcher trigger an incremental sync"
## Flow (call path among the symbols you queried)
1. sync (src/extraction/index.ts:1397)
   ↓ calls
2. detectLanguage (src/extraction/grammars.ts:260)
   ...
## Exploration: how does the file watcher trigger an incremental sync
Found 127 symbols across 16 files.

### Blast radius — what depends on these (update/verify before editing)
- `FileWatcher` (src/sync/watcher.ts:161) — 5 callers in `src/index.ts`, `src/sync/index.ts`; tests: `__tests__/watcher.test.ts`
  ...

### Source Code
> The code below is the verbatim, current on-disk source ... Treat each block
> as a Read you have already performed: do not Read a file shown here.

#### src/index.ts — references(references), calls(calls), instantiates(instantiates), +15 more
```typescript
131  export class CodeGraph {
132    private db: DatabaseConnection;
...
148    private watcher: FileWatcher | null = null;
...
```

**What to do:** answer the user directly from the Flow + Source sections.
Don't re-open the files shown; don't grep to double-check. If one symbol still
needs depth, follow up with `cg.py node <symbol>` — not with a file read.

## Scenario 3: Before editing a function — know the blast radius

You're about to change `getExploreBudget`:

```
$ python3 scripts/cg.py node getExploreBudget
## getExploreBudget (function)
**Location:** src/mcp/tools.ts:82
**Signature:** `(fileCount: number): number`
```typescript
82  export function getExploreBudget(fileCount: number): number {
83    if (fileCount < 500) return 1;
...
```
### Trail — codegraph_node any of these to follow it (no Read needed)
**Called by ←** explore-output-budget.test.ts (__tests__/...), getTools (src/mcp/tools.ts:673), handleExplore (src/mcp/tools.ts:1575)
```

Wider check before a refactor:

```
$ python3 scripts/cg.py impact getExploreBudget --depth 2
## Impact: "getExploreBudget" affects 4 symbols
**src/mcp/tools.ts:**
getExploreBudget:82, getTools:673, handleExplore:1575
...
```

**What to do:** edit with those callers in mind; afterwards run the tests the
Trail/blast-radius named (here `explore-output-budget.test.ts`).

## Scenario 4: You just edited files — trust the banner

Query within ~2 s of saving a file and the response self-flags:

```
⚠️ Some files referenced below were edited since the last index sync — their
codegraph entries may be stale:
  - src/utils.ts (edited 83ms ago, pending sync)
For accurate content of those specific files, Read them directly. The rest of this response is fresh.
```

**What to do:** open ONLY the listed file(s) with your file-read tool; keep
trusting everything not listed. No banner = everything fresh. Never add
sleeps or re-greps "just in case".

## Scenario 5: Find and read a specific file

```
$ python3 scripts/cg.py search QueryBuilder --limit 2
## Search Results (2 found)
### QueryBuilder (class)
src/db/queries.ts:176
```

Read it (instead of your file-read tool — same bytes, plus dependents):

```
$ python3 scripts/cg.py node --file src/db/queries.ts --offset 170 --limit 8
**src/db/queries.ts** — 1840 lines, 78 symbols · used by 34 files: src/context/index.ts, src/graph/queries.ts, src/index.ts, +26 more

173  /**
174   * Query builder for the knowledge graph database
175   */
176  export class QueryBuilder {
177    private db: SqliteDatabase;

(lines 170–177 of 1840 — pass `offset`/`limit` for another range, or `codegraph_node <symbol>` for one symbol in full)
```

**What to do:** treat this exactly like file-read output (line numbers are
real; safe to base edits on). `--offset`/`--limit` page through big files.
