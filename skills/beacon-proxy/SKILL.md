---
name: beacon-proxy
description: Use when working with Beacon Proxy (mitmproxy-based proxy for UI automation). Configures mock responses, domain rewrites, scenarios, and activations. Use when the user mentions proxy, mock API, request interception, mitmproxy, or UI test traffic control.
---

# Beacon Proxy

Beacon Proxy 是基于 mitmproxy 的 HTTP(S) 代理，用于 UI 自动化测试中的请求拦截与改写。

## 快速参考

| 入口 | 用途 |
|------|------|
| CLI | `beacon-proxy <cmd>` |
| REST API | `http://host:8765/api/*` |
| 规则编辑器 | `http://host:8765/rules` |
| MCP | `beacon-proxy mcp`（Cursor 等 AI 客户端） |

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

## 规则结构

- **单文件**：`LLM_PROXY_RULES=rules.yaml`
- **目录模式**：`LLM_PROXY_RULES=rules` → `rules/definitions/*.yaml` + `rules/scenarios/*.yaml` + `rules/activations.yaml`

## 详细文档

在 beacon-proxy 项目中可参考：
- `docs/TOOL_GUIDE.md` — 完整工具说明
- `docs/INTEGRATION.md` — REST API 与集成规范
