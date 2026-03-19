"""Minimal HTTP server for BDD integration testing.

Provides a health endpoint and 404 for everything else.
Prints PORT=<N> to stdout so the cucumber-js World class
can discover which port was assigned.
"""

from __future__ import annotations

import argparse
import json
import signal
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer


class TestHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path == "/health":
            self._respond(200, {"status": "ok"})
        else:
            self._respond(404, {"error": "not found"})

    def _respond(self, status: int, body: dict[str, str]) -> None:
        payload = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        """Suppress default request logging to keep stdout clean for port discovery."""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=0)
    args = parser.parse_args()

    server = HTTPServer(("127.0.0.1", args.port), TestHandler)
    actual_port = server.server_address[1]

    print(f"PORT={actual_port}", flush=True)

    def handle_sigterm(_signum: int, _frame: object) -> None:
        server.shutdown()

    signal.signal(signal.SIGTERM, handle_sigterm)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        sys.exit(0)


if __name__ == "__main__":
    main()
