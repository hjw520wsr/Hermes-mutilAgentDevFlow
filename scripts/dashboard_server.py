#!/usr/bin/env python3
"""
Multi-Agent Dashboard Server — Zero External Dependencies

Pure Python stdlib: http.server + asyncio + hashlib (RFC 6455 WebSocket)

Usage:
    python dashboard_server.py              # Start on :9121
    python dashboard_server.py --port 9200  # Custom port

Endpoints:
    GET  /          → Dashboard HTML
    GET  /state     → Current state JSON
    POST /event     → Submit event
    WS   /ws        → WebSocket (real-time updates)
"""

import argparse
import hashlib
import base64
import json
import os
import queue as thread_queue
import socket
import struct
import sys
import threading
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

# ─── Global State ────────────────────────────────────────────────

STATE = {
    "workflow": {"name": "", "status": "idle", "current_phase": ""},
    "phases": {
        "discovery":    {"status": "pending", "progress": 0},
        "planning":     {"status": "pending", "progress": 0},
        "building":     {"status": "pending", "progress": 0},
        "verification": {"status": "pending", "progress": 0},
    },
    "agents": {},
    "metrics": {
        "agents_spawned": 0, "tool_calls": 0,
        "total_tokens": 0, "start_time": 0, "elapsed": 0,
        "tests_passed": 0, "issues_found": 0,
        "files_created": 0, "files_modified": 0,
    },
    "events": [],
}

WS_CLIENTS = set()        # set of asyncio.Queue
WS_CLIENTS_LOCK = threading.Lock()
EVENT_LOG_MAX = 200

PHASE_ORDER = ["discovery", "planning", "building", "verification"]
PHASE_TO_NUM = {name: i + 1 for i, name in enumerate(PHASE_ORDER)}

# ─── HTML File ───────────────────────────────────────────────────

DASHBOARD_HTML_PATH = Path(__file__).parent / "dashboard.html"

# ─── Event Processing ────────────────────────────────────────────

def process_event(event: dict):
    """Process an incoming event and update global STATE.
    
    Accepts two formats:
    - Structured: {"type": "agent.spawn", "data": {"agent_id": "...", ...}}
    - Flat (demo): {"type": "agent.spawn", "agent_id": "...", "tool": "...", ...}
    """
    etype = event.get("type", "")
    ts = event.get("timestamp", event.get("time", time.time()))
    
    # Normalize: if no "data" key, treat all non-type/timestamp fields as data
    if "data" in event:
        data = event["data"]
    else:
        data = {k: v for k, v in event.items() if k not in ("type", "timestamp", "time")}

    # Workflow events
    if etype == "workflow.start":
        # Accept project name from either data.name or data.project.name (demo format)
        project = data.get("project", {})
        STATE["workflow"]["name"] = data.get("name", "") or project.get("name", "")
        STATE["workflow"]["status"] = "running"
        STATE["workflow"]["current_phase"] = "discovery"
        STATE["metrics"]["start_time"] = ts
        STATE["metrics"]["agents_spawned"] = 0
        STATE["metrics"]["tool_calls"] = 0
        STATE["metrics"]["tests_passed"] = 0
        STATE["metrics"]["issues_found"] = 0
        STATE["metrics"]["files_created"] = 0
        STATE["metrics"]["files_modified"] = 0
        STATE["agents"].clear()
        for p in STATE["phases"].values():
            p["status"] = "pending"
            p["progress"] = 0

    elif etype == "workflow.complete":
        STATE["workflow"]["status"] = "completed"

    elif etype == "workflow.error":
        STATE["workflow"]["status"] = "error"

    # Phase events
    elif etype == "phase.start":
        phase = data.get("phase", "")
        # Accept both string ("discovery") and number (1) formats
        if isinstance(phase, int):
            phase = PHASE_ORDER[phase - 1] if 1 <= phase <= 4 else ""
        if phase in STATE["phases"]:
            STATE["phases"][phase]["status"] = "running"
            STATE["workflow"]["current_phase"] = phase

    elif etype == "phase.complete":
        phase = data.get("phase", "")
        if isinstance(phase, int):
            phase = PHASE_ORDER[phase - 1] if 1 <= phase <= 4 else ""
        if phase in STATE["phases"]:
            STATE["phases"][phase]["status"] = "completed"
            STATE["phases"][phase]["progress"] = 100

    elif etype == "phase.progress":
        phase = data.get("phase", "")
        if isinstance(phase, int):
            phase = PHASE_ORDER[phase - 1] if 1 <= phase <= 4 else ""
        if phase in STATE["phases"]:
            STATE["phases"][phase]["progress"] = data.get("progress", 0)

    # Agent events
    elif etype == "agent.spawn":
        aid = data.get("agent_id", "")
        STATE["agents"][aid] = {
            "id": aid,
            "role": data.get("role", "unknown"),
            "status": "running",
            "phase": data.get("phase", ""),
            "current_tool": "",
            "current_file": "",
            "iteration": 0,
            "max_iterations": data.get("max_iterations", 50),
            "tool_calls": 0,
            "started_at": ts,
            "elapsed": 0,
            "output_summary": "",
            "activities": [],
        }
        STATE["metrics"]["agents_spawned"] += 1

    elif etype == "agent.tool_call":
        aid = data.get("agent_id", "")
        if aid in STATE["agents"]:
            STATE["agents"][aid]["current_tool"] = data.get("tool", "")
            STATE["agents"][aid]["current_file"] = data.get("file", "")
            STATE["agents"][aid]["iteration"] = data.get("iteration", 0)
            STATE["agents"][aid]["tool_calls"] += 1
            STATE["agents"][aid]["elapsed"] = ts - STATE["agents"][aid]["started_at"]
            STATE["agents"][aid]["activities"].append({
                "tool": data.get("tool", ""),
                "args": data.get("args", ""),
                "time": ts,
            })
            # Keep only last 20 activities
            STATE["agents"][aid]["activities"] = STATE["agents"][aid]["activities"][-20:]
        STATE["metrics"]["tool_calls"] += 1

    elif etype == "agent.thinking":
        aid = data.get("agent_id", "")
        if aid in STATE["agents"]:
            STATE["agents"][aid]["current_tool"] = "💭 thinking..."

    elif etype == "agent.complete":
        aid = data.get("agent_id", "")
        if aid in STATE["agents"]:
            STATE["agents"][aid]["status"] = data.get("result", "completed")
            STATE["agents"][aid]["current_tool"] = ""
            STATE["agents"][aid]["current_file"] = ""
            STATE["agents"][aid]["elapsed"] = ts - STATE["agents"][aid]["started_at"]
            STATE["agents"][aid]["output_summary"] = data.get("summary", "")

    elif etype == "agent.error":
        aid = data.get("agent_id", "")
        if aid in STATE["agents"]:
            STATE["agents"][aid]["status"] = "error"
            STATE["agents"][aid]["current_tool"] = ""
            STATE["agents"][aid]["elapsed"] = ts - STATE["agents"][aid]["started_at"]
            STATE["agents"][aid]["output_summary"] = data.get("error", "")[:200]

    # Metrics
    elif etype == "metrics.update":
        STATE["metrics"].update(data)

    # Update elapsed time
    if STATE["metrics"]["start_time"]:
        STATE["metrics"]["elapsed"] = time.time() - STATE["metrics"]["start_time"]

    # Append to event log
    STATE["events"].append({"type": etype, "data": data, "time": ts})
    if len(STATE["events"]) > EVENT_LOG_MAX:
        STATE["events"] = STATE["events"][-EVENT_LOG_MAX:]

    # Broadcast to WebSocket clients
    broadcast_state()


def broadcast_state():
    """Send current state to all connected WebSocket clients.
    
    Enriches the state with computed fields that the frontend needs.
    """
    # Compute progress_pct for each agent
    enriched_agents = {}
    for aid, agent in STATE["agents"].items():
        a = dict(agent)
        if a["max_iterations"] > 0:
            a["progress_pct"] = min(100, int((a["iteration"] / a["max_iterations"]) * 100))
        else:
            a["progress_pct"] = 0
        # Convert phase string to number for canvas layout
        if isinstance(a["phase"], str):
            a["phase_num"] = PHASE_TO_NUM.get(a["phase"], 1)
        else:
            a["phase_num"] = a["phase"] if isinstance(a["phase"], int) else 1
        enriched_agents[aid] = a
    
    # Build enriched state
    enriched = {
        "workflow": {
            **STATE["workflow"],
            "current_phase_num": PHASE_TO_NUM.get(STATE["workflow"]["current_phase"], 0),
        },
        "phases": STATE["phases"],
        "agents": enriched_agents,
        "metrics": STATE["metrics"],
        "events": STATE["events"],
    }
    
    msg = json.dumps({"type": "state", "state": enriched})
    with WS_CLIENTS_LOCK:
        for q in WS_CLIENTS:
            try:
                q.put_nowait(msg)
            except Exception:
                pass

# ─── WebSocket (RFC 6455 minimal) ────────────────────────────────

WS_MAGIC = b"258EAFA5-E914-47DA-95CA-C5AB0DC85B11"

def ws_accept_key(key: str) -> str:
    digest = hashlib.sha1(key.encode() + WS_MAGIC).digest()
    return base64.b64encode(digest).decode()

def ws_encode_frame(payload: str) -> bytes:
    data = payload.encode("utf-8")
    length = len(data)
    if length < 126:
        header = struct.pack("!BB", 0x81, length)
    elif length < 65536:
        header = struct.pack("!BBH", 0x81, 126, length)
    else:
        header = struct.pack("!BBQ", 0x81, 127, length)
    return header + data

def ws_decode_frame(data: bytes):
    """Decode a WebSocket frame. Returns (opcode, payload_bytes, total_consumed)."""
    if len(data) < 2:
        return None, None, 0
    b1, b2 = data[0], data[1]
    opcode = b1 & 0x0F
    masked = b2 & 0x80
    length = b2 & 0x7F
    offset = 2
    if length == 126:
        if len(data) < 4:
            return None, None, 0
        length = struct.unpack("!H", data[2:4])[0]
        offset = 4
    elif length == 127:
        if len(data) < 10:
            return None, None, 0
        length = struct.unpack("!Q", data[2:10])[0]
        offset = 10
    if masked:
        if len(data) < offset + 4 + length:
            return None, None, 0
        mask = data[offset:offset+4]
        offset += 4
        payload = bytearray(data[offset:offset+length])
        for i in range(length):
            payload[i] ^= mask[i % 4]
        return opcode, bytes(payload), offset + length
    else:
        if len(data) < offset + length:
            return None, None, 0
        return opcode, data[offset:offset+length], offset + length

# ─── HTTP Handler ─────────────────────────────────────────────────

class DashboardHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"  # Required for WebSocket upgrade handshake
    """Handles HTTP requests and WebSocket upgrades."""

    def log_message(self, format, *args):
        pass  # Suppress default logging

    def do_GET(self):
        # WebSocket upgrade
        if self.path == "/ws":
            upgrade = self.headers.get("Upgrade", "").lower()
            if upgrade == "websocket":
                self._handle_ws_upgrade()
                return
            self._send_json(400, {"error": "Expected WebSocket upgrade"})
            return

        # Dashboard HTML
        if self.path == "/" or self.path == "/index.html":
            if DASHBOARD_HTML_PATH.exists():
                html = DASHBOARD_HTML_PATH.read_bytes()
                self._send_response(200, "text/html; charset=utf-8", html)
            else:
                self._send_json(404, {"error": "dashboard.html not found"})
            return

        # State API
        if self.path == "/state":
            self._send_json(200, STATE)
            return

        # Health check
        if self.path == "/health":
            self._send_json(200, {"status": "ok"})
            return

        self._send_json(404, {"error": "Not found"})

    def do_POST(self):
        if self.path == "/event":
            try:
                length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(length)
                event = json.loads(body)
                process_event(event)
                self._send_json(200, {"ok": True})
            except Exception as e:
                self._send_json(400, {"error": str(e)})
            return

        # Reset state
        if self.path == "/reset":
            STATE["agents"].clear()
            STATE["events"].clear()
            STATE["workflow"]["status"] = "idle"
            STATE["workflow"]["name"] = ""
            STATE["workflow"]["current_phase"] = ""
            STATE["metrics"]["agents_spawned"] = 0
            STATE["metrics"]["tool_calls"] = 0
            STATE["metrics"]["start_time"] = 0
            STATE["metrics"]["elapsed"] = 0
            STATE["metrics"]["tests_passed"] = 0
            STATE["metrics"]["issues_found"] = 0
            STATE["metrics"]["files_created"] = 0
            STATE["metrics"]["files_modified"] = 0
            for p in STATE["phases"].values():
                p["status"] = "pending"
                p["progress"] = 0
            broadcast_state()
            self._send_json(200, {"ok": True})
            return

        self._send_json(404, {"error": "Not found"})

    def do_OPTIONS(self):
        """Handle CORS preflight."""
        self.send_response(204)
        self._cors_headers()
        self.end_headers()

    def _send_response(self, code, content_type, body):
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self._cors_headers()
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, code, obj):
        body = json.dumps(obj).encode("utf-8")
        self._send_response(code, "application/json", body)

    def _cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _handle_ws_upgrade(self):
        """Upgrade HTTP connection to WebSocket and run read/write loop."""
        key = self.headers.get("Sec-WebSocket-Key", "")
        accept = ws_accept_key(key)

        self.send_response(101, "Switching Protocols")
        self.send_header("Upgrade", "websocket")
        self.send_header("Connection", "Upgrade")
        self.send_header("Sec-WebSocket-Accept", accept)
        self.end_headers()

        # Create a thread-safe queue for this client
        send_q = thread_queue.Queue()

        with WS_CLIENTS_LOCK:
            WS_CLIENTS.add(send_q)

        sock = self.request
        sock.settimeout(0.5)

        # Send initial state
        try:
            initial = json.dumps({"type": "state", "state": STATE})
            sock.sendall(ws_encode_frame(initial))
        except Exception:
            pass

        # Read/write loop
        try:
            while True:
                # Send queued messages
                while not send_q.empty():
                    try:
                        msg = send_q.get_nowait()
                        sock.sendall(ws_encode_frame(msg))
                    except Exception:
                        break

                # Read incoming frames (pings, messages)
                try:
                    data = sock.recv(4096)
                    if not data:
                        break
                    opcode, payload, consumed = ws_decode_frame(data)
                    if opcode == 0x8:  # Close
                        break
                    elif opcode == 0x9:  # Ping → Pong
                        pong = struct.pack("!BB", 0x8A, 0) 
                        sock.sendall(pong)
                    elif opcode == 0x1 and payload:  # Text
                        try:
                            msg = json.loads(payload)
                            if msg.get("type") == "ping":
                                sock.sendall(ws_encode_frame('{"type":"pong"}'))
                            elif msg.get("type"):
                                # Process as event (from demo mode or external WS client)
                                process_event(msg)
                        except Exception:
                            pass
                except socket.timeout:
                    pass
                except Exception:
                    break
        finally:
            with WS_CLIENTS_LOCK:
                WS_CLIENTS.discard(send_q)




# ─── Threaded HTTP Server ─────────────────────────────────────────

class ThreadedHTTPServer(HTTPServer):
    """Handle each request in a new thread (needed for WebSocket connections)."""
    allow_reuse_address = True
    daemon_threads = True

    def process_request(self, request, client_address):
        t = threading.Thread(target=self._handle, args=(request, client_address))
        t.daemon = True
        t.start()

    def _handle(self, request, client_address):
        try:
            self.finish_request(request, client_address)
        except Exception:
            self.handle_error(request, client_address)
        finally:
            self.shutdown_request(request)


# ─── Main ─────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Multi-Agent Dashboard Server")
    parser.add_argument("--port", type=int, default=9121, help="Port (default: 9121)")
    args = parser.parse_args()

    server = ThreadedHTTPServer(("127.0.0.1", args.port), DashboardHandler)

    print()
    print(f"  ╔══════════════════════════════════════════════╗")
    print(f"  ║   🤖 Multi-Agent Dashboard Server            ║")
    print(f"  ╠══════════════════════════════════════════════╣")
    print(f"  ║   Dashboard → http://localhost:{args.port}/{'':>{5-len(str(args.port))}}       ║")
    print(f"  ║   WebSocket → ws://localhost:{args.port}/ws{'':>{4-len(str(args.port))}}       ║")
    print(f"  ║   Event API → POST /event                   ║")
    print(f"  ║   State API → GET  /state                   ║")
    print(f"  ║                                              ║")
    print(f"  ║   ✅ Zero dependencies — pure Python stdlib  ║")
    print(f"  ╚══════════════════════════════════════════════╝")
    print()
    sys.stdout.flush()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  Shutting down...")
        server.shutdown()


if __name__ == "__main__":
    main()
