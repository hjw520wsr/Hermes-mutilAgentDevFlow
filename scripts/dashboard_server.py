#!/usr/bin/env python3
"""
Multi-Agent Dashboard — aiohttp Server (single port: HTTP + WebSocket)

Usage:
    python dashboard_server.py              # Start on :9121
    python dashboard_server.py --port 9200  # Custom port

Endpoints:
    GET  /          → Dashboard HTML
    GET  /state     → Current state JSON
    POST /event     → Submit event
    WS   /ws        → WebSocket for real-time updates
"""

import asyncio
import json
import os
import sys
import time
import argparse
from pathlib import Path

try:
    from aiohttp import web
except ImportError:
    print("Installing aiohttp...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "aiohttp", "-q"])
    from aiohttp import web

# ── State ──────────────────────────────────────────────────────
STATE = {
    "project": {"name": "", "path": "", "requirement": ""},
    "workflow": {
        "current_phase": 0,
        "total_phases": 4,
        "phase_names": ["Discovery", "Planning", "Building", "Verification"],
        "status": "idle",
        "started_at": None,
        "elapsed": 0,
        "iteration": 0,
        "max_iterations": 3,
    },
    "agents": {},
    "events": [],
    "metrics": {
        "total_agents_spawned": 0,
        "total_tool_calls": 0,
        "total_tokens": 0,
        "files_created": 0,
        "files_modified": 0,
        "tests_passed": 0,
        "tests_failed": 0,
        "issues_found": 0,
        "issues_fixed": 0,
    },
}

WS_CLIENTS = set()
STATUS_FILE = Path("/tmp/hermes-multi-agent-status.json")
DASHBOARD_HTML = Path(__file__).parent / "dashboard.html"

# ── Agent state schema ─────────────────────────────────────────
def make_agent(agent_id, role, phase, engine="delegate_task"):
    return {
        "id": agent_id,
        "role": role,
        "phase": phase,
        "engine": engine,
        "status": "pending",
        "current_tool": None,
        "current_file": None,
        "tool_calls": 0,
        "iteration": 0,
        "max_iterations": 50,
        "started_at": None,
        "completed_at": None,
        "elapsed": 0,
        "output_summary": "",
        "progress_pct": 0,
        "artifacts": [],
        "log": [],
    }


# ── Event handling ─────────────────────────────────────────────
def handle_event(event):
    etype = event.get("type", "")
    ts = event.get("timestamp", time.time())
    event["timestamp"] = ts

    STATE["events"].append(event)
    if len(STATE["events"]) > 200:
        STATE["events"] = STATE["events"][-200:]

    if etype == "workflow.start":
        STATE["project"] = event.get("project", STATE["project"])
        STATE["workflow"]["status"] = "running"
        STATE["workflow"]["started_at"] = ts
        STATE["workflow"]["current_phase"] = 0
        STATE["workflow"]["iteration"] = 0
        STATE["agents"].clear()
        STATE["events"].clear()
        STATE["metrics"] = {
            "total_agents_spawned": 0,
            "total_tool_calls": 0,
            "tests_passed": 0,
            "issues_found": 0,
            "files_created": 0,
            "files_modified": 0,
        }

    elif etype == "workflow.complete":
        STATE["workflow"]["status"] = "completed"

    elif etype == "workflow.fail":
        STATE["workflow"]["status"] = "failed"

    elif etype == "phase.start":
        STATE["workflow"]["current_phase"] = event.get("phase", 0)

    elif etype == "phase.complete":
        pass

    elif etype == "agent.spawn":
        aid = event["agent_id"]
        agent = make_agent(
            aid,
            role=event.get("role", "unknown"),
            phase=event.get("phase", STATE["workflow"]["current_phase"]),
            engine=event.get("engine", "delegate_task"),
        )
        agent["status"] = "running"
        agent["started_at"] = ts
        STATE["agents"][aid] = agent
        STATE["metrics"]["total_agents_spawned"] += 1

    elif etype == "agent.tool_call":
        aid = event.get("agent_id", "")
        if aid in STATE["agents"]:
            a = STATE["agents"][aid]
            a["current_tool"] = event.get("tool", "")
            a["current_file"] = event.get("file", "")
            a["tool_calls"] += 1
            a["iteration"] = event.get("iteration", a["iteration"])
            a["progress_pct"] = min(95, int(a["iteration"] / max(a["max_iterations"], 1) * 100))
            log_line = f"[{a['tool_calls']}] {a['current_tool']}"
            if a["current_file"]:
                log_line += f" → {a['current_file']}"
            a["log"].append(log_line)
            if len(a["log"]) > 30:
                a["log"] = a["log"][-30:]
            STATE["metrics"]["total_tool_calls"] += 1

    elif etype == "agent.thinking":
        aid = event.get("agent_id", "")
        if aid in STATE["agents"]:
            a = STATE["agents"][aid]
            a["log"].append(f"💭 {event.get('text', '')[:80]}")
            if len(a["log"]) > 30:
                a["log"] = a["log"][-30:]

    elif etype == "agent.complete":
        aid = event.get("agent_id", "")
        if aid in STATE["agents"]:
            a = STATE["agents"][aid]
            a["status"] = "completed"
            a["completed_at"] = ts
            a["elapsed"] = ts - (a["started_at"] or ts)
            a["current_tool"] = None
            a["progress_pct"] = 100
            a["output_summary"] = event.get("summary", "")
            a["artifacts"] = event.get("artifacts", [])

    elif etype == "agent.fail":
        aid = event.get("agent_id", "")
        if aid in STATE["agents"]:
            a = STATE["agents"][aid]
            a["status"] = "failed"
            a["completed_at"] = ts
            a["elapsed"] = ts - (a["started_at"] or ts)
            a["output_summary"] = event.get("error", "Failed")

    elif etype == "metrics.update":
        for k, v in event.get("metrics", {}).items():
            if k in STATE["metrics"]:
                STATE["metrics"][k] = v

    if STATE["workflow"]["started_at"]:
        STATE["workflow"]["elapsed"] = ts - STATE["workflow"]["started_at"]

    try:
        STATUS_FILE.write_text(json.dumps(STATE, default=str))
    except Exception:
        pass

    return STATE


# ── Broadcast to all WebSocket clients ─────────────────────────
async def broadcast():
    global WS_CLIENTS
    if not WS_CLIENTS:
        return
    msg = json.dumps({"type": "state.full", "state": STATE}, default=str)
    dead = set()
    for ws in WS_CLIENTS:
        try:
            await ws.send_str(msg)
        except Exception:
            dead.add(ws)
    if dead:
        WS_CLIENTS -= dead


# ── HTTP Handlers ──────────────────────────────────────────────
async def handle_index(request):
    if DASHBOARD_HTML.exists():
        return web.Response(
            body=DASHBOARD_HTML.read_bytes(),
            content_type="text/html",
            charset="utf-8",
        )
    return web.Response(text="Dashboard HTML not found", status=404)


async def handle_state(request):
    return web.json_response(STATE)


async def handle_event_post(request):
    try:
        event = await request.json()
        handle_event(event)
        await broadcast()
        return web.json_response({"ok": True})
    except Exception as e:
        return web.json_response({"error": str(e)}, status=400)


# ── WebSocket Handler ──────────────────────────────────────────
async def handle_ws(request):
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    WS_CLIENTS.add(ws)

    # Send current state on connect
    await ws.send_str(json.dumps({"type": "state.full", "state": STATE}, default=str))

    try:
        async for msg in ws:
            if msg.type == web.WSMsgType.TEXT:
                try:
                    event = json.loads(msg.data)
                    handle_event(event)
                    await broadcast()
                except json.JSONDecodeError:
                    pass
            elif msg.type == web.WSMsgType.ERROR:
                break
    finally:
        WS_CLIENTS.discard(ws)

    return ws


# ── App Setup ──────────────────────────────────────────────────
def create_app():
    app = web.Application()
    # Enable CORS for all routes
    app.router.add_get("/", handle_index)
    app.router.add_get("/dashboard", handle_index)
    app.router.add_get("/state", handle_state)
    app.router.add_post("/event", handle_event_post)
    app.router.add_get("/ws", handle_ws)
    return app


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Multi-Agent Dashboard Server")
    parser.add_argument("--port", type=int, default=9121, help="Server port (HTTP + WS)")
    args = parser.parse_args()

    print(f"🎛️  Multi-Agent Dashboard Server")
    print(f"   Dashboard → http://localhost:{args.port}/")
    print(f"   WebSocket → ws://localhost:{args.port}/ws")
    print(f"   Event     → POST http://localhost:{args.port}/event")
    print(f"   State     → GET  http://localhost:{args.port}/state")
    print()
    sys.stdout.flush()

    web.run_app(create_app(), host="0.0.0.0", port=args.port, print=None)
