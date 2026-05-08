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
| 激活场景 | `beacon-proxy activate <scenario> <ip> [--rule-ids ...]` | `POST /api/activate` |
| 取消激活 | `beacon-proxy deactivate --scenario\|--ip\|--all` | `DELETE /api/activate/*` |
| 列出激活 | `beacon-proxy list-activations` | `GET /api/activate` |
| 根据需求生成规则 | `beacon-proxy generate <requirement> --ip <ip> [--scenario <id>]` | `POST /api/generate` |
| 设置网络条件 | `beacon-proxy set-net-condition <ip> --preset 3g\|4g\|airplane\|latency` | `POST /api/network-condition` |
| 查看网络条件 | `beacon-proxy list-net-conditions` | `GET /api/network-condition` |
| 查看某 IP 条件 | — | `GET /api/network-condition/{client_ip}` |
| 清除某 IP 条件 | `beacon-proxy clear-net-condition --ip <ip>` | `DELETE /api/network-condition/{client_ip}` |
| 清除所有条件 | `beacon-proxy clear-net-condition --all` | `DELETE /api/network-condition` |
| 列出远端调用定义 | `beacon-proxy remote-call list` | `GET /api/remote-calls` |
| 新增远端调用定义 | `beacon-proxy remote-call add <id> -u <url> [-X M] [-H K=V]...` | `POST /api/remote-calls` |
| 更新远端调用定义 | `beacon-proxy remote-call update <id> [...]` | `PUT /api/remote-calls/{id}` |
| 删除远端调用定义 | `beacon-proxy remote-call delete <id>` | `DELETE /api/remote-calls/{id}` |
| 触发远端调用（按 id） | `beacon-proxy remote-call invoke <id> [--var K=V]... [--async]` | `POST /api/remote-calls/{id}/invoke?mode=sync\|async` |
| 一次性触发远端调用 | — | `POST /api/remote-calls/invoke?mode=sync\|async` |
| 查询单次调用结果 | `beacon-proxy remote-call get-call <call_id>` | `GET /api/remote-calls/calls/{call_id}` |
| 最近调用列表 | `beacon-proxy remote-call calls [-n N]` | `GET /api/remote-calls/calls?limit=N` |

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

### 添加带网络模拟的规则
```bash
# 给特定接口加 3 秒延迟
curl -X POST http://127.0.0.1:8765/api/rules \
  -H "Content-Type: application/json" \
  -d '{"url_pattern":"/api/login","delay_ms":3000,"scenario_id":"scenario_A"}'

# 给特定接口加限速 + 丢包
curl -X POST http://127.0.0.1:8765/api/rules \
  -H "Content-Type: application/json" \
  -d '{"url_pattern":"/api/upload","throttle_kbps":50,"packet_loss_rate":0.1,"scenario_id":"scenario_A"}'
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

### 网络模拟

#### 设置飞行模式
```bash
curl -X POST http://127.0.0.1:8765/api/network-condition \
  -H "Content-Type: application/json" \
  -d '{"client_ip":"192.168.1.101","airplane_mode":true}'
```

#### 设置弱网 3G
```bash
curl -X POST http://127.0.0.1:8765/api/network-condition \
  -H "Content-Type: application/json" \
  -d '{"client_ip":"192.168.1.101","delay_ms":400,"throttle_kbps":50,"packet_loss_rate":0.02}'
```

#### 查看所有网络条件
```bash
curl http://127.0.0.1:8765/api/network-condition
```

### 远端调用（出站 API 编排）

#### 注册调用定义（URL/headers 支持 {{var}} 模板）
```bash
curl -X POST http://127.0.0.1:8765/api/remote-calls \
  -H "Content-Type: application/json" \
  -d '{
    "id": "reset_login",
    "description": "重置用户登录状态",
    "method": "POST",
    "url": "https://api-test.example.com/user/{{user_id}}/reset",
    "headers": {"Authorization": "{{device.last_request.headers.authorization}}"}
  }'
```

#### 同步触发（阻塞返回结果）
```bash
curl -X POST http://127.0.0.1:8765/api/remote-calls/reset_login/invoke \
  -H "Content-Type: application/json" \
  -d '{"variables":{"user_id":"12345"},"client_ip":"192.168.1.101"}'
```

#### 异步触发 + 查询
```bash
# 立即返回 call_id
CALL_ID=$(curl -sX POST 'http://127.0.0.1:8765/api/remote-calls/reset_login/invoke?mode=async' \
  -H "Content-Type: application/json" \
  -d '{"variables":{"user_id":"12345"}}' | jq -r .call_id)

# 轮询结果（状态：pending → success | failed）
curl http://127.0.0.1:8765/api/remote-calls/calls/$CALL_ID
```

#### 一次性调用（不落库）
```bash
curl -X POST http://127.0.0.1:8765/api/remote-calls/invoke \
  -H "Content-Type: application/json" \
  -d '{"id":"once","method":"GET","url":"https://api/health"}'
```

#### 查看最近调用
```bash
curl 'http://127.0.0.1:8765/api/remote-calls/calls?limit=20'
```

**模板变量**：
- `{{caller_var}}` — invoke body 的 `variables` 注入
- `{{device.client_ip}}` — 设备 IP（body.client_ip 优先，否则 HTTP 源 IP）
- `{{device.scenario_id}}` — 该 IP 当前激活的 scenario
- `{{device.last_request.path|method|url}}` — 该 IP 最近一次被代理的请求
- `{{device.last_request.headers.<name>}}` / `{{device.last_request.query.<name>}}` — 最近请求的 header / query

**错误透传**：远端 5xx / 超时 / 网络错误时 HTTP 层始终返回 200，业务语义看 `ok` / `error` / `error_detail` 字段。

#### 清除某设备网络条件
```bash
curl -X DELETE http://127.0.0.1:8765/api/network-condition/192.168.1.101
```

### NetworkCondition 请求体字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `client_ip` | string | 必填，客户端 IP |
| `airplane_mode` | bool | 飞行模式，默认 false |
| `delay_ms` | int | 全局延迟(ms)，0-60000 |
| `throttle_kbps` | int | 全局限速(KB/s)，0-102400 |
| `packet_loss_rate` | float | 全局丢包率，0.0-1.0 |

### InterceptRule 网络模拟字段（可选）

| 字段 | 类型 | 说明 |
|------|------|------|
| `delay_ms` | int | 该 URL 的延迟(ms) |
| `throttle_kbps` | int | 该 URL 的限速(KB/s) |
| `packet_loss_rate` | float | 该 URL 的丢包率 |

> 规则级别的网络模拟会覆盖设备级别的值（非叠加）。

## 规则路径

- 默认：`LLM_PROXY_RULES=rules.yaml` 或 `rules`
- CLI 指定：`beacon-proxy add-rule ... --rules rules`
- API 使用环境变量，需在启动服务前设置
