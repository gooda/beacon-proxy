# Beacon Proxy

基于 mitmproxy 的代理服务，用于 UI 自动化测试中的请求拦截、改写与网络模拟。支持 CLI、REST API 与 Skills（AI 编程）。

- **工具说明**：[TOOL_GUIDE.md](docs/TOOL_GUIDE.md) — 安装、配置、入口、命令与 API 参考
- **外部系统集成**：[使用规范 (INTEGRATION.md)](docs/INTEGRATION.md) — REST API、调用流程与示例
- **AI 编程场景**：[AI Coding 使用指南 (AI_CODING_GUIDE.md)](docs/AI_CODING_GUIDE.md) — Skills、对话式 mock、TDD 等

## 安装

```bash
pip install -e .
```

### Agent Skills（Cursor / Claude Code 等）

在 AI 编程助手中安装 Beacon Proxy 技能，便于对话中配置代理、规则与激活：

```bash
# 从本仓库安装（需替换为实际仓库 URL）
npx skills add https://github.com/your-org/mitmproxy-server
# 或 GitLab
npx skills add https://gitlab.com/your-org/mitmproxy-server

# 仅安装 beacon-proxy 技能
npx skills add https://github.com/your-org/mitmproxy-server --skill beacon-proxy
```

安装后，当对话涉及 proxy、mock API、请求拦截等时，AI 会自动应用该技能。

## 打包与部署

### tar 包（跨设备部署）

```bash
./scripts/package.sh
# 生成 dist/beacon-proxy-0.1.0.tar.gz
```

部署到其他设备：

```bash
tar -xzf beacon-proxy-0.1.0.tar.gz && cd beacon-proxy-0.1.0
pip install -r requirements.txt && pip install .
./scripts/start.sh
```

### 脚本部署（推荐）

使用 `deploy.sh` 自动打包、传输、安装并启动，支持远程和本地部署：

```bash
# 部署到远程服务器（从 deploy.conf 读取配置）
./scripts/deploy.sh jenkins --start

# 部署到本地目录
./scripts/deploy.sh local --start

# 列出所有部署目标
./scripts/deploy.sh --list
```

部署后目录结构：

```
<部署目录>/
├── app/        # 代码（每次部署覆盖）
├── config/     # 规则 + 激活（持久化）
└── venv/       # Python 虚拟环境（持久化）
```

部署后在服务器上手动启动：

```bash
cd <部署目录>
source venv/bin/activate
./app/scripts/start.sh
```

## 使用

### 快速启动

```bash
# 使用启动脚本（代理 + API，推荐）
./scripts/start.sh

# 自定义端口
./scripts/start.sh --port 8080 --api-port 8765 --rules rules
```

### CLI

CLI 命令分为：**规则管理**（add-rule/add-rewrite/remove-rule/bind-rule/unbind-rule/list-rules/list-definitions）、**激活与网络条件**（activate/deactivate/list-activations/set-net-condition/clear-net-condition/list-net-conditions）、**自然语言生成**（generate）、**远端调用**（`remote-call add/list/get/update/delete/invoke/calls/get-call`）、**服务启动**（start/api）。完整列表见 [TOOL_GUIDE.md 六、CLI 命令参考](docs/TOOL_GUIDE.md)。

```bash
# 启动代理（默认端口 8080）
beacon-proxy start

# 添加拦截规则
beacon-proxy add-rule "/api/login" --status 500 --body '{"error":"server_error"}'

# 添加域名重写（A 域名 -> B 域名）
beacon-proxy add-rewrite api.prod.example.com api.staging.example.com -d scenario_A

# 列出规则
beacon-proxy list-rules

# 删除规则
beacon-proxy remove-rule rule_1

# 激活 / 网络条件
beacon-proxy activate scenario_A 192.168.1.101
beacon-proxy set-net-condition 192.168.1.101 --preset 3g
beacon-proxy list-activations

# 自然语言生成
beacon-proxy generate "登录失败" --ip 192.168.1.101

# 远端调用
beacon-proxy remote-call add reset_login -X POST -u https://api-test.example.com/user/{{user_id}}/reset
beacon-proxy remote-call invoke reset_login --var user_id=42 --client-ip 192.168.1.101
beacon-proxy remote-call calls -n 20
```

### 规则文件

规则默认保存在 `rules.yaml`，可通过环境变量 `LLM_PROXY_RULES` 或 `--rules` 指定路径。

### 多设备与规则复用（服务化部署）

当 `LLM_PROXY_RULES` 指向目录（如 `rules/`）时，使用 **definitions + scenarios** 结构，支持规则复用：

```
rules/
├── definitions/       # 可复用规则定义
│   ├── login_500.yaml
│   └── cart_empty.yaml
└── scenarios/         # 场景引用的规则
    ├── scenario_A.yaml  # rule_ids: [login_500]
    └── scenario_B.yaml  # rule_ids: [login_500, cart_empty]
```

场景通过请求头 `X-Scenario-ID` 识别（可通过 `BEACON_PROXY_SCENARIO_ID_HEADER` 自定义）。

```bash
# 使用 rules 目录
export LLM_PROXY_RULES=rules
beacon-proxy start

# 定义规则并绑定到场景
beacon-proxy add-rule "/api/login" --id login_500 --status 500 --scenario-id scenario_A

# 定义规则（不绑定）
beacon-proxy add-rule "/api/cart" --id cart_empty --body '[]'

# 将已有规则绑定到另一场景
beacon-proxy bind-rule login_500 scenario_B

# 从场景解绑
beacon-proxy unbind-rule login_500 scenario_B

# 列出所有定义
beacon-proxy list-definitions

# 列出场景规则
beacon-proxy list-rules --scenario-id scenario_A
```

客户端需在请求中带上 `X-Scenario-ID: scenario_A` 才会使用该场景的规则。

### 激活 API（按 IP 动态激活）

UI 自动化执行前调用 API，将设备 IP 与规则绑定，适用于 APP 等无法注入 Header 的场景。

```bash
# 启动代理（可选：同时启动 API）
beacon-proxy start --with-api

# 或单独启动 API 服务
beacon-proxy api
```

**证书配置**：HTTPS 拦截需在设备上安装 CA 证书。证书默认存于 `~/.mitmproxy`，可通过 `BEACON_PROXY_CONFDIR` 自定义。设备配置代理后访问 `http://<API地址>:8765/certificate` 下载；移动端需 `--api-host 0.0.0.0`。详见 [INTEGRATION.md 7.1 证书配置与安装](docs/INTEGRATION.md)。

## 八、规则编辑器

![规则编辑器](http://dap-ai.fp.ps.netease.com/file/69ba74d3dbc5625e5b9cb461533QuEFe07)
访问 `http://<host>:8765/rules` 或 `/editor`，包含三个 Tab：

- **规则配置**：场景与规则的 CRUD（Mock 响应、域名重写、规则级网络模拟）
- **规则应用**：IP↔场景激活，快捷设置网络条件（飞行模式/弱网3G/4G/高延迟）
- **远端调用**：调用定义 CRUD + 同步/异步触发 + 最近调用历史

**API 示例：**

```bash
# 激活：场景 scenario_A 的请求来自 IP 192.168.1.101
curl -X POST http://127.0.0.1:8765/api/activate \
  -H "Content-Type: application/json" \
  -d '{"scenario_id":"scenario_A","client_ip":"192.168.1.101","rule_ids":["login_500","cart_empty"]}'

# 指定 rule_ids 时覆盖 scenarios/scenario_A.yaml 的配置；不传则使用场景默认规则

# 列出激活
curl http://127.0.0.1:8765/api/activate

# 取消激活（按场景，清除该场景下所有 IP）
curl -X DELETE http://127.0.0.1:8765/api/activate/scenario_A

# 取消激活（按 IP，仅清除指定设备）
curl -X DELETE http://127.0.0.1:8765/api/activate/ip/192.168.1.101

# 取消所有激活（清除全部 IP 绑定，代理恢复透传状态）
curl -X DELETE http://127.0.0.1:8765/api/activate
```

**持久化**：激活信息保存在 `activations.yaml`（与 rules 同目录），重启代理后仍生效。

### 网络模拟（弱网 / 飞行模式）

支持按设备 IP 设置网络条件（延迟、限速、丢包、飞行模式），也可在激活时一并传入。

```bash
# 飞行模式（阻断所有连接）
curl -X POST http://127.0.0.1:8765/api/network-condition \
  -H "Content-Type: application/json" \
  -d '{"client_ip":"192.168.1.101","airplane_mode":true}'

# 弱网 3G（延迟 400ms + 限速 50KB/s + 2% 丢包）
curl -X POST http://127.0.0.1:8765/api/network-condition \
  -H "Content-Type: application/json" \
  -d '{"client_ip":"192.168.1.101","delay_ms":400,"throttle_kbps":50,"packet_loss_rate":0.02}'

# 激活时同时设置网络条件
curl -X POST http://127.0.0.1:8765/api/activate \
  -H "Content-Type: application/json" \
  -d '{"scenario_id":"scenario_A","client_ip":"192.168.1.101","network_condition":{"delay_ms":2000}}'

# 清除网络条件
curl -X DELETE http://127.0.0.1:8765/api/network-condition/192.168.1.101

# 查看所有网络条件
curl http://127.0.0.1:8765/api/network-condition
```

也可在规则级别对特定接口设置延迟/限速/丢包，详见 [INTEGRATION.md](docs/INTEGRATION.md)。

### 远端调用（出站 API 编排）

测试用例执行时主动触发出站 API 调用（如「重置登录状态」「初始化测试数据」）。代理服务作为可配置的出站 HTTP 客户端，**不走 mitmproxy 拦截链路**，与 rules / network_condition 独立管理。

```bash
# 1) 注册一个调用定义（支持 {{var}} 模板 + device 上下文变量）
curl -X POST http://127.0.0.1:8765/api/remote-calls \
  -H "Content-Type: application/json" \
  -d '{
    "id": "reset_login",
    "method": "POST",
    "url": "https://api-test.example.com/user/{{user_id}}/reset",
    "headers": {"Authorization": "{{device.last_request.headers.authorization}}"}
  }'

# 2) 同步触发（默认）
curl -X POST http://127.0.0.1:8765/api/remote-calls/reset_login/invoke \
  -H "Content-Type: application/json" \
  -d '{"variables":{"user_id":"12345"},"client_ip":"10.0.0.5"}'

# 3) 异步触发 + 轮询结果
CALL_ID=$(curl -sX POST 'http://127.0.0.1:8765/api/remote-calls/reset_login/invoke?mode=async' \
  -d '{"variables":{"user_id":"12345"}}' -H "Content-Type: application/json" | jq -r .call_id)
curl http://127.0.0.1:8765/api/remote-calls/calls/$CALL_ID

# 4) 一次性调用（不落库）
curl -X POST http://127.0.0.1:8765/api/remote-calls/invoke \
  -H "Content-Type: application/json" \
  -d '{"id":"once","method":"GET","url":"https://api/health"}'
```

**模板变量**：
- `{{ caller_var }}` — invoke body 里 `variables` 注入
- `{{ device.client_ip }}` / `{{ device.scenario_id }}` — 自动从激活信息取
- `{{ device.last_request.path }}` / `{{ device.last_request.headers.<name> }}` — 自动从该 IP 最近一次被代理的请求取（适合复用 token、trace id）

**特性**：
- HTTP 层错误透传（远端 5xx / 超时 / 网络错误）始终返回 200 + `ok:false` + `error` 字段
- async 模式立即返回 `call_id`（pending），通过 `GET /api/remote-calls/calls/{id}` 轮询
- 调用历史保留在内存环形 buffer（最近 100 条 / 10 分钟 TTL），可通过 `GET /api/remote-calls/calls` 查看

详细 API 与字段定义见 [INTEGRATION.md 3.10 远端调用](docs/INTEGRATION.md)。

### Mock 数据示例

**单文件模式**（`rules.yaml`）：

```yaml
rules:
  - id: login_500
    url_pattern: /api/login
    description: 模拟登录服务异常
    status_code: 500
    body: '{"code":500,"message":"Internal Server Error"}'

  - id: cart_empty
    url_pattern: /api/cart
    description: 模拟空购物车
    status_code: 200
    body: '{"items":[],"total":0}'

  - id: user_list_empty
    url_pattern: /api/users
    description: 模拟用户列表为空
    status_code: 200
    body: '{"users":[],"total":0}'
```

**CLI 添加**：

```bash
beacon-proxy add-rule "/api/login" --id login_500 --status 500 \
  --body '{"code":500,"message":"Internal Server Error"}' \
  --description "模拟登录服务异常"

beacon-proxy add-rule "/api/cart" --id cart_empty --status 200 \
  --body '{"items":[],"total":0}' \
  --description "模拟空购物车"
```

**验证**（代理启动后）：

```bash
# 通过代理请求，应返回 mock 数据
curl -x http://127.0.0.1:8080 https://your-api.com/api/login
# 返回: {"code":500,"message":"Internal Server Error"}  状态码 500

curl -x http://127.0.0.1:8080 https://your-api.com/api/cart
# 返回: {"items":[],"total":0}  状态码 200
```

完整示例见 `examples/mock-rules.yaml`。
