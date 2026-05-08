---
name: beacon-proxy
description: Use when working with Beacon Proxy (mitmproxy-based proxy for UI automation). Configures mock responses, domain rewrites, network simulation (weak network, airplane mode), scenarios, activations, and remote API calls (outbound call orchestration triggered by test scripts). Use when the user mentions proxy, mock API, request interception, mitmproxy, weak network, airplane mode, latency, throttle, packet loss, remote call / outbound API / reset login state from tests, or UI test traffic control.
---

# Beacon Proxy

Beacon Proxy 是基于 mitmproxy 的 HTTP(S) 代理，用于 UI 自动化测试中的请求拦截、改写与网络模拟。

## 调用方式

使用 CLI 或 REST API。API 默认 `http://127.0.0.1:8765`。

| 入口 | 用途 |
|------|------|
| CLI | `beacon-proxy <cmd>` |
| REST API | `http://host:8765/api/*` |
| 规则编辑器 | `http://host:8765/rules` |

## 核心能力

### 响应 Mock
```bash
beacon-proxy add-rule "/api/login" --status 500 --body '{"error":"server_error"}'
```

### 域名重写
```bash
beacon-proxy add-rewrite api.prod.example.com api.staging.example.com -d scenario_A
```

### 按 IP 激活场景
```bash
curl -X POST http://host:8765/api/activate \
  -H "Content-Type: application/json" \
  -d '{"scenario_id":"scenario_A","client_ip":"192.168.1.101"}'
```

### 网络模拟（弱网 / 飞行模式）

设置设备级网络条件（作用于该 IP 的全部流量）：
```bash
# 飞行模式（阻断所有连接）
curl -X POST http://host:8765/api/network-condition \
  -H "Content-Type: application/json" \
  -d '{"client_ip":"192.168.1.101","airplane_mode":true}'

# 弱网 3G（延迟 400ms + 限速 50KB/s + 2% 丢包）
curl -X POST http://host:8765/api/network-condition \
  -H "Content-Type: application/json" \
  -d '{"client_ip":"192.168.1.101","delay_ms":400,"throttle_kbps":50,"packet_loss_rate":0.02}'

# 清除网络条件
curl -X DELETE http://host:8765/api/network-condition/192.168.1.101
```

也可在规则级别设置（仅对匹配 URL 生效）：
```bash
curl -X POST http://host:8765/api/rules \
  -H "Content-Type: application/json" \
  -d '{"url_pattern":"/api/login","delay_ms":3000,"scenario_id":"scenario_A"}'
```

### 预设网络条件

| 预设 | delay_ms | throttle_kbps | packet_loss_rate |
|------|----------|---------------|------------------|
| 弱网 3G | 400 | 50 | 0.02 |
| 弱网 4G | 150 | 200 | 0.01 |
| 高延迟 | 2000 | — | — |
| 飞行模式 | — | — | — (airplane_mode=true) |

### 远端调用（出站 API 编排）

测试用例执行时主动触发出站 API 调用（如"重置登录状态"）。代理作为可配置的出站 HTTP 客户端，**不走拦截链路**，与 rules / network_condition 独立管理。

```bash
# 注册定义（URL/headers 支持 {{var}} 模板）
curl -X POST http://host:8765/api/remote-calls \
  -H "Content-Type: application/json" \
  -d '{"id":"reset_login","method":"POST","url":"https://api-test.example.com/user/{{user_id}}/reset"}'

# 同步触发
curl -X POST http://host:8765/api/remote-calls/reset_login/invoke \
  -H "Content-Type: application/json" \
  -d '{"variables":{"user_id":"12345"},"client_ip":"192.168.1.101"}'

# 异步触发 + 轮询
curl -X POST 'http://host:8765/api/remote-calls/reset_login/invoke?mode=async' ...
curl http://host:8765/api/remote-calls/calls/{call_id}
```

**模板变量**：`{{caller_var}}` + 自动注入 `device.client_ip` / `device.scenario_id` / `device.last_request.{path,headers.<n>,query.<n>}`（从 activations 和最近被代理请求取值，常用于复用设备的 Authorization header）。

**错误透传**：远端 5xx / 超时 / 网络错误时 HTTP 仍返回 200，业务语义看 `ok` / `error` 字段。

## 操作对照

| 操作 | CLI | REST |
|------|-----|------|
| 添加规则 | `beacon-proxy add-rule <url> --status <code> --body <json> -d <scenario>` | `POST /api/rules` |
| 域名重写 | `beacon-proxy add-rewrite <from> <to> -d <scenario>` | `POST /api/rules` |
| 删除规则 | `beacon-proxy remove-rule <id> [-d scenario]` | `DELETE /api/rules/{id}` |
| 激活场景 | `beacon-proxy activate <scenario> <ip> [--rule-ids ...]` | `POST /api/activate` |
| 取消激活 | `beacon-proxy deactivate --scenario\|--ip\|--all` | `DELETE /api/activate/*` |
| 列出激活 | `beacon-proxy list-activations` | `GET /api/activate` |
| 生成规则 | `beacon-proxy generate <requirement> --ip <ip>` | `POST /api/generate` |
| 设置网络条件 | `beacon-proxy set-net-condition <ip> --preset 3g\|4g\|airplane\|latency` | `POST /api/network-condition` |
| 查看网络条件 | `beacon-proxy list-net-conditions` | `GET /api/network-condition` |
| 清除网络条件 | `beacon-proxy clear-net-condition --ip <ip>\|--all` | `DELETE /api/network-condition/*` |
| 注册远端调用 | `beacon-proxy remote-call add <id> -u <url> [-X M] [-H K=V]` | `POST /api/remote-calls` |
| 列出/查看远端调用 | `beacon-proxy remote-call list\|get <id>` | `GET /api/remote-calls[/{id}]` |
| 删除远端调用 | `beacon-proxy remote-call delete <id>` | `DELETE /api/remote-calls/{id}` |
| 触发远端调用 | `beacon-proxy remote-call invoke <id> [--var K=V] [--async]` | `POST /api/remote-calls/{id}/invoke?mode=sync\|async` |
| 查调用结果 | `beacon-proxy remote-call get-call <call_id>` | `GET /api/remote-calls/calls/{call_id}` |
| 最近调用列表 | `beacon-proxy remote-call calls [-n N]` | `GET /api/remote-calls/calls?limit=N` |

完整对照见 [reference/tools-reference.md](reference/tools-reference.md)。

## 规则结构

- **单文件**：`LLM_PROXY_RULES=rules.yaml`
- **目录模式**：`LLM_PROXY_RULES=rules` → `rules/definitions/*.yaml` + `rules/scenarios/*.yaml` + `rules/activations.yaml`

## 详细文档

- `docs/TOOL_GUIDE.md` — 完整工具说明
- `docs/INTEGRATION.md` — REST API 与集成规范
