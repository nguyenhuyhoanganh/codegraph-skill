# Bug report: `cg.py node --file` ("file mode") does not work on CodeGraph 0.9.9

## Summary

While dogfooding `using-codegraph` end-to-end (setup + every documented `cg.py`
subcommand) against the sample project `best-practices/` (a Spring Boot
backend + React/TS frontend), every command worked correctly **except**
`cg.py node --file <path>` (the "read a whole file instead of `Read`" mode
documented in `SKILL.md` and `references/EXAMPLES.md`, scenario 5).

It fails with:

```
Error: symbol must be a non-empty string
```

Root cause: the `codegraph_node` MCP tool exposed by the installed
**CodeGraph CLI v0.9.9** (the latest version on npm at the time of testing —
there is no newer version, and `codegraph upgrade` does not exist in 0.9.9)
declares `symbol` as a **required** string parameter and has **no**
`offset` / `limit` / `symbolsOnly` parameters at all. `cg.py` (per
`SKILL.md`/`EXAMPLES.md`) sends `{file, offset, limit, symbolsOnly,
includeCode}` without `symbol` when the user passes only `--file`, which the
server rejects outright. The "file mode" of `codegraph_node` described in
this skill's docs does not exist in the currently-installed/available
CodeGraph release.

## Environment

| Item | Value |
|---|---|
| Date | 2026-06-12 |
| OS | Linux 7.0.0-15-generic (Ubuntu, aarch64) |
| `uname -a` | `Linux hoanganh 7.0.0-15-generic #15-Ubuntu SMP PREEMPT_DYNAMIC Wed Apr 22 15:54:12 UTC 2026 aarch64 GNU/Linux` |
| Python | 3.14.4 |
| Node | v24.16.0 |
| npm | 11.13.0 |
| `npm config get prefix` | `/usr` (global installs need root → EACCES for normal user) |
| CodeGraph CLI | `0.9.9` (`linux-arm64`), installed at `/home/hoanganh/.codegraph/versions/v0.9.9`, linked to `/home/hoanganh/.local/bin/codegraph` |
| `npm view @colbymchenry/codegraph version` | `0.9.9` (same as installed — not a stale-binary issue) |
| `codegraph upgrade` | `error: unknown command 'upgrade'` (not present in 0.9.9, despite being documented in `references/REFERENCE.md`) |
| Project under test | `best-practices/` (untracked sample app in this repo): Spring Boot backend (`axon-backend`, Java) + Vite/React frontend (`axon-frontend`, TS/TSX) |

## Steps to reproduce

### 1. Bootstrap (worked, with one fallback)

```bash
$ python3 using-codegraph/scripts/cg.py setup
[setup] codegraph not found - installing with npm i -g @colbymchenry/codegraph ...
npm error code EACCES
npm error syscall mkdir
npm error path /usr/lib/node_modules/@colbymchenry
... (permission denied, npm prefix is /usr)
[setup] npm install did not produce a usable binary; trying the official installer...
[setup] running the official installer (no Node required)...
Installing CodeGraph v0.9.9 (linux-arm64)...
Installed to /home/hoanganh/.codegraph/versions/v0.9.9
Linked     /home/hoanganh/.local/bin/codegraph
[setup] codegraph binary: /home/hoanganh/.local/bin/codegraph
[setup] no .codegraph/ in /home/hoanganh/Desktop/WorkSpace/codegraph-skill - building the index (one-time)...
◆  Indexed 147 files
●  1,922 nodes, 3,270 edges in 338ms
[setup] ready.
```

The npm fallback worked correctly and is not itself a bug (this user account
has no write access to `/usr/lib/node_modules`), but it's worth noting the
fallback installer also lands on 0.9.9 — there is no newer build to fall
forward to.

### 2. Capabilities that worked correctly

All run with `--project best-practices`:

| Command | Result |
|---|---|
| `status` | Correct counts (147 files, 1922 nodes, 3270 edges, by-kind/by-language breakdown). |
| `files` / `files --path best-practices/axon-backend/.../auth` | Correct project tree, scoped correctly. |
| `explore "AuthController AuthService JwtService login"` | Returned 80 symbols / 23 files, correct "Blast radius" section (callers + missing-test warnings) and verbatim source for `AuthController.java`, `AuthService.java`, `authStore.ts`, `application.yml`. |
| `search BestPracticeService` | 10 results: class, fields referencing it, file, and 3 of its methods, each with correct file:line. |
| `search "AuthService" --kind class` | Correctly filtered to 1 result. |
| `search login` (ambiguous name) | 7 results spanning a TS function, a Java method, a React component, a route, and an import — all correctly typed/located. |
| `node BestPracticeService` | Correct class outline (32 members with file:line + signatures) + "Called by" trail. |
| `node BestPracticeService --file <path> --offset 60 --limit 15` | Returns successfully, but **silently ignores `--file`/`--offset`/`--limit`** — output is identical to plain `node BestPracticeService` (see "Secondary issue" below). |
| `callers create` | 11 callers across frontend + backend, correctly aggregated across 9 same-named `create` symbols. |
| `callees toggleLike` | 7 callees, correctly aggregated across 2 same-named `toggleLike` symbols. |
| `impact JwtService --depth 2` | 36 affected symbols across 5 files (service, controller, filter, test, callers). |
| Staleness banner | Appended a line to `AuthService.java`, immediately ran `explore "AuthService"` → got `⚠️ Some files referenced below were edited since the last index sync ... AuthService.java (edited 75ms ago, pending sync)`. Reverted the edit afterwards. |
| `codegraph affected --stdin` (plain CLI) | Ran correctly (reported "No test files affected"). |

### 3. The bug: `node --file` (file-only mode)

```bash
$ python3 using-codegraph/scripts/cg.py node --file \
    best-practices/axon-backend/src/main/java/com/axon/bestpractice/BestPracticeService.java \
    --offset 60 --limit 15 --raw

{
  "content": [
    {
      "type": "text",
      "text": "Error: symbol must be a non-empty string"
    }
  ],
  "isError": true
}
```

Reproduced both with `--project best-practices` (relative path from repo
root) and with `cwd=best-practices` + `--project .` — same error either way,
so it is not a project-path resolution issue.

### 4. Root cause — MCP tool schema dump

Queried `tools/list` directly against `codegraph serve --mcp --path .`
(same transport `cg.py` uses):

```json
{
  "name": "codegraph_node",
  "description": "SECONDARY (after codegraph_explore): get ONE symbol in full ...",
  "inputSchema": {
    "type": "object",
    "properties": {
      "symbol": { "type": "string", "description": "Name of the symbol to get details for" },
      "includeCode": { "type": "boolean", "default": false },
      "file": { "type": "string", "description": "Optional: disambiguate an overloaded name to the definition in this file ..." },
      "line": { "type": "number" },
      "projectPath": { "type": "string" }
    },
    "required": ["symbol"]
  }
}
```

Observations:

- `symbol` is **required** — there is no way to call `codegraph_node` without
  it, so `cg.py node --file <path>` (which omits `symbol`) can never succeed
  against this server version.
- The schema has **no `offset`, `limit`, or `symbolsOnly` properties** at
  all. The entire "file mode" (`--offset`/`--limit`/`--symbols-only`,
  documented in `SKILL.md` lines 40/162-164 and `EXAMPLES.md` scenario 5) is
  not implemented by `codegraph_node` in v0.9.9 — `file` here only means
  "disambiguate an overloaded symbol", matching the `--file`+symbol behavior
  observed above (point 2: it works but silently ignores offset/limit).

Full tool list returned by v0.9.9 (for reference — no separate
file-reading tool exists either):
`codegraph_search, codegraph_callers, codegraph_callees, codegraph_impact, codegraph_node, codegraph_explore, codegraph_status, codegraph_files`.

### 5. Secondary issue: `node SYMBOL --file ... --offset ... --limit ...` silently drops flags

```bash
$ python3 using-codegraph/scripts/cg.py node BestPracticeService \
    --file best-practices/axon-backend/src/main/java/com/axon/bestpractice/BestPracticeService.java \
    --offset 60 --limit 15 --raw
```

returns the *full* class outline (all 32 members), identical to plain
`node BestPracticeService` — `--offset`/`--limit` had no effect. This is
consistent with the schema above (no such params exist server-side), but
`cg.py` accepts these flags without warning, which can mislead an agent into
thinking it got a windowed view of the file when it got the whole-symbol
outline instead.

## Impact on the skill

- `SKILL.md`'s tool-selection table lists `cg.py node --file ...` as *the*
  way to "Read a source file (any time you'd use your file-read tool)", and
  the "Anti-patterns" section explicitly tells the agent **not** to fall back
  to its file-read tool. With CodeGraph 0.9.9 (the only version currently
  installable), following that instruction literally produces a hard error
  with no useful fallback hint (the error message is just "symbol must be a
  non-empty string" — it doesn't point back to `setup`/`--help` like other
  `cg.py` errors do).
- Everything else in the skill (the actual high-value features — `explore`,
  `search`, `callers`/`callees`, `impact`, `node <symbol>`, `files`,
  `status`, staleness detection) works exactly as documented and is
  genuinely useful — this is not a "the skill is broken" finding, just one
  documented capability that doesn't exist in the shipped CLI version.

## Suggested follow-ups (not implemented by this report)

1. In `SKILL.md`/`EXAMPLES.md`, gate the `node --file` ("file mode") guidance
   behind a version check, or remove/rewrite it until a CodeGraph release
   that implements `offset`/`limit`/`symbolsOnly` and a symbol-less call is
   published.
2. Have `cg.py` detect this specific server error (`"symbol must be a
   non-empty string"` when `args.symbol` is falsy) and print a clear message
   pointing the agent back to its normal file-read tool, instead of
   surfacing the raw server error.
3. Have `cg.py` warn (not silently succeed) when `--offset`/`--limit`/
   `--symbols-only` are passed alongside a `symbol` but the server's
   `codegraph_node` schema doesn't support them, so agents don't believe they
   received a windowed file view.
