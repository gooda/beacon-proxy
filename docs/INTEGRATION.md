# Beacon Proxy 使用规范

面向外部系统（UI 自动化、测试平台、CI 等）的集成指南。

---

## 1. 服务概览

| 组件         | 默认端口 | 用途                   |
| ------------ | -------- | ---------------------- |
| **代理服务** | 8080     | 流量拦截与改写         |
| **激活 API** | 8765     | 按 IP 动态绑定设备规则 |

**部署方式**：代理与 API 可同机部署，或 API 单独部署（共享 rules 目录）。

---

## 2. 集成模式

### 2.1 模式 A：浏览器 / 可注入 Header 的客户端

客户端在请求中携带 `X-Device-ID`，代理按 Header 选择规则。

```
客户端 --[X-Device-ID: device_A]--> 代理:8080 --> 目标服务
```

**适用**：Web 自动化（Puppeteer/Playwright 可注入 Header）、Postman 等。

### 2.2 模式 B：APP / 无法注入 Header 的客户端

通过激活 API 将「客户端 IP」与「设备 ID」绑定，代理按 IP 选择规则。

```
1. 测试前：调用 POST /api/activate 绑定 IP <-> device_id
2. 客户端 --[无 Header]--> 代理:8080 --> 目标服务
3. 代理根据 client_ip 查找 device_id，应用对应规则
```

**适用**：移动端 APP、模拟器、真机等。

---

## 3. REST API 规范

**Base URL**：`http://<host>:8765`（默认 `http://127.0.0.1:8765`）

**Content-Type**：`application/json`

### 3.1 激活设备规则

将指定 IP 的流量绑定到某设备的规则集。

```
POST /api/activate
```

**请求体**：

| 字段      | 类型     | 必填 | 说明                                               |
| --------- | -------- | ---- | -------------------------------------------------- |
| device_id | string   | 是   | 设备 ID，对应 rules/devices/{device_id}.yaml       |
| client_ip | string   | 是   | 客户端 IP（代理看到的连接来源 IP）                 |
| rule_ids  | string[] | 否   | 规则 ID 列表，覆盖设备默认规则；不传则使用设备配置 |

**请求示例**：

```json
{
  "device_id": "device_A",
  "client_ip": "192.168.1.101"
}
```

```json
{
  "device_id": "device_B",
  "client_ip": "10.0.0.5",
  "rule_ids": ["login_500", "cart_empty"]
}
```

**响应**（200）：

```json
{
  "ok": true,
  "message": "Activated device device_A for IP 192.168.1.101"
}
```

### 3.2 按设备取消激活

取消该设备的所有 IP 绑定。

```
DELETE /api/activate/{device_id}
```

**响应**（200）：

```json
{
  "ok": true,
  "message": "Deactivated device device_A"
}
```

**错误**（404）：设备未在激活列表中。

### 3.3 按 IP 取消激活

取消指定 IP 的激活。

```
DELETE /api/activate/ip/{client_ip}
```

**示例**：`DELETE /api/activate/ip/192.168.1.101`

**响应**（200）：

```json
{
  "ok": true,
  "message": "Deactivated IP 192.168.1.101"
}
```

**错误**（404）：该 IP 未激活。

### 3.4 列出所有激活

```
GET /api/activate
```

**响应**（200）：

```json
{
  "ip_to_device": {
    "192.168.1.101": "device_A",
    "10.0.0.5": "device_B"
  },
  "device_rule_overrides": {
    "device_B": ["login_500", "cart_empty"]
  }
}
```

### 3.5 查询某 IP 的激活信息

```
GET /api/activate/ip/{client_ip}
```

**响应**（200）：

```json
{
  "client_ip": "192.168.1.101",
  "device_id": "device_A",
  "rule_count": 1,
  "rules": [{ "id": "login_500", "url_pattern": "/api/login" }]
}
```

**错误**（404）：该 IP 未激活。

---

## 4. 调用流程示例

### 4.1 UI 自动化（APP 场景）

```text
1. 获取被测设备/模拟器 IP（如 192.168.1.101）
2. 确定要 mock 的场景（如 device_A：登录失败）
3. POST /api/activate 绑定 IP 与 device_A
4. 配置被测 APP 使用代理 192.168.x.x:8080
5. 执行自动化用例
6. 用例结束：DELETE /api/activate/ip/192.168.1.101（可选，清理）
```

### 4.2 浏览器场景（X-Device-ID）

```text
1. 配置浏览器/Playwright 使用代理 127.0.0.1:8080
2. 注入请求头 X-Device-ID: device_A
3. 执行用例，代理自动应用 device_A 的规则
```

---

## 5. 规则与设备配置

### 5.1 目录结构（rules 目录模式）

```text
rules/
├── definitions/          # 可复用规则定义
│   ├── login_500.yaml
│   └── cart_empty.yaml
├── devices/               # 设备绑定的规则
│   ├── device_A.yaml
│   └── device_B.yaml
└── activations.yaml       # 激活映射（API 写入，持久化）
```

### 5.2 规则定义格式

```yaml
id: login_500
url_pattern: /api/login
description: 模拟登录失败
status_code: 500
body: '{"code":500,"message":"Internal Server Error"}'
use_regex: false
```

| 字段        | 说明                                    |
| ----------- | --------------------------------------- |
| url_pattern | URL 子串匹配，或正则（use_regex: true） |
| status_code | 改写响应状态码                          |
| body        | 改写响应体（JSON 字符串）               |

### 5.3 设备配置格式

```yaml
rule_ids:
  - login_500
  - cart_empty
overrides: {} # 可选，对某规则的字段覆盖
```

---

## 6. 环境变量

| 变量                          | 说明               | 默认值      |
| ----------------------------- | ------------------ | ----------- |
| LLM_PROXY_RULES               | 规则文件或目录路径 | rules.yaml  |
| BEACON_PROXY_DEVICE_ID_HEADER | 设备 ID 请求头名   | X-Device-ID |

---

## 7. 启动命令

```bash
# 仅代理
beacon-proxy start --port 8080 --rules rules

# 代理 + 激活 API（推荐服务化部署）
beacon-proxy start --port 8080 --with-api --api-port 8765 --rules rules

# 仅 API（与代理共享 rules 目录，可跨机部署）
LLM_PROXY_RULES=/path/to/rules beacon-proxy api --host 0.0.0.0 --port 8765
```

---

## 7.1 证书安装（HTTPS 拦截）

iOS/Android 等设备需安装 mitmproxy CA 证书后，HTTPS 流量才能正常通过代理。

**HTTP 服务**：API 服务提供证书下载页面，设备配置代理后访问：

```
http://<API地址>:8765/certificate
```

**移动端访问**：需将 API 绑定到 `0.0.0.0`，以便同网段设备访问：

```bash
# 方式一：启动时指定
beacon-proxy start --with-api --api-host 0.0.0.0

# 方式二：单独启动 API
beacon-proxy api --host 0.0.0.0
```

设备在浏览器中访问 `http://<宿主机IP>:8765/certificate`，按页面指引下载并安装证书。

**环境变量**：若 mitmproxy 使用自定义配置目录，可设置 `BEACON_PROXY_CONFDIR` 指向该目录。

---

## 7.2 系统级请求过滤（默认开启）

代理会收到大量系统级请求（iCloud、Apple、埋点、Sentry、HTTPDNS 等），这些通常不需要 mock，且会增加日志噪音和 TLS 握手失败（证书固定）。

**默认行为**：`--ignore-system` 默认开启，将常见系统/分析域名走隧道转发（不解密），减少无意义拦截。

覆盖范围：`*.icloud.com`、`*.apple.com`、`*.sentry*`、`*collect*`、`*metric*`、`*analytics*`、HTTPDNS、Google Analytics 等。

**关闭**：若需拦截上述域名，使用 `--no-ignore-system`：

```bash
beacon-proxy start --no-ignore-system --with-api
```

**额外忽略**：可与 `--ignore-hosts` 叠加，例如：

```bash
beacon-proxy start --ignore-hosts '.*\\.qq\\.com'
```

---

## 7.3 证书固定（Certificate Pinning）导致 App 网络失败

若 Safari 正常、某 App 仍失败，多为该 App 做了**证书固定**，不信任系统 CA。

**处理**：对使用证书固定的域名启用隧道转发（不解密），让流量直连目标服务器：

```bash
# 忽略指定域名，使其走隧道（正则，逗号分隔）
beacon-proxy start --ignore-hosts '.*\\.apple\\.com,.*\\.qq\\.com'
```

被忽略的域名无法 mock，但 App 可正常联网。仅对需要 mock 的 API 域名不加入 ignore。

---

## 7.4 IP 直连 / HTTPDNS 导致上游证书校验失败

App 通过 HTTPDNS 拿到 IP 后直接用 IP 发起 HTTPS，服务器证书是域名的，代理连接上游时校验失败（`Certificate verify failed: IP address mismatch`）。

**处理**：使用 `--ssl-insecure` / `-k` 跳过上游证书校验：

```bash
beacon-proxy start --ssl-insecure --with-api
```

此时仍可拦截并 mock 这些请求，仅上游连接不再校验证书。

---

## 8. 调用示例

### cURL

```bash
# 激活
curl -X POST http://127.0.0.1:8765/api/activate \
  -H "Content-Type: application/json" \
  -d '{"device_id":"device_A","client_ip":"192.168.1.101"}'

# 查询
curl http://127.0.0.1:8765/api/activate/ip/192.168.1.101

# 取消
curl -X DELETE http://127.0.0.1:8765/api/activate/ip/192.168.1.101
```

### Python

```python
import requests

API_BASE = "http://127.0.0.1:8765"

def activate(device_id: str, client_ip: str, rule_ids: list | None = None):
    r = requests.post(f"{API_BASE}/api/activate", json={
        "device_id": device_id,
        "client_ip": client_ip,
        "rule_ids": rule_ids,
    })
    r.raise_for_status()
    return r.json()

def deactivate_ip(client_ip: str):
    r = requests.delete(f"{API_BASE}/api/activate/ip/{client_ip}")
    r.raise_for_status()
    return r.json()

# 用例前
activate("device_A", "192.168.1.101")
# 执行自动化...
# 用例后
deactivate_ip("192.168.1.101")
```

### JavaScript / Node.js

```javascript
const API_BASE = "http://127.0.0.1:8765";

async function activate(deviceId, clientIp, ruleIds = null) {
  const res = await fetch(`${API_BASE}/api/activate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      device_id: deviceId,
      client_ip: clientIp,
      rule_ids: ruleIds,
    }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

async function deactivateByIp(clientIp) {
  const res = await fetch(`${API_BASE}/api/activate/ip/${clientIp}`, {
    method: "DELETE",
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}
```

---

## 9. 错误与约定

| HTTP 状态 | 说明                                   |
| --------- | -------------------------------------- |
| 200       | 成功                                   |
| 404       | 资源不存在（如未激活的 IP/设备）       |
| 422       | 请求体校验失败（缺必填字段、类型错误） |
| 500       | 服务端异常                             |

**约定**：

- `client_ip` 必须是代理连接时看到的来源 IP，通常为被测设备在代理所在网络的 IP。
- 同一 IP 只能绑定一个设备，重复激活会覆盖。
- 激活信息持久化到 `activations.yaml`，代理重启后仍生效。

---

## 10. 附录：CLI 与 MCP

**CLI**：用于规则管理、服务启动，适合脚本与 CI。

```bash
beacon-proxy add-rule "/api/login" --id login_500 --status 500 --device-id device_A
beacon-proxy list-rules --device-id device_A
beacon-proxy start --with-api --rules rules
```

**MCP**：供 Cursor 等 AI 客户端调用，支持 `add_rule`、`activate`、`deactivate` 等工具，用于交互式调试。
