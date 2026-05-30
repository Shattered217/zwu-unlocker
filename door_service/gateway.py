import json
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse
from urllib.request import Request, urlopen

from door_service.constants import AUTH_PARAMS, BASE_API, LOGIN_URL, OPEN_URL, TIMEOUT, WECHAT_USER_AGENT
from door_service.crypto import decrypt_text, encrypt_json


class ServiceError(RuntimeError):
    pass


def build_auth_url(callback_url: str) -> str:
    params = dict(AUTH_PARAMS)
    params["callbackUrl"] = callback_url
    return OPEN_URL + "?" + urlencode(params)


def extract_token_from_url(url: str) -> str | None:
    token = parse_qs(urlparse(url).query).get("token", [None])[0]
    return token or None


def http_request(
    url: str,
    method: str = "GET",
    body: bytes | None = None,
    headers: dict[str, str] | None = None,
    timeout: int = TIMEOUT,
) -> tuple[str, str]:
    req = Request(url, data=body, method=method)
    req.add_header("User-Agent", WECHAT_USER_AGENT)
    req.add_header("Referer", "http://172.18.1.70:9090/")
    req.add_header("X-Requested-With", "com.tencent.mm")
    if headers:
        for key, value in headers.items():
            req.add_header(key, value)
    with urlopen(req, timeout=timeout) as response:
        return response.geturl(), response.read().decode("utf-8", "replace")


def exchange_code_for_token(code: str, err_code: str = "0") -> dict[str, str | bool | None]:
    url = LOGIN_URL + "?" + urlencode({"code": code, "errCode": err_code})
    final_url, body = http_request(url)
    token = extract_token_from_url(final_url)
    return {
        "exchange_attempted": True,
        "exchange_ok": bool(token),
        "exchange_url": url,
        "final_url": final_url,
        "token": token,
        "exchange_body_preview": body[:300],
        "error": None if token else "token not found in redirect URL",
    }


def api_request(path: str, data: dict[str, Any], token: str, method: str = "GET") -> dict[str, Any]:
    method = method.upper()
    headers = {
        "zhangmenWebappToken": token,
        "content-type": "application/json" if method != "POST" else "application/x-www-form-urlencoded",
    }
    if method == "GET":
        url = BASE_API + path + "?" + urlencode({"str": encrypt_json(data)})
        _, raw = http_request(url, method="GET", headers=headers)
    else:
        url = BASE_API + path
        body = encrypt_json(data).encode("utf-8")
        _, raw = http_request(url, method=method, body=body, headers=headers)

    try:
        plain = decrypt_text(raw)
    except Exception:
        plain = raw
    return json.loads(plain)


def send_telegram_message(bot_token: str, chat_id: str, text: str) -> None:
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = urlencode({"chat_id": chat_id, "text": text}).encode("utf-8")
    http_request(url, method="POST", body=payload, headers={"content-type": "application/x-www-form-urlencoded"}, timeout=15)
