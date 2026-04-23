#!/usr/bin/env python3
"""
Multi-Agent Dashboard Client — Python helper for emitting events.

Usage from orchestration scripts:

    from dashboard_client import Dashboard

    db = Dashboard()                   # auto-connects via HTTP to localhost:9121
    db.workflow_start("myproject", "/path", "Build a REST API")
    db.phase_start(1)
    db.agent_spawn("explorer-1", "explorer", phase=1)
    db.agent_tool_call("explorer-1", "read_file", file="src/main.py", iteration=3)
    db.agent_complete("explorer-1", summary="Done", artifacts=["report.yaml"])
    db.phase_complete(1)
    db.workflow_complete()

Or use the ensure_server() helper to auto-start:

    from dashboard_client import ensure_server
    db = ensure_server()  # starts server if needed, opens browser
"""

import json
import time
import os
import subprocess
import sys
import urllib.request
import urllib.error


class Dashboard:
    """Client for the Multi-Agent Dashboard server (single-port aiohttp)."""

    def __init__(self, url="http://localhost:9121"):
        """
        url: Base URL of the dashboard server (HTTP + WS on same port).
        """
        self.url = url.rstrip("/")

    def _send(self, event):
        event["timestamp"] = time.time()
        data = json.dumps(event).encode("utf-8")
        try:
            req = urllib.request.Request(
                f"{self.url}/event",
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            urllib.request.urlopen(req, timeout=3)
        except Exception:
            # Fire-and-forget — don't crash the orchestrator if dashboard is down
            pass

    # ── Workflow events ──────────────────────────────────────
    def workflow_start(self, name="", path="", requirement=""):
        self._send({
            "type": "workflow.start",
            "project": {"name": name, "path": path, "requirement": requirement},
        })

    def workflow_complete(self):
        self._send({"type": "workflow.complete"})

    def workflow_fail(self, error=""):
        self._send({"type": "workflow.fail", "error": error})

    # ── Phase events ─────────────────────────────────────────
    def phase_start(self, phase):
        self._send({"type": "phase.start", "phase": phase})

    def phase_complete(self, phase):
        self._send({"type": "phase.complete", "phase": phase})

    # ── Agent events ─────────────────────────────────────────
    def agent_spawn(self, agent_id, role, phase=None, engine="delegate_task"):
        self._send({
            "type": "agent.spawn",
            "agent_id": agent_id,
            "role": role,
            "phase": phase,
            "engine": engine,
        })

    def agent_tool_call(self, agent_id, tool, file=None, iteration=0):
        self._send({
            "type": "agent.tool_call",
            "agent_id": agent_id,
            "tool": tool,
            "file": file or "",
            "iteration": iteration,
        })

    def agent_thinking(self, agent_id, text):
        self._send({
            "type": "agent.thinking",
            "agent_id": agent_id,
            "text": text,
        })

    def agent_complete(self, agent_id, summary="", artifacts=None):
        self._send({
            "type": "agent.complete",
            "agent_id": agent_id,
            "summary": summary,
            "artifacts": artifacts or [],
        })

    def agent_fail(self, agent_id, error=""):
        self._send({
            "type": "agent.fail",
            "agent_id": agent_id,
            "error": error,
        })

    # ── Metrics ──────────────────────────────────────────────
    def update_metrics(self, **kwargs):
        self._send({
            "type": "metrics.update",
            "metrics": kwargs,
        })


# ── Convenience: start server if not running ─────────────────
def ensure_server(port=9121):
    """Start the dashboard server if not already running. Returns Dashboard client."""
    import socket

    url = f"http://localhost:{port}"
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.connect(("localhost", port))
        sock.close()
        # Already running
        return Dashboard(url=url)
    except (ConnectionRefusedError, OSError):
        pass

    # Start server
    server_script = os.path.join(os.path.dirname(__file__), "dashboard_server.py")
    subprocess.Popen(
        [sys.executable, server_script, "--port", str(port)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    # Wait for it to start
    for _ in range(30):
        time.sleep(0.25)
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect(("localhost", port))
            sock.close()
            break
        except (ConnectionRefusedError, OSError):
            continue

    # Open browser
    try:
        import webbrowser
        webbrowser.open(f"http://localhost:{port}/")
    except Exception:
        pass

    return Dashboard(url=url)


if __name__ == "__main__":
    # Quick test
    db = ensure_server()
    print("Dashboard client ready. Server running.")
    print(f"Open http://localhost:9121/ in browser")
    print("Press 'D' in the dashboard for a demo animation!")
