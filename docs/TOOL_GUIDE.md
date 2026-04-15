# Beacon Proxy 工具说明

面向使用者的完整工具参考，涵盖安装、配置、入口与典型场景。

---

## 一、工具简介

**Beacon Proxy** 是基于 mitmproxy 的 HTTP(S) 代理服务，用于 UI 自动化测试中的请求拦截与改写。通过规则配置，可模拟接口异常、空数据、域名重写等场景，无需修改被测应用代码。

| 特性 | 说明 |
|------|------|
| **响应 Mock** | 匹配 URL 后改写状态码、响应体 |
| **域名重写** | 将 A 域名请求转发到 B 域名（A→B 代理） |
| **网络模拟** | 弱网（延迟、限速、丢包）、飞行模式，按设备或接口级别设置 |
| **场景与激活** | 按场景组织规则，支持按 IP 动态激活 |
| **多入口** | CLI、REST API、规则编辑器、Skills |

---

## 二、安装与启动

### 安装

```bash
pip install -e .
```

### 快速启动

```bash
# 代理 + API 同时启动（推荐）
./scripts/start.sh

# 或
beacon-proxy start --with-api
```

| 组件 | 默认端口 | 说明 |
|------|----------|------|
| 代理服务 | 8080 | 流量拦截与改写 |
| 激活 API | 8765 | 规则管理、激活、证书下载、规则编辑器 |

---

## 三、入口一览

| 入口 | 用途 | 命令/地址 |
|------|------|-----------|
| **CLI** | 脚本、CI、命令行管理规则 | `beacon-proxy <cmd>` |
| **REST API** | 外部系统集成、激活、规则 CRUD | `http://host:8765/api/*` |
| **规则编辑器** | 可视化管理场景、规则、激活 | `http://host:8765/rules` |
| **Skills** | AI 客户端（Cursor 等）依据 skill 使用 CLI/REST | `skills/beacon-proxy/` |

---

## 四、核心能力

### 4.1 响应 Mock

匹配 URL 后改写响应状态码和响应体。

```bash
beacon-proxy add-rule "/api/login" --status 500 --body '{"error":"server_error"}'
```

| 字段 | 说明 |
|------|------|
| url_pattern | URL 子串匹配，或正则（--regex） |
| status_code | 改写状态码 |
| body | 改写响应体（JSON 字符串） |

### 4.2 域名重写

将匹配域名的请求转发到目标域名。

```bash
beacon-proxy add-rewrite api.prod.example.com api.staging.example.com -d scenario_A
```

| 字段 | 说明 |
|------|------|
| url_pattern | 源域名（A） |
| upstream_host | 目标域名（B） |
| upstream_port | 目标端口，默认 443 |

### 4.3 网络模拟

按设备 IP 设置全局网络条件（弱网、飞行模式），或在规则级别对特定接口设置。

```bash
# 飞行模式（阻断所有连接）
curl -X POST http://127.0.0.1:8765/api/network-condition \
  -H "Content-Type: application/json" \
  -d '{"client_ip":"192.168.1.101","airplane_mode":true}'

# 弱网 3G
curl -X POST http://127.0.0.1:8765/api/network-condition \
  -H "Content-Type: application/json" \
  -d '{"client_ip":"192.168.1.101","delay_ms":400,"throttle_kbps":50,"packet_loss_rate":0.02}'
```

| 字段 | 说明 |
|------|------|
| airplane_mode | 飞行模式，阻断所有连接 |
| delay_ms | 延迟注入(ms) |
| throttle_kbps | 限速(KB/s) |
| packet_loss_rate | 丢包率 0.0-1.0 |

**预设参考**：

| 预设 | delay_ms | throttle_kbps | packet_loss_rate |
|------|----------|---------------|------------------|
| 弱网 3G | 400 | 50 | 0.02 |
| 弱网 4G | 150 | 200 | 0.01 |
| 高延迟 | 2000 | — | — |

**规则级别**：创建规则时可选填 `delay_ms`、`throttle_kbps`、`packet_loss_rate`，仅对匹配 URL 生效，覆盖设备级网络条件。

### 4.4 场景与激活

- **场景**：规则组，对应 `rules/scenarios/{scenario_id}.yaml`
- **激活**：将客户端 IP 与场景绑定，代理按 IP 应用对应规则

**适用**：APP、模拟器等无法注入请求头的场景。

```bash
# 激活：IP 192.168.1.101 使用 scenario_A 的规则
curl -X POST http://127.0.0.1:8765/api/activate \
  -H "Content-Type: application/json" \
  -d '{"scenario_id":"scenario_A","client_ip":"192.168.1.101"}'
```

---

## 五、规则结构

### 5.1 单文件模式

`LLM_PROXY_RULES=rules.yaml` 时，所有规则写在单一 YAML 文件：

```yaml
rules:
  - id: login_500
    url_pattern: /api/login
    status_code: 500
    body: '{"error":"server_error"}'
```

### 5.2 目录模式（definitions + scenarios）

`LLM_PROXY_RULES=rules`（目录）时，支持规则复用：

```
rules/
├── definitions/       # 可复用规则定义
│   ├── login_500.yaml
│   └── cart_empty.yaml
├── scenarios/         # 场景引用的规则
│   ├── scenario_A.yaml
│   └── scenario_B.yaml
└── activations.yaml   # IP↔场景 激活映射（API 写入）
```

**场景配置**（`scenarios/scenario_A.yaml`）：

```yaml
rule_ids:
  - login_500
  - cart_empty
overrides: {}
```

---

## 六、CLI 命令参考

| 命令 | 说明 |
|------|------|
| `beacon-proxy start` | 启动代理 |
| `beacon-proxy api` | 启动 API 服务 |
| `beacon-proxy add-rule <url>` | 添加拦截规则 |
| `beacon-proxy add-rewrite <from> <to>` | 添加域名重写 |
| `beacon-proxy remove-rule <id>` | 删除规则 |
| `beacon-proxy list-rules [-d scenario_id]` | 列出规则 |
| `beacon-proxy list-definitions` | 列出所有定义 |
| `beacon-proxy bind-rule <rule_id> <scenario_id>` | 绑定规则到场景 |
| `beacon-proxy unbind-rule <rule_id> <scenario_id>` | 从场景解绑 |

**常用选项**：

| 选项 | 说明 |
|------|------|
| `-p, --port` | 代理端口（默认 8080） |
| `-d, --scenario-id` | 场景 ID（绑定/解绑时使用） |
| `--rules <path>` | 规则文件或目录路径 |
| `--with-api` | 同时启动 API |

---

## 七、REST API 参考

**Base URL**：`http://<host>:8765`

### 激活

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /api/activate | 激活场景（绑定 IP↔场景） |
| DELETE | /api/activate/{scenario_id} | 取消某场景所有激活 |
| DELETE | /api/activate/ip/{client_ip} | 取消某 IP 激活 |
| GET | /api/activate | 列出所有激活 |
| GET | /api/activate/ip/{client_ip} | 查询某 IP 激活信息 |

### 规则 CRUD

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/rules/definitions | 列出所有规则定义 |
| GET | /api/rules?scenario_id=X | 列出某场景规则 |
| GET | /api/rules/{id} | 获取单条规则 |
| POST | /api/rules | 新增规则 |
| PUT | /api/rules/{id} | 更新规则 |
| DELETE | /api/rules/{id} | 删除规则 |
| POST | /api/rules/{id}/bind | 绑定规则到场景 |
| DELETE | /api/rules/{id}/bind/{scenario_id} | 从场景解绑 |

### 网络条件

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /api/network-condition | 设置网络条件 |
| GET | /api/network-condition | 列出所有网络条件 |
| GET | /api/network-condition/{client_ip} | 查询某 IP 网络条件 |
| DELETE | /api/network-condition/{client_ip} | 清除某 IP 网络条件 |
| DELETE | /api/network-condition | 清除所有网络条件 |

### 场景

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/scenarios | 列出场景 |
| POST | /api/scenarios | 新建场景 |

### 其他

| 路径 | 说明 |
|------|------|
| GET /certificate | 证书安装说明页 |
| GET /rules, /editor | 规则编辑器 |

---

## 八、规则编辑器

访问 `http://<host>:8765/rules` 或 `/editor`：

- **场景列表**：切换场景、新建场景
- **规则列表**：查看、编辑、删除当前场景规则
- **规则表单**：新增/编辑规则，支持 Mock 响应、域名重写、网络模拟（延迟/限速/丢包）
- **激活状态**：查看 IP↔场景映射，激活、取消激活，快捷设置网络条件（飞行模式/弱网3G/4G/高延迟）

适用于 rules 目录模式。

---

## 九、环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| LLM_PROXY_RULES | 规则文件或目录路径 | rules.yaml |
| BEACON_PROXY_CONFDIR | 证书存储目录 | ~/.mitmproxy |
| BEACON_PROXY_SCENARIO_ID_HEADER | 场景 ID 请求头名 | X-Scenario-ID |

---

## 十、典型场景

### 场景 1：Web 自动化（可注入 Header）

1. 配置浏览器/Playwright 使用代理 `127.0.0.1:8080`
2. 注入请求头 `X-Scenario-ID: scenario_A`
3. 执行用例，代理自动应用 scenario_A 的规则

### 场景 2：APP / 模拟器（按 IP 激活）

1. 获取被测设备 IP（如 192.168.1.101）
2. 调用 `POST /api/activate` 绑定 IP 与 scenario_A
3. 配置 APP 使用代理
4. 执行用例
5. 用例结束可调用 `DELETE /api/activate/ip/192.168.1.101` 清理

### 场景 3：域名重写（A→B 代理）

将线上 API 域名代理到测试/预发环境：

```bash
beacon-proxy add-rewrite api.prod.example.com api.staging.example.com -d scenario_A
```

### 场景 4：弱网 / 飞行模式测试

1. 获取被测设备 IP
2. 调用 `POST /api/network-condition` 或在 `POST /api/activate` 中传入 `network_condition`
3. 执行用例，验证 APP 弱网/断网表现
4. 测试结束调用 `DELETE /api/network-condition/{client_ip}` 或 `DELETE /api/activate/ip/{client_ip}` 清理

### 场景 5：自然语言生成规则

```bash
curl -X POST http://127.0.0.1:8765/api/generate \
  -H "Content-Type: application/json" \
  -d '{"requirement":"登录失败","scenario_id":"scenario_A","client_ip":"192.168.1.101"}'
```

支持：`飞行模式`、`弱网`、`弱网3G`、`弱网4G`、`高延迟`、`登录失败`、`购物车空`、`X 返回 Y`、`X 空`、直接 URL 等。

---

## 十一、证书配置

HTTPS 拦截需在设备上安装 CA 证书：

1. 设备配置代理后访问 `http://<API>:8765/certificate`
2. 下载对应平台证书（iOS .cer / Android .pem）
3. 按页面指引安装
4. iOS 需在「证书信任设置」中启用 mitmproxy 信任

证书默认存于 `~/.mitmproxy`，可通过 `BEACON_PROXY_CONFDIR` 自定义。

---

## 十二、相关文档

| 文档 | 说明 |
|------|------|
| [INTEGRATION.md](INTEGRATION.md) | 外部系统集成规范、API 详细说明 |
| [AI_CODING_GUIDE.md](AI_CODING_GUIDE.md) | AI 编程场景、Skills 使用 |
| [rule-editor-plan.md](plans/rule-editor-plan.md) | 规则编辑器方案 |
