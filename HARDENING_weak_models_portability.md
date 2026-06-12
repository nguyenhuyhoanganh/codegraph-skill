# Hardening pass: ordinary models, no subagents, any environment

**Goal (requested 2026-06-12):** the skill must stay usable when (a) the host
agent runs an ordinary model, not a frontier one, (b) the agent has no
subagents (single-loop, e.g. Cline), and (c) the skill folder is copied to a
different machine/agent later. Fixes live on this branch
(`report/node-file-mode-bug`), commits `f32a852` (script) and `3ff48cd` (docs).

## Method

Re-read SKILL.md / EXAMPLES.md / REFERENCE.md / cg.py pretending to be a small
model in a fresh environment: for every instruction, ask "what literal command
would I type, from which directory, and what happens when it fails?" Each trap
below is something that produces a dead end for a model that follows
instructions literally and gives up after one error.

## Traps found and fixed

| # | Trap | Who hits it | Fix | Commit |
|---|---|---|---|---|
| 1 | Every doc showed `python3 scripts/cg.py …` — a **relative** path that only works with cwd = the skill folder. Agents work from the user's project, get `No such file or directory`, and a weak model stops there. | Any agent outside Claude Code's base-dir injection; especially Cline | `cg.py` is now defined once, prominently, in SKILL.md and EXAMPLES.md (both mandatory reading) as **the absolute path** to `scripts/cg.py` inside the folder containing SKILL.md, and used consistently everywhere. | `3ff48cd` |
| 2 | The script's own hints repeated the same relative path (`INSTALL_HINT`, the not-initialized hint, the `[setup] ready` next step, `--help`). A weak model copies error output verbatim — and the copied command failed again. | Weak models recovering from any error | All self-referencing hints now print the script's **absolute path** (via `__file__`) with the right interpreter (`python` on Windows, `python3` elsewhere) and quote paths containing spaces. Error messages are now self-healing: copy-paste works from any directory. | `f32a852` |
| 3 | **Real Windows bug:** `shlex.split` in POSIX mode eats backslashes, so `CODEGRAPH_BIN=C:\Tools\codegraph.exe` became `C:Toolscodegraph.exe`. | Anyone on Windows using `CODEGRAPH_BIN` | On Windows, backslashes are doubled before splitting — paths survive, quoted segments still work. Verified: `C:\Tools\codegraph.exe` and `node "C:\one two\dist\codegraph.js"` both parse correctly. | `f32a852` |
| 4 | No escape hatch when **Python itself is missing** (minimal containers): the skill became all-or-nothing. | Sandboxes/containers without python3 | SKILL.md Limitations now points to the plain `codegraph` CLI, which covers 6 of the 8 tools (with the documented `codegraph sync` freshness caveat); only `explore`/`node` need the script. | `3ff48cd` |
| 5 | No `.gitattributes`: a Windows checkout with `autocrlf` writes CRLF into `cg.py`, breaking the shebang when the same clone is reused from WSL/Git Bash, and skewing byte-parity of documented outputs. | Windows↔WSL mixed use of one clone | `.gitattributes` pins `*.py` / `*.md` to LF. | `3ff48cd` |
| 6 | REFERENCE didn't show how to quote a Windows `CODEGRAPH_BIN` with spaces. | Windows users | Example added next to the existing env-var doc. | `3ff48cd` |

## Already in place from earlier passes (kept, verified still working)

- **No-subagent wording:** the only subagent-related instruction is explicitly
  conditional — "Single-loop agents like Cline: ignore, this can't happen."
- **Mandatory worked-examples read** before the first command, with the
  rationalization-blocker ("don't skip because the table looks clear").
- **Version-skew immunity:** capability detection via `tools/list` + local
  file-read fallback for CodeGraph ≤ 0.9.9, so future server versions and the
  current release both work without doc changes.
- **Self-bootstrap:** `cg.py setup` installs the CLI (npm → official installer
  fallback, PowerShell on Windows) and builds the index; every error points to
  the exact recovery command.
- **Non-English questions:** explore guidance tells the agent to query with
  symbol names, not prose, with a Vietnamese example.

## Deliberately NOT done (and why)

- **A `.bat`/`.ps1`/`sh` launcher wrapper** to hide the python3-vs-python
  difference: a second entry point doubles the docs surface and the failure
  modes; the absolute-path shorthand plus self-healing error hints solve the
  same problem with one canonical invocation.
- **Literal absolute paths in EXAMPLES outputs beyond one sanitized sample:**
  examples must show *shape*; the header now tells the agent exactly how to
  resolve the real path once.
- **Translating the skill to Vietnamese:** skill bodies in English remain the
  most reliably-followed format across models; the agent localizes toward the
  user.

## Verification (all on this branch, macOS; logic is platform-neutral)

- `shlex` Windows emulation: both bare and quoted backslash paths parse
  correctly (output in commit discussion).
- `INSTALL_HINT`, not-initialized hint, `[setup] ready`, and `--help` all
  print the absolute script path — confirmed by stripped-PATH and scratch-dir
  runs.
- Functional smoke vs the upstream-main build: `setup` (idempotent path),
  `search` — unchanged behavior.
- `skills-ref validate` — still `Valid skill`.
- Earlier matrices remain valid: published-0.9.9 fallback matrix (5 cases) and
  the clean-environment bootstrap test were re-run unmodified in this branch's
  fix commits.

## Residual risks (honest)

- Windows has still not been exercised live by us; the Windows-specific code
  paths (installer choice, `.cmd` spawning, backslash parsing, UTF-8 piping)
  are written from the platform's documented behavior and the upstream
  installers' sources. The branch is ready for a re-run of the community
  Windows test — against THIS branch, not `main`.
- A model weak enough to ignore the bolded shorthand definition can still type
  `cg.py` literally; the very first error it gets back (`command not found`)
  is adjacent to the definition it skipped, which is the best recovery signal
  text alone can provide.
