import json
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import TYPE_CHECKING, cast
from urllib.parse import parse_qs, urlparse

from door_service.service import DoorControlService
from door_service.utils import mask_secret

if TYPE_CHECKING:
    from door_service.http_app import DoorControlServer


class DoorControlHandler(BaseHTTPRequestHandler):
    @property
    def app(self) -> DoorControlService:
        server = cast("DoorControlServer", self.server)
        return server.app

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        routes = self.app.config.routes

        if parsed.path == routes.status_path:
            self._send_json(self.app.snapshot())
            return

        if parsed.path == routes.callback_path:
            query = parse_qs(parsed.query)
            latest = self.app.handle_callback(query, self.path)
            self._send_html(self._render_callback_page(latest))
            return

        if parsed.path == routes.refresh_path:
            self._send_html(self._render_refresh_page())
            return

        if parsed.path == routes.refresh_start_path:
            self._require_access_or_raise(parsed)
            self.send_response(HTTPStatus.FOUND)
            self.send_header("Location", self.app.auth_url)
            self.end_headers()
            return

        if parsed.path == routes.check_api_path:
            self._require_access_or_raise(parsed)
            snapshot = self.app.run_health_check_once()
            self._send_json(snapshot)
            return

        if parsed.path == routes.open_api_path:
            self._require_access_or_raise(parsed)
            door_code = parse_qs(parsed.query).get("doorCode", [None])[0]
            try:
                result = self.app.open_door(door_code)
                self._send_json(result)
            except Exception as exc:
                self._send_json({"ok": False, "error": str(exc)}, status=HTTPStatus.BAD_GATEWAY)
            return

        if parsed.path == routes.dashboard_path:
            self._send_html(self._render_index_page())
            return

        self.send_error(HTTPStatus.NOT_FOUND, "Not Found")

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == self.app.config.routes.open_api_path:
            self._require_access_or_raise(parsed)
            try:
                result = self.app.open_door(None)
                self._send_json(result)
            except Exception as exc:
                self._send_json({"ok": False, "error": str(exc)}, status=HTTPStatus.BAD_GATEWAY)
            return
        self.send_error(HTTPStatus.NOT_FOUND, "Not Found")

    def log_message(self, format: str, *args) -> None:
        stamp = time.strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{stamp}] {self.address_string()} {format % args}")

    def handle_one_request(self) -> None:
        try:
            super().handle_one_request()
        except PermissionError as exc:
            self._send_html(f"<h1>403 Forbidden</h1><p>{exc}</p>", status=HTTPStatus.FORBIDDEN)

    def _send_json(self, payload: dict, status: int = HTTPStatus.OK) -> None:
        body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, html: str, status: int = HTTPStatus.OK) -> None:
        body = html.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _extract_access_key(self, parsed) -> str | None:
        query_key = parse_qs(parsed.query).get("key", [None])[0]
        header_key = self.headers.get("X-Access-Key")
        return header_key or query_key

    def _require_access_or_raise(self, parsed) -> None:
        if not self.app.config.access_key:
            return
        if self._extract_access_key(parsed) == self.app.config.access_key:
            return
        raise PermissionError("access key required")

    def _render_index_page(self) -> str:
        snapshot = self.app.snapshot()
        latest = snapshot.get("latest", {})
        health = latest.get("health", {}) if isinstance(latest, dict) else {}
        doors = health.get("doors", []) if isinstance(health, dict) else []
        routes = self.app.config.routes
        key_query = f"?key={self.app.config.access_key}" if self.app.config.access_key else ""
        first_door = doors[0] if doors else {}
        return f"""<!doctype html>
<html>
<head>
  <meta charset=\"utf-8\">
  <title>Door Control Service</title>
  <style>
    body {{ font-family: sans-serif; margin: 2rem; line-height: 1.5; max-width: 60rem; }}
    code, textarea {{ font-family: ui-monospace, monospace; }}
    textarea {{ width: 100%; min-height: 7rem; }}
    button {{ padding: 0.7rem 1rem; margin-right: 0.75rem; margin-top: 0.75rem; }}
    .card {{ border: 1px solid #ddd; padding: 1rem; border-radius: 0.75rem; margin-bottom: 1rem; }}
  </style>
</head>
<body>
  <h1>Door Control Service</h1>
  <div class=\"card\">
    <p><strong>Health:</strong> <code>{health.get('ok')}</code></p>
    <p><strong>Token:</strong> <code>{mask_secret(latest.get('token'))}</code></p>
    <p><strong>Expires:</strong> <code>{health.get('expires_at')}</code></p>
    <p><strong>Last error:</strong> <code>{health.get('error')}</code></p>
    <p><strong>Door:</strong> <code>{first_door.get('doorInfo')}</code></p>
    <p><strong>Battery:</strong> <code>{first_door.get('battery')}</code></p>
  </div>
  <div class=\"card\">
    <p><strong>Status URL:</strong> <code>{self.app.config.public_base}{routes.status_path}</code></p>
    <p><strong>Open API:</strong> <code>{self.app.config.public_base}{routes.open_api_path}{key_query}</code></p>
    <p><strong>Refresh Page:</strong> <code>{self.app.config.public_base}{routes.refresh_path}</code></p>
    <form action=\"{routes.open_api_path}{key_query}\" method=\"post\">
      <button type=\"submit\">远程开门</button>
    </form>
    <form action=\"{routes.refresh_start_path}{key_query}\" method=\"get\">
      <button type=\"submit\">刷新 Token（打开微信授权）</button>
    </form>
  </div>
  <div class=\"card\">
    <p>也可以把下面授权链接发到微信里手动打开：</p>
    <textarea readonly>{self.app.auth_url}</textarea>
  </div>
</body>
</html>"""

    def _render_refresh_page(self) -> str:
        key_query = f"?key={self.app.config.access_key}" if self.app.config.access_key else ""
        return f"""<!doctype html>
<html><head><meta charset=\"utf-8\"><title>Refresh Token</title></head>
<body>
  <h1>Refresh Token</h1>
  <p>在微信里点击下面按钮，完成授权后会自动回到本服务并更新 token。</p>
  <p><a href=\"{self.app.config.routes.refresh_start_path}{key_query}\">打开微信授权链接</a></p>
  <p><a href=\"{self.app.config.routes.dashboard_path}\">返回首页</a></p>
</body></html>"""

    def _render_callback_page(self, latest: dict) -> str:
        token = mask_secret(latest.get("token")) or ""
        code = latest.get("code") or ""
        error = latest.get("error") or ""
        exchange_ok = latest.get("exchange_ok")
        return f"""<!doctype html>
<html>
<head><meta charset=\"utf-8\"><title>Callback Received</title></head>
<body>
  <h1>Callback Received</h1>
  <p><strong>code:</strong> <code>{code}</code></p>
  <p><strong>token:</strong> <code>{token}</code></p>
  <p><strong>exchange_ok:</strong> <code>{exchange_ok}</code></p>
  <p><strong>error:</strong> <code>{error}</code></p>
  <p><a href=\"{self.app.config.routes.dashboard_path}\">回到首页</a></p>
</body>
</html>"""


class DoorControlServer(ThreadingHTTPServer):
    def __init__(self, server_address: tuple[str, int], app: DoorControlService):
        super().__init__(server_address, DoorControlHandler)
        self.app = app
