# ZWU 寝室物联网门锁 API 逆向 及苹果快捷指令集成

用于承接微信授权回调、把 `微信 Oauth code` 换成平台 `token`，并提供远程开门和刷新令牌接口，以及对接苹果快捷指令。

## 实现原理

1. 程序生成一个微信授权链接：

   ```text
   https://open.xiaofubao.com/routeauth/auth/route/ua/authorize/getCodeV2
   ```

   这个链接会带上固定参数 `authType`、`ymAppId`、`authAppid`，以及配置的 `callbackUrl`。

2. 在微信里打开授权链接后，平台会把结果回调到你的 `callback_url`。

   默认情况下它会是：

   ```text
   http://ip:port/wechat/callback
   ```

   如果你在 `config.json` 里显式设置了 `callback_url`，那就以设置地址为准。

3. 平台回调到本服务时，会在查询参数里带上 `code` 和 `errCode`，如：

   ```text
   http://ip:port/wechat/callback?code=xxxx&errCode=0
   ```

4. 然后程序会拿这个 `code` 去请求下面这个登录接口：

   ```text
   http://172.18.1.70:18080/api/loginByURL/mobile/easySchool?code=xxxx&errCode=0
   ```

5. 请求完成后，程序从这次请求**最终跳转到的 URL** 里提取 `token` 参数。

6. 拿到 `token` 之后，程序会把它放到请求头 `zhangmenWebappToken` 里，去请求实际业务接口：

   ```text
   http://172.18.1.70:18080/api/mobile/user
   http://172.18.1.70:18080/api/mobile/doors
   http://172.18.1.70:18080/api/mobile/remote-door-open
   ```

   其中：
   - `user` 用来检查当前 token 对应的用户信息
   - `doors` 用来读取门锁列表和电量等信息
   - `remote-door-open` 用来实际执行远程开门

## 仓库结构

```text
callback_collector.py      # 运行入口
door_service/             # 配置、HTTP、加密、网关、状态逻辑
config.example.json       # 示例配置
requirements.txt
```

## 配置

复制一份配置：

```bash
cp config.example.json config.json
```

然后至少修改这些字段：

- `public_base`: 你实际对外访问的基础地址
- `callback_url`: 微信回调地址；如果你走反向代理，建议明确配置
- `access_key`: 开门 API 鉴权密钥，**必填**
- `routes.base_path`: 随机路径前缀
- `telegram.bot_token` / `telegram.chat_id`: 可选，用于 token 失效提醒

## 安装

### 方式一：Python + venv

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 方式二：uv

```bash
uv venv
uv pip install -r requirements.txt
```

## 运行

### Python

```bash
python callback_collector.py
```

### uv

```bash
uv run callback_collector.py
```

启动后终端会打印：

- `public_base`
- `callback_url`
- 面板路径
- 状态页路径
- 刷新路径
- 开门 API 路径
- 授权链接

## 使用方法

### 1. 刷新 token

打开面板里的刷新入口，或者直接在微信里打开程序打印出来的授权链接。

服务收到回调后会自动：

1. 记录 `code`
2. 交换 `token`
3. 更新本地状态文件

### 2. 查看状态

访问：

```text
http://127.0.0.1:8765/door-control-panel-change-me/status?key=YOUR_ACCESS_KEY
```

可以看到当前 token、过期时间、用户信息、门锁信息和最近一次开门结果。

### 3. 远程开门

访问：

```text
http://127.0.0.1:8765/door-control-panel-change-me/api/open?key=YOUR_ACCESS_KEY
```

### 4. Apple 快捷指令集成

可以在 iPhone / iPad 上通过下面这个 iCloud 分享链接导入快捷指令：

```text
https://www.icloud.com/shortcuts/02edc2a40d6746439260a856b3e6fc5b
```

导入后，检查并修改：

1. 请求地址改成你自己的开门接口，例如：

   ```text
   http://127.0.0.1:8765/door-control-panel-change-me/api/open?key=YOUR_ACCESS_KEY
   ```

   或者

   ```text
   https://example.com/door-control-panel-change-me/api/open?key=YOUR_ACCESS_KEY
   ```

2. 把其中的 `YOUR_ACCESS_KEY` 替换成你在 `config.json` 里配置的 `access_key`
3. 如果你走了反向代理或 HTTPS，把域名改成最终对外可访问的地址
