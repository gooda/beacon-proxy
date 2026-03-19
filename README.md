# Beacon Proxy

基于 mitmproxy 的代理服务，用于 UI 自动化测试中的请求拦截与改写。支持 CLI、REST API 与 Skills（AI 编程）。

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


## 使用

### 快速启动

```bash
# 使用启动脚本（代理 + API，推荐）
./scripts/start.sh

# 自定义端口
./scripts/start.sh --port 8080 --api-port 8765 --rules rules
```

### CLI

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

**规则编辑器**：API 启动后访问 `http://<API地址>:8765/rules` 或 `/editor`，可可视化管理场景、规则与激活。

**API 示例：**

```bash
# 激活：场景 scenario_A 的请求来自 IP 192.168.1.101
curl -X POST http://127.0.0.1:8765/api/activate \
  -H "Content-Type: application/json" \
  -d '{"scenario_id":"scenario_A","client_ip":"192.168.1.101","rule_ids":["login_500","cart_empty"]}'

# 指定 rule_ids 时覆盖 scenarios/scenario_A.yaml 的配置；不传则使用场景默认规则

# 列出激活
curl http://127.0.0.1:8765/api/activate

# 取消激活
curl -X DELETE http://127.0.0.1:8765/api/activate/scenario_A
curl -X DELETE http://127.0.0.1:8765/api/activate/ip/192.168.1.101
```

**持久化**：激活信息保存在 `activations.yaml`（与 rules 同目录），重启代理后仍生效。

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
