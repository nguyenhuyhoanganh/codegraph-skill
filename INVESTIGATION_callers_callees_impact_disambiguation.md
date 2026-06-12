# Investigation: per-definition narrowing for `callers` / `callees` / `impact`

**Opened 2026-06-12** (branch `report/node-file-mode-bug`). Source: field
feedback from running `using-codegraph` under **Cline** against a large Spring
Boot + React project (~3,724 files). Eight issues were reported; this document
covers the three that are **not** pure docs and need a server-schema decision
before coding. The other five were handled in the same branch (camelCase flag
aliases, quiet `setup`, and doc clarifications for class-level `callees`,
reflection/DI callbacks, and the `explore` budget).

## Items in scope

| # | Symptom (Cline) | What the user wanted |
|---|---|---|
| 4 | `callers`/`callees` can't be pinned to one definition when a method name is shared by many classes (`doFilterInternal` across many Spring filters) | A way to say "callers of `doFilterInternal` **in this filter**" |
| 5 | `node` accepts `--file` to disambiguate an overload, but `callers`/`callees` don't | Same `--file` knob on callers/callees |
| 8 | `impact SecurityService` aggregates **both** the class `SecurityService` and a file/other node of the same name → duplicated / mixed results | A way to target just the class |

All three are the same underlying need: **narrow a name-resolved query to one
definition.** `cg.py` exposes that only for `node` today.

## Finding: upstream already supports `file` narrowing on all three

Read the upstream MCP tool schemas directly from
`github.com/colbymchenry/codegraph` (`src/mcp/tools.ts`, `main`):

| Tool | `inputSchema` properties | Required | Has `file`? | Has `line`? | Has `kind`? |
|---|---|---|---|---|---|
| `codegraph_callers` | `symbol`, `file`, `limit`, `projectPath` | `symbol` | **yes** — "Narrow to the definition in this file (path or suffix)" | no | no |
| `codegraph_callees` | `symbol`, `file`, `limit`, `projectPath` | `symbol` | **yes** (same) | no | no |
| `codegraph_impact` | `symbol`, `file`, `depth`, `projectPath` | `symbol` | **yes** (same) | no | no |
| `codegraph_node` (for contrast) | `symbol`, `includeCode`, `file`, `offset`, `limit`, `symbolsOnly`, `line`, `projectPath` | none | yes | **yes** | no |

So upstream resolves #4/#5/#8 with a **single** optional parameter — `file`,
accepting a full path **or a suffix** — on each of the three commands. Notably:

- **`line` is NOT accepted** on callers/callees/impact (only `node` has it). Two
  overloads in the *same file* therefore can't be split apart on these commands
  even upstream — `file` is the finest grain available.
- **`kind` is NOT accepted** either, so the class-vs-file collision in #8 is
  meant to be resolved by `file` (point `impact SecurityService` at
  `SecurityService.java`), not by a kind filter.

## Version caveat (the file-mode trap, again)

This schema is from `main`. The published **0.9.9** release is known to lag
`main` (that is exactly why `node`'s file mode failed — it was a main-only
feature; see `BUG_REPORT_node_file_mode.md`). The original 0.9.9 `tools/list`
dump in that report captured **only** `codegraph_node`, so **we do not yet know
whether 0.9.9's `callers`/`callees`/`impact` carry the `file` property.** Do not
assume they do.

Risk is lower here than it was for file mode, though: file mode failed because
`symbol` was *required and omitted*. Here `symbol` is still sent — we'd only add
an **extra optional** `file`. A strict MCP server could still reject an unknown
property, so the call must be **capability-gated**, not sent blindly.

### Probe to confirm on 0.9.9 (run before implementing)

Against a real published-0.9.9 install (same transport `cg.py` uses):

```bash
# point CODEGRAPH_BIN at the 0.9.9 binary if not on PATH
printf '%s\n' \
  '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"probe","version":"1"}}}' \
  '{"jsonrpc":"2.0","method":"notifications/initialized"}' \
  '{"jsonrpc":"2.0","id":2,"method":"tools/list"}' \
  | codegraph serve --mcp --path /path/to/indexed/project
```

Look at each tool's `inputSchema.properties` for a `file` key. (`cg.py` already
does exactly this check for `node`'s `offset` — see `attempt()` in `cg.py`,
the `tools/list` + schema-property probe.)

## Proposed implementation (pending the 0.9.9 probe)

1. **Add `--file` to `callers`, `callees`, `impact`** parsers in `cg.py`
   (`build_parser`), and include it in `tool_arguments` for those tools.
   Do **not** add `--line` or `--kind` — upstream doesn't accept them on these
   tools, and silently accepting a flag the server ignores is the very
   "silent flag drop" this branch already fixed for `node`.
2. **Capability-gate it**, reusing the existing pattern: when `--file` is passed
   to one of the three, issue `tools/list` on the same connection and check the
   target tool's schema for a `file` property.
   - present → pass `file` through.
   - absent (old 0.9.9) → drop it and print a one-line stderr warning
     ("this CodeGraph version can't narrow callers/callees/impact to one file;
     showing all definitions — disambiguate with `search <name> --kind …` or
     upgrade"), mirroring the node flag-drop warning. The call still runs
     unfiltered rather than erroring.
3. **Docs:** the SKILL.md / REFERENCE.md note added in this branch currently
   says per-definition pinning "is not available yet" — change to document
   `--file` on these three once shipped, while keeping the residual limits:
   same-file overloads (no `line`) and no `kind` filter.

### How this maps back to the reported items

- **#4 / #5** — `cg.py callers doFilterInternal --file JwtAuthFilter.java`
  narrows to that one filter's method instead of aggregating every
  `doFilterInternal`. (`--file` accepts a suffix, so the basename is enough.)
- **#8** — `cg.py impact SecurityService --file SecurityService.java` targets
  the class definition, dropping the same-named file node from the aggregate —
  a real fix, not a text-level dedupe of the rendered output.

## Explicitly out of scope here

- **#1 (class-level `callees` returns nothing).** Different root cause — a class
  has no outgoing call edges; `file` narrowing doesn't change that. Documented
  as a limitation in this branch (use `explore`/`node` for a class).
- **#2 (reflection / DI / framework-dispatch callers).** No static call edge
  exists for `callers` to find regardless of narrowing. Documented; the
  recommended path is `explore` (dynamic-dispatch aware) or route/impact views.
- **#7 (`explore` budget).** Server-side, scales with repo size; documented with
  the `--max-files` widening guidance. Not a narrowing problem.

## Status

- [x] Upstream `main` schema confirmed (callers/callees/impact accept `file`;
      not `line`/`kind`).
- [ ] Confirm the published 0.9.9 schema via the `tools/list` probe above.
- [ ] Implement capability-gated `--file` pass-through on the three commands.
- [ ] Flip the docs note from "not available yet" to documenting `--file`.
- [ ] Verify against both a 0.9.9 install and an upstream-`main` build (the two
      matrices already used in `BUG_REPORT_node_file_mode.md`).
