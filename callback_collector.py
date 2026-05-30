from door_service.config import default_config_path, load_config
from door_service.http_app import DoorControlServer
from door_service.service import DoorControlService


def main() -> int:
    config_path = default_config_path()
    config = load_config(config_path)
    app = DoorControlService(config)
    server = DoorControlServer((config.host, config.port), app)

    app.start_background_tasks()
    print(f"[*] config = {config_path}")
    print(f"[*] listening on http://{config.host}:{config.port}")
    print(f"[*] public_base = {config.public_base}")
    print(f"[*] callback_url = {config.callback_url}")
    print(f"[*] dashboard = {config.public_base}{config.routes.dashboard_path}")
    print(f"[*] status = {config.public_base}{config.routes.status_path}")
    print(f"[*] refresh = {config.public_base}{config.routes.refresh_path}")
    print(f"[*] open_api = {config.public_base}{config.routes.open_api_path}")
    print("[*] auth_url =")
    print(app.auth_url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[*] shutting down")
    finally:
        app.stop_background_tasks()
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
