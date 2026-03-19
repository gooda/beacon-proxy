# CLI 与 REST API 操作对照

| 操作 | CLI | REST API |
|------|-----|----------|
| 添加规则 | `beacon-proxy add-rule` | `POST /api/rules` |
| 域名重写 | `beacon-proxy add-rewrite` | `POST /api/rules` |
| 删除规则 | `beacon-proxy remove-rule` | `DELETE /api/rules/{rule_id}` |
| 绑定规则到场景 | `beacon-proxy bind-rule` | `POST /api/rules/{rule_id}/bind` |
| 从场景解绑 | `beacon-proxy unbind-rule` | `DELETE /api/rules/{rule_id}/bind/{scenario_id}` |
| 列出定义 | `beacon-proxy list-definitions` | `GET /api/rules/definitions` |
| 列出规则 | `beacon-proxy list-rules` | `GET /api/rules?scenario_id=` |
| 激活场景 | — | `POST /api/activate` |
| 取消激活 | — | `DELETE /api/activate/{scenario_id}` 或 `DELETE /api/activate/ip/{client_ip}` |
| 列出激活 | — | `GET /api/activate` |
| 根据需求生成规则 | — | `POST /api/generate` |

## 详细示例

### 添加规则
```bash
# CLI
beacon-proxy add-rule "/api/login" --status 500 --body '{"error":"server_error"}' -d scenario_A

# REST
curl -X POST http://127.0.0.1:8765/api/rules \
  -H "Content-Type: application/json" \
  -d '{"url_pattern":"/api/login","status_code":500,"body":"{\"error\":\"server_error\"}","scenario_id":"scenario_A"}'
```

### 域名重写
```bash
# CLI
beacon-proxy add-rewrite api.prod.example.com api.staging.example.com -d scenario_A
```

### 删除规则
```bash
# CLI
beacon-proxy remove-rule rule_1 -d scenario_A   # 仅解绑场景
beacon-proxy remove-rule rule_1                 # 删除定义

# REST
curl -X DELETE "http://127.0.0.1:8765/api/rules/rule_1?scenario_id=scenario_A"
```

### 激活场景
```bash
curl -X POST http://127.0.0.1:8765/api/activate \
  -H "Content-Type: application/json" \
  -d '{"scenario_id":"scenario_A","client_ip":"192.168.1.101"}'
```

### 根据需求生成规则
```bash
curl -X POST http://127.0.0.1:8765/api/generate \
  -H "Content-Type: application/json" \
  -d '{"requirement":"登录失败","scenario_id":"default","client_ip":"192.168.1.101"}'
```

## 规则路径

- 默认：`LLM_PROXY_RULES=rules.yaml` 或 `rules`
- CLI 指定：`beacon-proxy add-rule ... --rules rules`
- API 使用环境变量，需在启动服务前设置
