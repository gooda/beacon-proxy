# Beacon Proxy

基于 mitmproxy 的代理服务，用于 UI 自动化测试中的请求拦截与改写。支持 CLI（自动化）与 MCP（交互式调试）。

**外部系统集成**：参见 [使用规范 (INTEGRATION.md)](docs/INTEGRATION.md)，含 REST API、调用流程与示例。

## 安装

```bash
pip install -e .
# MCP 支持（可选）: pip install "beacon-proxy[mcp]"
```

## 使用

### CLI

```bash
# 启动代理（默认端口 8080）
beacon-proxy start

# 添加拦截规则
beacon-proxy add-rule "/api/login" --status 500 --body '{"error":"server_error"}'

# 列出规则
beacon-proxy list-rules

# 删除规则
beacon-proxy remove-rule rule_1
```

### MCP

```bash
beacon-proxy mcp
```

需先安装 `pip install mcp`。在 Cursor 等支持 MCP 的客户端中配置该服务器，大模型可调用 `add_rule`、`remove_rule`、`list_rules` 等工具。

### 规则文件

规则默认保存在 `rules.yaml`，可通过环境变量 `LLM_PROXY_RULES` 或 `--rules` 指定路径。

### 多设备与规则复用（服务化部署）

当 `LLM_PROXY_RULES` 指向目录（如 `rules/`）时，使用 **definitions + devices** 结构，支持规则复用：

```
rules/
├── definitions/       # 可复用规则定义
│   ├── login_500.yaml
│   └── cart_empty.yaml
└── devices/           # 设备引用的规则
    ├── device_A.yaml  # rule_ids: [login_500]
    └── device_B.yaml  # rule_ids: [login_500, cart_empty]
```

设备通过请求头 `X-Device-ID` 识别（可通过 `BEACON_PROXY_DEVICE_ID_HEADER` 自定义）。

```bash
# 使用 rules 目录
export LLM_PROXY_RULES=rules
beacon-proxy start

# 定义规则并绑定到设备
beacon-proxy add-rule "/api/login" --id login_500 --status 500 --device-id device_A

# 定义规则（不绑定）
beacon-proxy add-rule "/api/cart" --id cart_empty --body '[]'

# 将已有规则绑定到另一设备
beacon-proxy bind-rule login_500 device_B

# 从设备解绑
beacon-proxy unbind-rule login_500 device_B

# 列出所有定义
beacon-proxy list-definitions

# 列出设备规则
beacon-proxy list-rules --device-id device_A
```

客户端需在请求中带上 `X-Device-ID: device_A` 才会使用该设备的规则。

### 激活 API（按 IP 动态激活）

UI 自动化执行前调用 API，将设备 IP 与规则绑定，适用于 APP 等无法注入 Header 的场景。

```bash
# 启动代理（可选：同时启动 API）
beacon-proxy start --with-api

# 或单独启动 API 服务
beacon-proxy api
```

**API 示例：**

```bash
# 激活：设备 device_A 的请求来自 IP 192.168.1.101
curl -X POST http://127.0.0.1:8765/api/activate \
  -H "Content-Type: application/json" \
  -d '{"device_id":"device_A","client_ip":"192.168.1.101","rule_ids":["login_500","cart_empty"]}'

# 指定 rule_ids 时覆盖 devices/device_A.yaml 的配置；不传则使用设备默认规则

# 列出激活
curl http://127.0.0.1:8765/api/activate

# 取消激活
curl -X DELETE http://127.0.0.1:8765/api/activate/device_A
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
