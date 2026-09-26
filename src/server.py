import json
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

from src.catalog import (
    DataIntegrityError,
    load_context,
    load_registry,
    oversight_pledge_view,
    pledge_statuses,
    public_pledge_view,
)

REGISTRY = load_registry()


class Handler(BaseHTTPRequestHandler):
    def _send(self, payload: dict | list, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        parts = urlsplit(self.path)
        query = parse_qs(parts.query)
        try:
            as_of = (
                date.fromisoformat(query["as_of"][0])
                if query.get("as_of")
                else date.today()
            )
            if parts.path == "/health":
                self._send({"status": "ok"})
            elif parts.path == "/context":
                self._send(load_context())
            elif parts.path == "/pledges":
                self._send(pledge_statuses(REGISTRY, as_of))
            elif parts.path.startswith("/pledges/"):
                pledge_id = parts.path.rsplit("/", 1)[1]
                self._send(public_pledge_view(REGISTRY, pledge_id, as_of))
            elif parts.path.startswith("/oversight/pledges/"):
                pledge_id = parts.path.rsplit("/", 1)[1]
                self._send(oversight_pledge_view(REGISTRY, pledge_id, as_of))
            else:
                self.send_error(404)
        except DataIntegrityError as exc:
            self._send({"error": "data_integrity", "detail": str(exc)}, status=500)
        except (KeyError, ValueError) as exc:
            self._send({"error": "bad_request", "detail": str(exc)}, status=400)


if __name__ == "__main__":
    ThreadingHTTPServer(("127.0.0.1", 8000), Handler).serve_forever()
