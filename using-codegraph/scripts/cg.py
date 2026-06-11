#!/usr/bin/env python3
"""One-shot CodeGraph query client.

Spawns `codegraph serve --mcp` (which attaches to the project's shared
CodeGraph daemon, starting it if needed), issues a single MCP tools/call,
prints the text result, and exits. Routing through the daemon instead of
the plain CLI means every answer is fresh: the daemon runs the file
watcher, reconciles the index against the working tree on connect, and
prepends a staleness banner when a referenced file is mid-sync.

Usage:
  cg.py setup                      # bootstrap: install codegraph + build the index if missing
  cg.py explore "<question or symbol names>" [--max-files N]
  cg.py node [SYMBOL] [--file F] [--line N] [--no-code] [--offset N] [--limit N] [--symbols-only]
  cg.py search <query> [--kind K] [--limit N]
  cg.py callers <symbol> [--limit N]
  cg.py callees <symbol> [--limit N]
  cg.py impact <symbol> [--depth N]
  cg.py files [--path P] [--pattern G] [--format tree|flat|grouped] [--max-depth N]
  cg.py status

Common flags: --project PATH (default: cwd), --timeout SECONDS, --raw
Environment:  CODEGRAPH_BIN overrides the `codegraph` binary (may include args).

Works on macOS, Linux, and Windows (use `python` instead of `python3` on Windows).

Exit codes: 0 ok · 1 tool reported an error · 2 setup/usage error · 3 timeout
"""

import argparse
import json
import os
import queue
import shlex
import shutil
import subprocess
import sys
import threading

# When stdout/stderr is a pipe on Windows, Python falls back to the legacy
# code page and crashes printing the server's UTF-8 output (the staleness
# banner). Force UTF-8 with replacement everywhere; line-buffer so our
# progress lines interleave correctly with child-process output.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)

# The daemon answers warm queries in milliseconds, but the *first* call in a
# project pays daemon startup plus a catch-up sync of files edited since the
# last session - on a large repo that reconciliation can take tens of seconds.
DEFAULT_TIMEOUT_S = 120

INSTALL_SH_URL = "https://raw.githubusercontent.com/colbymchenry/codegraph/main/install.sh"
INSTALL_PS1_URL = "https://raw.githubusercontent.com/colbymchenry/codegraph/main/install.ps1"

INSTALL_HINT = (
    "codegraph binary not found.\n"
    "Run the bundled bootstrapper - it installs codegraph and builds the index:\n"
    "  python3 scripts/cg.py setup     (python scripts/cg.py setup on Windows)\n"
    "Manual alternatives: `npm i -g @colbymchenry/codegraph`, or\n"
    f"  curl -fsSL {INSTALL_SH_URL} | sh   (lands at ~/.local/bin/codegraph)\n"
    f"  Windows: irm {INSTALL_PS1_URL} | iex\n"
    "Or point CODEGRAPH_BIN at an existing binary."
)


def resolve_binary():
    override = os.environ.get("CODEGRAPH_BIN")
    if override:
        return shlex.split(override)
    found = shutil.which("codegraph")
    if found:
        # Full path, not the bare name: on Windows the npm shim is
        # codegraph.cmd, which subprocess can only spawn by its real path.
        return [found]
    # Where the official installers put the binary - covers a fresh install
    # whose PATH entry hasn't reached this shell yet.
    home = os.path.expanduser("~")
    candidates = [
        os.path.join(home, ".local", "bin", "codegraph"),
        os.path.join(home, ".codegraph", "current", "bin", "codegraph"),
    ]
    if os.name == "nt" and os.environ.get("LOCALAPPDATA"):
        win_bin = os.path.join(os.environ["LOCALAPPDATA"], "codegraph", "current", "bin")
        candidates += [os.path.join(win_bin, "codegraph.exe"), os.path.join(win_bin, "codegraph")]
    for path in candidates:
        if os.path.isfile(path) and os.access(path, os.X_OK):
            return [path]
    return None


def install_codegraph():
    """Install the codegraph CLI; returns the resolved binary or None."""
    npm = shutil.which("npm")
    if npm:
        print("[setup] codegraph not found - installing with npm i -g @colbymchenry/codegraph ...")
        if subprocess.call([npm, "i", "-g", "@colbymchenry/codegraph"]) == 0:
            binary = resolve_binary()
            if binary:
                return binary
        print("[setup] npm install did not produce a usable binary; trying the official installer...",
              file=sys.stderr)
    if os.name == "nt":
        print("[setup] running the official Windows installer (no Node required)...")
        rc = subprocess.call(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
                              "-Command", f"irm {INSTALL_PS1_URL} | iex"])
    else:
        print("[setup] running the official installer (no Node required)...")
        rc = subprocess.call(["sh", "-c", f"curl -fsSL {INSTALL_SH_URL} | sh"])
    return resolve_binary() if rc == 0 else None


def run_setup(args):
    """Idempotent bootstrap: binary present -> index present -> ready."""
    project = os.path.abspath(args.project)
    binary = resolve_binary()
    if binary is None:
        binary = install_codegraph()
        if binary is None:
            print(INSTALL_HINT, file=sys.stderr)
            return 2
    print(f"[setup] codegraph binary: {' '.join(binary)}")

    index_dir = os.path.join(project, ".codegraph")
    if os.path.isdir(index_dir):
        print(f"[setup] index present: {index_dir}")
    else:
        print(f"[setup] no .codegraph/ in {project} - building the index (one-time)...")
        if subprocess.call(binary + ["init", project]) != 0:
            print("[setup] `codegraph init` failed - see its output above.", file=sys.stderr)
            return 2
    print('[setup] ready. Try: python3 scripts/cg.py explore "<your question>" --project ' + project)
    return 0


def build_parser():
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--project", default=os.getcwd(), help="Project root (default: current directory)")
    common.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_S, help="Seconds to wait for the answer")
    common.add_argument("--raw", action="store_true", help="Print the raw JSON-RPC result instead of its text")

    p = argparse.ArgumentParser(
        prog="cg.py",
        description="Query the CodeGraph index (one-shot MCP call).",
        epilog="Before first use, read references/EXAMPLES.md (sibling of scripts/) — "
               "real outputs of every command and how to act on them.",
    )
    sub = p.add_subparsers(dest="tool", required=True)

    def add_parser(name, help_text):
        return sub.add_parser(name, help=help_text, parents=[common])

    s = add_parser("explore", "PRIMARY: source of all relevant symbols for a question, in one call")
    s.add_argument("query", help='Natural-language question or a bag of symbol/file names ("AuthService login session.ts")')
    s.add_argument("--max-files", type=int, dest="maxFiles", help="Max files to include source from (default 12)")

    s = add_parser("node", "Read one file (like Read) or one symbol's source + caller/callee trail")
    s.add_argument("symbol", nargs="?", help="Symbol name; omit it and pass --file to read a whole file")
    s.add_argument("--file", help="File path or basename: alone = read the file; with SYMBOL = pin an overload")
    s.add_argument("--line", type=int, help="Pin an overloaded symbol to the definition at/near this line")
    s.add_argument("--no-code", action="store_true", help="Symbol mode: omit the body (location/signature/trail only)")
    s.add_argument("--offset", type=int, help="File mode: 1-based first line, like Read")
    s.add_argument("--limit", type=int, help="File mode: max lines, like Read")
    s.add_argument("--symbols-only", action="store_true", dest="symbolsOnly", help="File mode: symbol map only, no source")

    s = add_parser("search", "Locate symbols by name (locations only, no code)")
    s.add_argument("query", help="Symbol name or partial name")
    s.add_argument("--kind", choices=["function", "method", "class", "interface", "type", "variable", "route", "component"])
    s.add_argument("--limit", type=int, help="Max results (default 10)")

    for name, help_text in (("callers", "What calls <symbol>"), ("callees", "What <symbol> calls")):
        s = add_parser(name, help_text)
        s.add_argument("symbol")
        s.add_argument("--limit", type=int, help="Max results (default 20)")

    s = add_parser("impact", "Everything affected by changing <symbol> (run before a refactor)")
    s.add_argument("symbol")
    s.add_argument("--depth", type=int, help="Dependency levels to traverse (default 2)")

    s = add_parser("files", "Indexed file tree with language + symbol counts")
    s.add_argument("--path", help="Restrict to files under this directory")
    s.add_argument("--pattern", help='Glob filter, e.g. "**/*.test.ts"')
    s.add_argument("--format", choices=["tree", "flat", "grouped"])
    s.add_argument("--max-depth", type=int, dest="maxDepth")

    add_parser("status", "Index health: file/node/edge counts, backend, pending sync")

    add_parser("setup", "Bootstrap: install the codegraph CLI and build this project's index if missing")
    return p


def tool_arguments(args):
    if args.tool == "node":
        params = {
            "symbol": args.symbol,
            "file": args.file,
            "line": args.line,
            "offset": args.offset,
            "limit": args.limit,
            "symbolsOnly": args.symbolsOnly or None,
            # The graph answer an agent wants almost always includes the body.
            "includeCode": False if args.no_code else True,
        }
    elif args.tool == "explore":
        params = {"query": args.query, "maxFiles": args.maxFiles}
    elif args.tool == "search":
        params = {"query": args.query, "kind": args.kind, "limit": args.limit}
    elif args.tool in ("callers", "callees"):
        params = {"symbol": args.symbol, "limit": args.limit}
    elif args.tool == "impact":
        params = {"symbol": args.symbol, "depth": args.depth}
    elif args.tool == "files":
        params = {"path": args.path, "pattern": args.pattern, "format": args.format, "maxDepth": args.maxDepth}
    else:  # status
        params = {}
    return {k: v for k, v in params.items() if v is not None}


def main():
    args = build_parser().parse_args()
    if args.tool == "setup":
        return run_setup(args)
    if args.tool == "node" and not args.symbol and not args.file:
        sys.exit("node needs a SYMBOL, a --file, or both (see --help)")

    binary = resolve_binary()
    if binary is None:
        print(INSTALL_HINT, file=sys.stderr)
        return 2

    project = os.path.abspath(args.project)
    # Same upward search the server performs, but failing fast with the fix.
    probe = project
    while not os.path.isdir(os.path.join(probe, ".codegraph")):
        parent = os.path.dirname(probe)
        if parent == probe:
            print(f"CodeGraph isn't initialized for {project}.\n"
                  f"Bootstrap it (installs nothing that's already there):\n"
                  f"  python3 scripts/cg.py setup --project {shlex.quote(project)}", file=sys.stderr)
            return 1
        probe = parent
    # A connection can rarely wedge if it lands exactly as the daemon starts a
    # re-sync; a fresh connection right after succeeds. So: short first attempt
    # to detect the wedge cheaply, full-budget second attempt for genuinely
    # slow first calls (daemon spawn + catch-up sync on a big repo).
    attempts = [min(args.timeout, 25.0), args.timeout]
    for attempt_timeout in attempts:
        try:
            return attempt(binary, project, args, attempt_timeout)
        except queue.Empty:
            continue
    print(f"timed out waiting for codegraph (tried twice, {attempts[0]:.0f}s then {attempts[1]:.0f}s). "
          "A first call in a huge repo can be slow — retry with --timeout 300.", file=sys.stderr)
    return 3


def attempt(binary, project, args, timeout_s):
    """One server connection + tool call. Raises queue.Empty on timeout."""
    proc = subprocess.Popen(
        binary + ["serve", "--mcp", "--path", project],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    )

    lines = queue.Queue()

    def pump(stream):
        for line in stream:
            lines.put(line)
        lines.put(None)

    threading.Thread(target=pump, args=(proc.stdout,), daemon=True).start()
    # Drain stderr so a chatty server can't fill the pipe and block; keep the
    # tail for error reporting.
    stderr_tail = []
    threading.Thread(target=lambda: [stderr_tail.append(l) for l in proc.stderr], daemon=True).start()

    def send(msg):
        proc.stdin.write(json.dumps(msg) + "\n")
        proc.stdin.flush()

    def next_message():
        while True:
            line = lines.get(timeout=timeout_s)
            if line is None:
                raise EOFError("server closed its stdout")
            line = line.strip()
            if not line:
                continue
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                continue  # stray non-JSON output; ignore

    exit_code = 0
    try:
        send({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "codegraph-skill", "version": "1.0"},
        }})
        send({"jsonrpc": "2.0", "method": "notifications/initialized"})
        send({"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {
            "name": "codegraph_" + args.tool,
            "arguments": tool_arguments(args),
        }})

        result = None
        while result is None:
            msg = next_message()
            if msg.get("method") == "roots/list" and "id" in msg:
                # Server-initiated request; we already pinned the root via --path.
                send({"jsonrpc": "2.0", "id": msg["id"],
                      "result": {"roots": [{"uri": "file://" + project, "name": "project"}]}})
            elif msg.get("id") == 2:
                if "error" in msg:
                    print(msg["error"].get("message", json.dumps(msg["error"])), file=sys.stderr)
                    return 1
                result = msg["result"]

        if args.raw:
            print(json.dumps(result, indent=2))
        else:
            for block in result.get("content", []):
                if block.get("type") == "text":
                    print(block["text"])
        if result.get("isError"):
            exit_code = 1

    except (EOFError, BrokenPipeError) as e:
        print(f"codegraph server exited unexpectedly: {e}\n{''.join(stderr_tail)[-2000:]}", file=sys.stderr)
        exit_code = 2
    finally:
        try:
            proc.stdin.close()  # host-side close: proxy detaches, daemon stays warm
            proc.wait(timeout=5)
        except Exception:
            proc.kill()

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
