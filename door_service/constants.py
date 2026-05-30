OPEN_URL = "https://open.xiaofubao.com/routeauth/auth/route/ua/authorize/getCodeV2"
LOGIN_URL = "http://172.18.1.70:18080/api/loginByURL/mobile/easySchool"
BASE_API = "http://172.18.1.70:18080/api/mobile/"

AUTH_PARAMS = {
    "authType": "2",
    "ymAppId": "2502603627238621185",
    "authAppid": "10876",
}

DEFAULT_CALLBACK_PATH = "/wechat/callback"
DEFAULT_DASHBOARD_PATH = "/door-control-panel-change-me"
DEFAULT_STATE_FILE = "callback_state.json"
DEFAULT_CONFIG_FILE = "config.json"
DEFAULT_HEALTH_INTERVAL = 300
TIMEOUT = 20

KEY = b"abcdef0123456789"
IV = b"abcdef0123456789"

WECHAT_USER_AGENT = (
    "Mozilla/5.0 (Linux; Android 15; 22127RK46C Build/AQ3A.250226.002; wv) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/116.0.0.0 "
    "Mobile Safari/537.36 XWEB/1160289 MMWEBSDK/20260101 MMWEBID/5319 "
    "REV/d9bd9f73ab9a2b3cf0e05598dfe5f36c97321fc3 MicroMessenger/8.0.68.3003"
    "(0x28004443) WeChat/arm64 Weixin GPVersion/1 NetType/WIFI Language/zh_CN ABI/arm64"
)
