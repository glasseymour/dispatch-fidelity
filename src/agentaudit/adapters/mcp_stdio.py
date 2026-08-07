"""A pass-through logger for an MCP stdio server.

Put this between your client and a real MCP server and every `tools/call` gets recorded
without either side knowing. That out-of-band position is the point: a log the agent can
write to is a log the agent can shape, and the whole method depends on ground truth the
measured system cannot reach.

    python -m agentaudit.adapters.mcp_stdio --run-dir audit_runs -- npx -y @scope/server

The proxy speaks no MCP semantics beyond finding `tools/call` requests and matching
responses by id. Anything it does not understand is relayed byte-for-byte, so a protocol
version it has never seen still works.

Limitation, stated rather than hidden: this records execution only. It does not inject a
canary, because a canary has to be a tool the agent believes in, and inventing one inside
a relay would change the toolset the server advertises. For canary coverage, add a canary
tool to the server itself, or use the in-process session.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path


def _write(log_path: Path, record: dict) -> None:
    with open(log_path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")


def _pump(src, dst, on_line) -> None:
    for raw in iter(src.readline, b""):
        try:
            on_line(raw)
        except Exception:
            pass          # never let bookkeeping break the relay
        dst.write(raw)
        dst.flush()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="MCP stdio pass-through logger")
    ap.add_argument("--run-dir", default="audit_runs")
    ap.add_argument("--run-id", default=None)
    ap.add_argument("command", nargs=argparse.REMAINDER,
                    help="-- <server command> [args...]")
    args = ap.parse_args(argv)

    cmd = args.command[1:] if args.command and args.command[0] == "--" else args.command
    if not cmd:
        ap.error("give the server command after --")

    run_dir = Path(args.run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    run_id = args.run_id or f"mcp-{datetime.now(timezone.utc):%Y%m%dT%H%M%S}"
    log_path = run_dir / f"{run_id}.toollog.jsonl"

    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    pending: dict = {}
    seq = [0]
    lock = threading.Lock()

    def on_request(raw: bytes) -> None:
        msg = json.loads(raw.decode("utf-8", "replace"))
        if msg.get("method") == "tools/call":
            params = msg.get("params") or {}
            with lock:
                pending[msg.get("id")] = (params.get("name"), params.get("arguments") or {})

    def on_response(raw: bytes) -> None:
        msg = json.loads(raw.decode("utf-8", "replace"))
        with lock:
            entry = pending.pop(msg.get("id"), None)
            if entry is None:
                return
            seq[0] += 1
            n = seq[0]
        tool, tool_args = entry
        result = msg.get("result", msg.get("error"))
        _write(log_path, {
            "seq": n, "run_id": run_id, "agent_id": "mcp-client",
            "tool": tool, "args": tool_args,
            "result": json.dumps(result, ensure_ascii=False),
            "ts": datetime.now(timezone.utc).isoformat(),
        })

    up = threading.Thread(target=_pump,
                          args=(sys.stdin.buffer, proc.stdin, on_request), daemon=True)
    down = threading.Thread(target=_pump,
                            args=(proc.stdout, sys.stdout.buffer, on_response), daemon=True)
    up.start()
    down.start()
    code = proc.wait()
    down.join(timeout=2)
    print(f"[agentaudit] tool log: {log_path}", file=sys.stderr)
    return code


if __name__ == "__main__":
    sys.exit(main())
