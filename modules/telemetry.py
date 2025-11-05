# modules/telemetry.py
import json
import logging
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Dict, Optional

LOG = logging.getLogger("telemetry")


class _MetricsStore:
    def __init__(self):
        self._gauges: Dict[str, float] = {}
        self._counters: Dict[str, float] = {}
        self._heartbeats: Dict[str, float] = {}
        self._lock = threading.RLock()

    def set_gauge(self, name: str, value: float):
        with self._lock:
            self._gauges[name] = float(value)

    def inc_counter(self, name: str, inc: float = 1.0):
        with self._lock:
            self._counters[name] = self._counters.get(name, 0.0) + float(inc)

    def heartbeat(self, name: str):
        with self._lock:
            self._heartbeats[name] = time.time()

    def snapshot(self):
        with self._lock:
            return dict(self._gauges), dict(self._counters), dict(self._heartbeats)


class Telemetry:
    """
    Minimal Prometheus-style exporter with no external deps.
    - Exposes /metrics on <port>
    - Provides gauges, counters, and named heartbeats
    """

    def __init__(self, enabled: bool = False, port: int = 9100):
        self.enabled = enabled
        self.port = port
        self.metrics = _MetricsStore()
        self._server: Optional[HTTPServer] = None
        self._thread: Optional[threading.Thread] = None

    def start(self):
        if not self.enabled:
            LOG.info("[telemetry] disabled")
            return
        if self._server:
            LOG.info("[telemetry] already running on port %d", self.port)
            return

        store = self.metrics

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                # Health check endpoint
                if self.path == "/health":
                    _, _, hbs = store.snapshot()
                    now = time.time()

                    # Basic health: check if we have recent heartbeats
                    ws_age = now - hbs.get("ws", 0) if hbs.get("ws") else 999999
                    quote_age = now - hbs.get("quote", 0) if hbs.get("quote") else 999999

                    # Consider healthy if we have heartbeats within last 60s
                    is_healthy = ws_age < 60.0 or quote_age < 60.0

                    status = 200 if is_healthy else 503
                    body = {
                        "status": "healthy" if is_healthy else "unhealthy",
                        "ws_age_seconds": round(ws_age, 2),
                        "quote_age_seconds": round(quote_age, 2),
                        "timestamp": round(now, 2)
                    }
                    data = json.dumps(body).encode("utf-8")
                    self.send_response(status)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(data)))
                    self.end_headers()
                    self.wfile.write(data)
                    return

                # Metrics endpoint
                if self.path != "/metrics":
                    self.send_response(404)
                    self.end_headers()
                    return
                gauges, counters, heartbeats = store.snapshot()
                body = []
                now = time.time()

                for k, v in gauges.items():
                    body.append(f"# TYPE {k} gauge")
                    body.append(f"{k} {v}")

                for k, v in counters.items():
                    body.append(f"# TYPE {k} counter")
                    body.append(f"{k} {v}")

                for k, ts in heartbeats.items():
                    age = max(0.0, now - ts)
                    body.append(f"# TYPE {k}_last heartbeat")
                    body.append(f"{k}_last {ts}")
                    body.append(f"# TYPE {k}_age_seconds gauge")
                    body.append(f"{k}_age_seconds {age}")

                data = ("\n".join(body) + "\n").encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/plain; version=0.0.4")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, format, *args):
                # Silence default HTTP server noise
                return

        self._server = HTTPServer(("0.0.0.0", self.port), Handler)
        self._thread = threading.Thread(
            target=self._server.serve_forever, name="TelemetryHTTP", daemon=True
        )
        self._thread.start()
        LOG.info("[telemetry] started on port %d", self.port)

    # Public metric helpers
    def set_gauge(self, name: str, value: float):
        self.metrics.set_gauge(name, value)

    def inc_counter(self, name: str, inc: float = 1.0):
        self.metrics.inc_counter(name, inc)

    def heartbeat(self, name: str):
        self.metrics.heartbeat(name)

    # Convenience aliases used by other modules
    touch = heartbeat
