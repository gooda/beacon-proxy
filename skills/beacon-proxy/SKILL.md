---
name: beacon-proxy
description: Use when working with Beacon Proxy (mitmproxy-based proxy for UI automation). Configures mock responses, domain rewrites, network simulation (weak network, airplane mode), scenarios, and activations. Use when the user mentions proxy, mock API, request interception, mitmproxy, weak network, airplane mode, latency, throttle, packet loss, or UI test traffic control.
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

## 操作对照

| 操作 | CLI | REST |
|------|-----|------|
| 添加规则 | `beacon-proxy add-rule <url> --status <code> --body <json> -d <scenario>` | `POST /api/rules` |
| 域名重写 | `beacon-proxy add-rewrite <from> <to> -d <scenario>` | `POST /api/rules` |
| 删除规则 | `beacon-proxy remove-rule <id> [-d scenario]` | `DELETE /api/rules/{id}` |
| 激活场景 | — | `POST /api/activate` |
| 生成规则 | — | `POST /api/generate` |
| 设置网络条件 | — | `POST /api/network-condition` |
| 查看网络条件 | — | `GET /api/network-condition` |
| 清除网络条件 | — | `DELETE /api/network-condition/{client_ip}` |

完整对照见 [reference/tools-reference.md](reference/tools-reference.md)。

## 规则结构

- **单文件**：`LLM_PROXY_RULES=rules.yaml`
- **目录模式**：`LLM_PROXY_RULES=rules` → `rules/definitions/*.yaml` + `rules/scenarios/*.yaml` + `rules/activations.yaml`

## 详细文档

- `docs/TOOL_GUIDE.md` — 完整工具说明
- `docs/INTEGRATION.md` — REST API 与集成规范
