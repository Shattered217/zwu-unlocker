import json
import threading
from datetime import datetime, timezone
from typing import Any

from door_service.config import ServiceConfig
from door_service.crypto import decode_jwt_payload
from door_service.gateway import ServiceError, api_request, build_auth_url, exchange_code_for_token, send_telegram_message
from door_service.storage import load_state, save_state
from door_service.utils import utc_now_iso


class DoorControlService:
    def __init__(self, config: ServiceConfig) -> None:
        self.config = config
        self.lock = threading.Lock()
        self.state = load_state(config.state_file)
        self.stop_event = threading.Event()
        self.health_thread: threading.Thread | None = None

    @property
    def auth_url(self) -> str:
        return build_auth_url(self.config.callback_url)

    def start_background_tasks(self) -> None:
        if self.config.health_interval <= 0:
            return
        if self.health_thread and self.health_thread.is_alive():
            return
        self.health_thread = threading.Thread(target=self._health_loop, daemon=True)
        self.health_thread.start()

    def stop_background_tasks(self) -> None:
        self.stop_event.set()
        if self.health_thread:
            self.health_thread.join(timeout=2)

    def _health_loop(self) -> None:
        while not self.stop_event.is_set():
            try:
                self.run_health_check_once()
            except Exception as exc:
                self._merge_state({
                    "health": {
                        "checked_at": utc_now_iso(),
                        "ok": False,
                        "error": f"health check crashed: {exc}",
                    }
                })
            self.stop_event.wait(self.config.health_interval)

    def snapshot(self) -> dict[str, Any]:
        with self.lock:
            latest = json.loads(json.dumps(self.state)) if self.state else {}
        return {
            "public_base": self.config.public_base,
            "callback_url": self.config.callback_url,
            "auth_url": self.auth_url,
            "health_interval": self.config.health_interval,
            "access_key_enabled": bool(self.config.access_key),
            "routes": {
                "dashboard_path": self.config.routes.dashboard_path,
                "status_path": self.config.routes.status_path,
                "refresh_path": self.config.routes.refresh_path,
                "refresh_start_path": self.config.routes.refresh_start_path,
                "open_api_path": self.config.routes.open_api_path,
                "check_api_path": self.config.routes.check_api_path,
                "callback_path": self.config.routes.callback_path,
            },
            "latest": latest,
        }

    def update(self, state: dict[str, Any]) -> dict[str, Any]:
        state["updated_at"] = utc_now_iso()
        with self.lock:
            self.state = state
            save_state(self.config.state_file, self.state)
            return dict(self.state)

    def _merge_state(self, patch: dict[str, Any]) -> dict[str, Any]:
        with self.lock:
            merged = dict(self.state)
            for key, value in patch.items():
                merged[key] = value
            merged["updated_at"] = utc_now_iso()
            self.state = merged
            save_state(self.config.state_file, self.state)
            return dict(self.state)

    def current_token(self) -> str | None:
        with self.lock:
            token = self.state.get("token")
        return token if isinstance(token, str) and token else None

    def handle_callback(self, query: dict[str, list[str]], raw_path: str) -> dict[str, Any]:
        state: dict[str, Any] = {
            "captured_at": utc_now_iso(),
            "callback_path": raw_path,
            "raw_query": {key: values[:] for key, values in query.items()},
            "code": query.get("code", [None])[0],
            "errCode": query.get("errCode", [None])[0],
            "state": query.get("state", [None])[0],
            "token": query.get("token", [None])[0],
            "exchange_attempted": False,
            "exchange_ok": False,
            "final_url": None,
            "exchange_url": None,
            "exchange_body_preview": None,
            "error": query.get("errMsg", [None])[0] or query.get("message", [None])[0],
        }

        code = state["code"]
        err_code = state["errCode"] or "0"
        if code and self.config.exchange_token:
            state.update(exchange_code_for_token(code, err_code))

        latest = self.update(state)
        self.run_health_check_once()
        return latest

    def validate_token(self, token: str) -> dict[str, Any]:
        payload = decode_jwt_payload(token)
        expiry = payload.get("exp") if isinstance(payload, dict) else None
        token_status: dict[str, Any] = {
            "token": token,
            "checked_at": utc_now_iso(),
            "ok": False,
            "error": None,
            "exp": expiry,
            "expires_at": datetime.fromtimestamp(expiry, timezone.utc).isoformat() if isinstance(expiry, int) else None,
            "user": None,
            "doors": [],
        }
        try:
            user_payload = api_request("user", {}, token, method="GET")
            if user_payload.get("result") != 0:
                raise ServiceError(user_payload.get("message", "token invalid"))
            doors_payload = api_request(
                "doors",
                {"campusId": "", "buildingId": "", "floorId": "", "pageNum": 1, "pageSize": 20},
                token,
                method="GET",
            )
            if doors_payload.get("result") != 0:
                raise ServiceError(doors_payload.get("message", "doors query failed"))
            token_status["ok"] = True
            token_status["user"] = user_payload.get("data", {}).get("userInfo")
            token_status["doors"] = [
                {
                    "name": door.get("name"),
                    "doorInfo": door.get("doorInfo"),
                    "battery": door.get("battery"),
                    "doorCode": door.get("code"),
                    "doorinternetIotLockId": door.get("doorinternetIotLockId"),
                    "doorId": door.get("doorId"),
                    "doorOpen": door.get("doorOpen"),
                }
                for door in doors_payload.get("data", [])
            ]
        except Exception as exc:
            token_status["error"] = str(exc)
        return token_status

    def run_health_check_once(self) -> dict[str, Any]:
        token = self.current_token()
        if not token:
            health = {
                "checked_at": utc_now_iso(),
                "ok": False,
                "error": "token missing",
                "token": None,
                "exp": None,
                "expires_at": None,
                "user": None,
                "doors": [],
            }
            snapshot = self._merge_state({"health": health})
            self._maybe_send_invalid_alert(snapshot)
            return snapshot

        health = self.validate_token(token)
        snapshot = self._merge_state({"health": health})
        if health["ok"]:
            self._reset_invalid_alert(snapshot)
        else:
            self._maybe_send_invalid_alert(snapshot)
        return snapshot

    def telegram_enabled(self) -> bool:
        return bool(self.config.telegram.bot_token and self.config.telegram.chat_id)

    def _maybe_send_invalid_alert(self, snapshot: dict[str, Any]) -> None:
        if not self.telegram_enabled():
            return
        if snapshot.get("invalid_alert_sent"):
            return
        health = snapshot.get("health", {})
        text = (
            "[door-service] token unavailable\n"
            f"time: {health.get('checked_at')}\n"
            f"error: {health.get('error')}\n"
            f"refresh: {self.config.public_base}{self.config.routes.refresh_path}"
        )
        try:
            send_telegram_message(self.config.telegram.bot_token, self.config.telegram.chat_id, text)
        except Exception as exc:
            self._merge_state({
                "invalid_alert_sent": False,
                "invalid_alert_error": str(exc),
                "invalid_alert_error_at": utc_now_iso(),
            })
            return
        self._merge_state({
            "invalid_alert_sent": True,
            "invalid_alert_sent_at": utc_now_iso(),
            "invalid_alert_error": None,
        })

    def _reset_invalid_alert(self, snapshot: dict[str, Any]) -> None:
        patch: dict[str, Any] = {"invalid_alert_error": None}
        if snapshot.get("invalid_alert_sent"):
            patch["invalid_alert_sent"] = False
        self._merge_state(patch)

    def resolve_door_code(self, requested: str | None = None) -> str:
        if requested:
            return requested
        if self.config.default_door_code:
            return self.config.default_door_code
        health = self.snapshot().get("latest", {}).get("health", {})
        doors = health.get("doors", []) if isinstance(health, dict) else []
        if doors:
            first = doors[0].get("doorCode")
            if first:
                return first
        raise ServiceError("doorCode not configured and no cached doors available")

    def open_door(self, requested_door_code: str | None = None) -> dict[str, Any]:
        token = self.current_token()
        if not token:
            raise ServiceError("token missing")
        health = self.validate_token(token)
        self._merge_state({"health": health})
        if not health["ok"]:
            self._maybe_send_invalid_alert(self.snapshot())
            raise ServiceError(f"token invalid: {health.get('error')}")
        door_code = self.resolve_door_code(requested_door_code)
        response = api_request("remote-door-open", {"doorCode": door_code}, token, method="POST")
        result = {
            "opened_at": utc_now_iso(),
            "doorCode": door_code,
            "response": response,
            "ok": response.get("result") == 0,
        }
        self._merge_state({"last_open_result": result})
        return result
