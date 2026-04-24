#!/usr/bin/env python3
"""
Multi-Agent Dashboard Client — Zero External Dependencies

Sends events to the Dashboard server via HTTP POST (urllib).
Auto-starts the server if not running.

Usage:
    from dashboard_client import Dashboard

    db = Dashboard()                   # auto-connects to localhost:9121
    db.ensure_server()                 # starts server if needed + opens browser
    db.workflow_start("My Project")    # begin workflow
    db.agent_spawn("explorer-1", "explorer", "discovery")
    db.agent_tool_call("explorer-1", "read_file", "src/main.py")
    db.agent_complete("explorer-1")
    db.phase_complete("discovery")
    db.workflow_complete()
"""

import json
import os
import platform
import socket
import subprocess
import sys
import time
import webbrowser
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import URLError


class Dashboard:
    """Client for the Multi-Agent Dashboard server (zero dependencies)."""

    def __init__(self, url="http://localhost:9121"):
        self.url = url.rstrip("/")

    # ── Server Management ─────────────────────────────────────

    def is_running(self) -> bool:
        """Check if dashboard server is reachable."""
        try:
            port = int(self.url.split(":")[-1].split("/")[0])
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            sock.connect(("localhost", port))
            sock.close()
            return True
        except (socket.error, OSError):
            return False

    def ensure_server(self, open_browser=True):
        """Start dashboard server if not running, optionally open browser."""
        if self.is_running():
            if open_browser:
                self._open_browser()
            return

        # Find server script relative to this file
        server_script = Path(__file__).parent / "dashboard_server.py"
        if not server_script.exists():
            # Fallback: search common locations
            candidates = [
                Path.home() / ".hermes" / "skills" / "multi-agent-dev" / "scripts" / "dashboard_server.py",
                Path.cwd() / "scripts" / "dashboard_server.py",
            ]
            for c in candidates:
                if c.exists():
                    server_script = c
                    break

        if not server_script.exists():
            print(f"[Dashboard] ⚠️  Cannot find dashboard_server.py")
            return

        port = int(self.url.split(":")[-1].split("/")[0])

        # Start server as background process
        subprocess.Popen(
            [sys.executable, str(server_script), "--port", str(port)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )

        # Wait for server to be ready
        for _ in range(30):
            time.sleep(0.2)
            if self.is_running():
                break

        if open_browser:
            time.sleep(0.3)
            self._open_browser()

    def _open_browser(self):
        """Open dashboard in default browser (cross-platform)."""
        url = f"{self.url}/"
        try:
            webbrowser.open(url)
        except Exception:
            # Fallback for headless / special environments
            system = platform.system()
            try:
                if system == "Darwin":
                    subprocess.Popen(["open", url])
                elif system == "Linux":
                    # Check for WSL
                    if "microsoft" in platform.uname().release.lower():
                        subprocess.Popen(["wslview", url])
                    else:
                        subprocess.Popen(["xdg-open", url])
                elif system == "Windows":
                    os.startfile(url)
            except Exception:
                print(f"[Dashboard] Open {url} in browser")

    # ── Event Sending ─────────────────────────────────────────

    def send_event(self, event_type: str, data: dict = None):
        """Send an event to the dashboard server."""
        event = {
            "type": event_type,
            "data": data or {},
            "timestamp": time.time(),
        }
        try:
            body = json.dumps(event).encode("utf-8")
            req = Request(
                f"{self.url}/event",
                data=body,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            urlopen(req, timeout=3)
        except (URLError, OSError):
            pass  # Server might not be running — fail silently

    # ── Convenience Methods ───────────────────────────────────

    def workflow_start(self, name: str, project_path: str = ""):
        self.send_event("workflow.start", {
            "name": name,
            "project_path": project_path,
        })

    def workflow_complete(self):
        self.send_event("workflow.complete")

    def workflow_error(self, error: str):
        self.send_event("workflow.error", {"error": error})

    def phase_start(self, phase: str):
        self.send_event("phase.start", {"phase": phase})

    def phase_complete(self, phase: str):
        self.send_event("phase.complete", {"phase": phase})

    def phase_progress(self, phase: str, progress: int):
        self.send_event("phase.progress", {"phase": phase, "progress": progress})

    def agent_spawn(self, agent_id: str, role: str, phase: str, max_iterations: int = 50, engine: str = ""):
        self.send_event("agent.spawn", {
            "agent_id": agent_id,
            "role": role,
            "phase": phase,
            "max_iterations": max_iterations,
            "engine": engine,  # v2: track which engine (delegate_task, claude-cli, claude-acp, orchestrator-self)
        })

    def agent_tool_call(self, agent_id: str, tool: str, args: str = "", iteration: int = 0):
        self.send_event("agent.tool_call", {
            "agent_id": agent_id,
            "tool": tool,
            "args": args,
            "iteration": iteration,
        })

    def agent_thinking(self, agent_id: str):
        self.send_event("agent.thinking", {"agent_id": agent_id})

    def agent_complete(self, agent_id: str, result: str = "completed"):
        self.send_event("agent.complete", {
            "agent_id": agent_id,
            "result": result,
        })

    def agent_error(self, agent_id: str, error: str):
        self.send_event("agent.error", {
            "agent_id": agent_id,
            "error": error,
        })

    # ── v2: Pre-flight, Gate, and Fallback events ────────────

    def preflight_start(self):
        """Emit when pre-flight checks begin."""
        self.send_event("preflight.start", {})

    def preflight_check(self, check_name: str, passed: bool, detail: str = ""):
        """Emit per-check result during pre-flight."""
        self.send_event("preflight.check", {
            "check": check_name,
            "passed": passed,
            "detail": detail,
        })

    def preflight_complete(self, status: str, fallback_plan: dict = None):
        """Emit when pre-flight finishes. status: passed|degraded|failed."""
        self.send_event("preflight.complete", {
            "status": status,
            "fallback_plan": fallback_plan or {},
        })

    def gate_check(self, gate_id: str, status: str, checks: dict = None, detail: str = ""):
        """Emit gate validation result. gate_id: gate0..gate3, status: passed|failed."""
        self.send_event("gate.check", {
            "gate_id": gate_id,
            "status": status,
            "checks": checks or {},
            "detail": detail,
        })

    def fallback_triggered(self, role: str, primary_engine: str, fallback_engine: str, reason: str = ""):
        """Emit when a role falls back to a degraded engine."""
        self.send_event("fallback.triggered", {
            "role": role,
            "primary_engine": primary_engine,
            "fallback_engine": fallback_engine,
            "reason": reason,
        })

    def integration_build(self, group_id: int, passed: bool, output: str = ""):
        """Emit after post-parallel-merge build check."""
        self.send_event("build.integration", {
            "group_id": group_id,
            "passed": passed,
            "output": output[:500] if output else "",  # truncate long build output
        })

    def metrics_update(self, **kwargs):
        self.send_event("metrics.update", kwargs)


# ── CLI Usage ─────────────────────────────────────────────────

if __name__ == "__main__":
    db = Dashboard()
    db.ensure_server()
    print(f"Dashboard server running at {db.url}")
    print(f"Open {db.url}/ in browser")
