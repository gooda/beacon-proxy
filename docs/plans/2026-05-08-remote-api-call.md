# Beacon Proxy 远端 API 调用能力 · 计划方案

> 日期：2026-05-08
> 状态：草案 v2（待评审）

## 一、需求概述

测试用例执行时，测试脚本向代理服务发起"执行某个远端调用"的指令（如"重置登录状态"、"初始化测试数据"），代理服务按预配置发起出站 HTTP 请求并返回结果。

```
测试脚本 → Beacon Proxy API → 远端业务 API → ↩ 响应回传
```

**价值**：
- 远端 API 地址、参数模板、headers 集中在代理侧维护，测试脚本只管 id
- 跨环境切换时改代理配置，不改脚本
- 统一的调用历史、可观测性

## 二、定位

| | rules | network_condition | **remote_calls（新）** |
|---|---|---|---|
| 管理形式 | definitions + scenario | 按 IP 绑定 | **definitions，不需激活** |
| 触发方式 | 流量拦截时自动触发 | IP 绑定后自动生效 | **按 id 主动触发** |
| 代码位置 | mitmproxy addon | mitmproxy addon | FastAPI endpoint（不碰流量路径） |

与 rules / network_condition **独立管理、独立调用**，但在编辑器 UI 与后台接口保持对齐风格。

## 三、数据模型

```python
class RemoteApiCall(BaseModel):
    id: str
    description: Optional[str]
    method: Literal["GET","POST","PUT","DELETE","PATCH"]
    url: str                                # 支持 {{var}} 模板
    headers: Optional[Dict[str, str]]       # value 支持 {{var}}
    query_params: Optional[Dict[str, str]]  # value 支持 {{var}}
    body: Optional[Union[str, Dict]]
    body_type: Literal["json","text","form"] = "json"
    timeout_ms: int = 10000


class RemoteCallResult(BaseModel):
    ok: bool
    call_id: str
    status: Literal["pending","success","failed"]  # async 用
    status_code: Optional[int]
    headers: Optional[Dict[str, str]]
    body: Optional[Any]
    error: Optional[str]              # "upstream_timeout"|"network_error"|"template_error"|...
    error_detail: Optional[str]
    duration_ms: Optional[int]
    request_url: Optional[str]
    started_at: Optional[str]         # ISO8601
```

## 四、设备上下文变量（设计亮点）

模板渲染时，除了调用方传入的 `variables`，还可引用"发起 invoke 的设备上下文"——解决测试脚本不想手动抓 token/header 的痛点。

| 变量 | 含义 | 来源 |
|---|---|---|
| `{{device.client_ip}}` | 设备 IP | invoke body 的 `client_ip`，或 HTTP 源 IP |
| `{{device.scenario_id}}` | 当前激活的 scenario | `activations.yaml` |
| `{{device.last_request.path}}` | 最近一次被代理的请求 path | `recorded_requests` 按 IP 过滤 |
| `{{device.last_request.headers.<name>}}` | 最近一次请求的 header | 同上 |
| `{{device.last_request.query.<name>}}` | 最近一次请求的 query | 同上 |

**示例**：
```yaml
id: reset_login
method: POST
url: https://api-test.example.com/user/reset
headers:
  Authorization: "{{device.last_request.headers.authorization}}"
  X-Client-IP: "{{device.client_ip}}"
body:
  reason: automation
```

**前置**：当前 `record_request`（`addon.py:75`）仅存 `url/method/path/scenario_id`，**需扩展为同时存 `client_ip` 和 `headers/query`**，并在 manager 增加 `get_last_request_for_ip`。

## 五、文件结构

```
rules/
├── definitions/                 # 现有
├── scenarios/                   # 现有
├── activations.yaml             # 现有
└── remote_calls/                # 新增
    ├── reset_login.yaml
    └── seed_orders.yaml
```

`remote_calls/reset_login.yaml` 示例：
```yaml
id: reset_login
description: 重置用户登录状态
method: POST
url: https://api-test.example.com/user/{{user_id}}/reset
headers:
  X-Trace: "{{trace_id}}"
body:
  reason: automation
body_type: json
timeout_ms: 10000
```

## 六、REST API

### 6.1 定义 CRUD

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/remote-calls` | 列出所有定义 |
| GET | `/api/remote-calls/{id}` | 查询单个定义 |
| POST | `/api/remote-calls` | 新增定义 |
| PUT | `/api/remote-calls/{id}` | 更新定义 |
| DELETE | `/api/remote-calls/{id}` | 删除定义 |

### 6.2 触发调用

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/remote-calls/{id}/invoke?mode=sync\|async` | 按 id 触发，默认 sync |
| POST | `/api/remote-calls/invoke?mode=sync\|async` | 一次性调用（body 内含完整定义） |
| GET | `/api/remote-calls/calls/{call_id}` | 查询调用结果（async 必用） |
| GET | `/api/remote-calls/calls?limit=N` | 最近 N 条调用记录 |

**invoke 请求 body**：
```json
{
  "variables": { "user_id": "12345", "trace_id": "abc" },
  "client_ip": "192.168.1.101",
  "timeout_ms": 5000
}
```

**sync 响应（成功）**：
```json
{
  "ok": true,
  "call_id": "rc_ab12cd34",
  "status": "success",
  "status_code": 200,
  "headers": {...},
  "body": {...},
  "duration_ms": 432,
  "request_url": "https://api-test.example.com/user/12345/reset"
}
```

**sync 响应（远端 5xx / 超时 / 网络错误，HTTP 层始终 200）**：
```json
{
  "ok": false,
  "call_id": "rc_ab12cd34",
  "status": "failed",
  "status_code": 504,
  "error": "upstream_timeout",
  "error_detail": "Read timeout after 5000ms",
  "duration_ms": 5001
}
```

> 沿用现有 Activate/NetworkCondition 接口风格：HTTP 层总是 200，业务语义靠 `ok`/`error` 字段承载；只有参数非法、定义不存在时返回 4xx。

**async 响应（立即返回）**：
```json
{ "ok": true, "call_id": "rc_ab12cd34", "status": "pending" }
```
随后 `GET /api/remote-calls/calls/{call_id}` 轮询，状态 `pending → success/failed`。

## 七、关键设计决策（已确认）

| 项 | 决策 |
|---|---|
| 同步 / 异步 | **都支持**，`?mode=async` 切换，默认同步 |
| 模板语法 | `{{var}}`（Mustache 风格，避开 YAML/shell 扩展冲突） |
| 鉴权 | 本期**不做**，通过设备上下文变量（4 节）复用已有 header |
| 错误透传 | HTTP 200 + `ok:false` + `error/error_detail` 字段 |
| 重试 | 不做 |
| SSL 校验 | 不提供关闭开关 |
| 日志 | 内存环形 buffer，**100 条 / 10 分钟 TTL**，不持久化 |
| 编辑器 UI | `/rules` 页面新增独立「远端调用」tab |
| HTTP 客户端 | `httpx`（异步、超时、统一 API） |

## 八、代码改动

| 文件 | 改动 |
|---|---|
| `models.py` | 新增 `RemoteApiCall`, `RemoteCallResult` |
| `src/llm_proxy/remote_call.py` | **新增**：HTTP 执行器、`{{var}}` 模板渲染（含 device 上下文）、环形 buffer、async 任务池 |
| `manager/base.py` | 协议追加 `list/get/save/delete_remote_call`、`get_last_request_for_ip` |
| `manager/file_based.py` | 实现 remote_calls 目录 CRUD；`record_request` 带 `client_ip/headers/query`；`get_last_request_for_ip` |
| `addon.py` | `record_request` 调用时新增 `client_ip` + 过滤的 headers/query（参考 `_get_client_ip`） |
| `api_server.py` | 新增 9 个 endpoint（CRUD 5 + invoke 2 + calls 2） |
| `static/editor.html` | 新增「远端调用」tab（列表 / 编辑 / 触发测试按钮） |
| `pyproject.toml` | 依赖追加 `httpx` |

## 九、实现分阶段

| 阶段 | 内容 | 验收 |
|---|---|---|
| P0 | 模型 + `remote_calls/` 目录读写 + CRUD 5 接口 + **sync invoke（无模板）** | curl 能 CRUD、能触发一次固定 URL 调用 |
| P1 | `{{var}}` 模板渲染 + `variables` 注入 | 模板化 URL/headers/body 可用 |
| P2 | 扩展 `record_request` → `client_ip/headers/query` + `get_last_request_for_ip` + **device 上下文变量** | 示例 `reset_login.yaml` 能从设备最近请求自动取 auth header |
| P3 | async 模式 + `call_id` 查询 + 内存 ring buffer + `GET /calls` 列表 | async 调用可轮询结果，最近调用可查 |
| P4 | 编辑器 tab UI（列表、表单、"立即触发"按钮） | 浏览器可完整操作 |

## 十、安全与边界

- **URL 范围**：不加白名单（测试场景可信），但响应体大小限制 1MB 防撑爆内存
- **并发**：async 任务池加上限（默认 50 个 pending），超过拒绝新请求
- **模板注入**：渲染时对未解析变量保留 `{{var}}` 原样并在 `error_detail` 提示（严格模式可选）
- **call_id 格式**：`rc_` + 8 位 hex，内存唯一

---

## 附：验收 DEMO 流程

```bash
# 1. 注册定义
curl -X POST http://proxy:8765/api/remote-calls -H 'Content-Type: application/json' -d '{
  "id":"reset_login","method":"POST",
  "url":"https://api-test.example.com/user/{{user_id}}/reset"
}'

# 2. 测试脚本触发（同步）
curl -X POST http://proxy:8765/api/remote-calls/reset_login/invoke \
  -H 'Content-Type: application/json' \
  -d '{"variables":{"user_id":"12345"}}'

# 3. 异步触发 + 查询
CALL_ID=$(curl -sX POST 'http://proxy:8765/api/remote-calls/reset_login/invoke?mode=async' \
  -d '{"variables":{"user_id":"12345"}}' | jq -r .call_id)
curl http://proxy:8765/api/remote-calls/calls/$CALL_ID
```
