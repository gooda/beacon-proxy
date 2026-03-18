# Beacon Proxy 规则编辑器 - 计划方案

## 一、当前代理功能总结

### 1.1 核心能力

| 能力 | 说明 | 规则字段 |
|------|------|----------|
| **响应 Mock** | 匹配 URL 后改写响应状态码、响应体 | url_pattern, status_code, body |
| **域名重写** | 将 A 域名请求转发到 B 域名 | url_pattern, upstream_host, upstream_port |
| **场景激活** | 按 IP 绑定场景规则，APP/模拟器场景 | scenario_id, client_ip, rule_ids |
| **规则复用** | definitions 定义 + scenarios 引用 | rule_ids, overrides |

### 1.2 数据模型

**InterceptRule**：
- `id`：规则 ID
- `url_pattern`：URL 匹配（子串或正则）
- `description`：描述
- `status_code`：改写状态码（Mock 用）
- `body`：改写响应体（Mock 用）
- `use_regex`：url_pattern 是否正则
- `upstream_host`：目标域名（域名重写用）
- `upstream_port`：目标端口（域名重写用）

**规则类型**：
1. **Mock 规则**：status_code 或 body 非空
2. **域名重写规则**：upstream_host 非空

### 1.3 现有入口

- **CLI**：add-rule, add-rewrite, remove-rule, list-rules, bind-rule, activate
- **MCP**：add_rule, add_domain_rewrite, remove_rule, list_rules, activate
- **REST API**：/api/activate, /api/generate（无规则 CRUD）

---

## 二、规则编辑器方案

### 2.1 技术选型

| 选项 | 说明 |
|------|------|
| **单页 HTML + 原生 JS** | 无构建、与 API 同源、易部署 |
| **Vue/React SPA** | 交互丰富，需构建 |

**推荐**：单页 HTML + 原生 JS，内嵌于 FastAPI 静态路由，与证书页一致。

### 2.2 界面布局

```
┌─────────────────────────────────────────────────────────────────────────┐
│  Beacon Proxy 规则编辑器                                    [刷新] [帮助] │
├──────────────┬────────────────────────────────┬──────────────────────────┤
│  场景列表    │  规则列表（当前场景）           │  规则编辑 / 新增          │
│              │                                │                          │
│  ○ scenario_A│  id          url_pattern 操作  │  [Mock 响应] [域名重写]   │
│  ● scenario_B│  login_500   /api/login   ✎ ✕  │  ─────────────────────   │
│  ○ default   │  api_rewrite api.prod...  ✎ ✕  │  URL 匹配: [____________] │
│              │                                │  描述:     [____________] │
│  [+ 新场景]  │  [+ 添加规则]                  │  状态码:   [500____]      │
│              │                                │  响应体:   [____________] │
│              │                                │  或 目标域名: [__________] │
│              │                                │  目标端口: [443___]       │
│              │                                │  [保存] [取消]            │
├──────────────┴────────────────────────────────┴──────────────────────────┤
│  激活状态                                                                  │
│  IP 192.168.1.101 → scenario_A [login_500]     [取消激活]                    │
│  IP 10.0.0.5     → scenario_B [api_rewrite]    [取消激活]                     │
│  [+ 激活场景]                                                               │
└────────────────────────────────────────────────────────────────────────────┘
```

### 2.3 区域说明

| 区域 | 功能 |
|------|------|
| **场景列表** | 切换场景、查看该场景绑定的规则、新建场景 |
| **规则列表** | 展示当前场景的规则，支持编辑、删除、排序 |
| **规则编辑** | 新增/编辑规则，Tab 切换 Mock / 域名重写 模式 |
| **激活状态** | 展示 IP↔场景绑定，支持激活、取消激活 |

### 2.4 交互流程

#### 2.4.1 添加 Mock 规则

1. 选择场景
2. 点击「添加规则」
3. 选择「Mock 响应」
4. 填写：URL 匹配、状态码、响应体（可选）
5. 保存 → 调用 API 写入 definitions 并 bind 到场景

#### 2.4.2 添加域名重写规则

1. 选择场景
2. 点击「添加规则」
3. 选择「域名重写」
4. 填写：源域名（URL 匹配）、目标域名、目标端口
5. 保存

#### 2.4.3 编辑规则

1. 在规则列表点击「编辑」
2. 右侧表单加载规则数据
3. 修改后保存 → 更新 definition 文件

#### 2.4.4 删除规则

1. 点击「删除」
2. 确认 → 从 definitions 删除并 unbind 所有场景

#### 2.4.5 激活设备

1. 点击「激活设备」
2. 输入 scenario_id、client_ip，可选 rule_ids 覆盖
3. 保存 → POST /api/activate

#### 2.4.6 取消激活

1. 在激活列表中点击「取消激活」
2. 调用 DELETE /api/activate/ip/{client_ip}

### 2.5 需新增的 API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/rules/definitions | 列出所有规则定义 |
| GET | /api/rules?scenario_id=X | 列出某场景的规则 |
| POST | /api/rules | 新增规则（含 scenario_id 则 bind） |
| PUT | /api/rules/{id} | 更新规则 |
| DELETE | /api/rules/{id} | 删除规则 |
| POST | /api/rules/{id}/bind | 绑定规则到场景 |
| DELETE | /api/rules/{id}/bind/{scenario_id} | 从场景解绑 |

### 2.6 页面路由

- `/rules` 或 `/editor`：规则编辑器单页
- 与 `/certificate` 同级，由 FastAPI 提供 HTML 响应

### 2.7 文件结构

```
src/llm_proxy/
├── api_server.py      # 新增 rules API + 编辑器路由
├── static/            # 可选：若后续拆分
│   └── editor.html
```

或直接在 api_server 中 `@app.get("/rules", response_class=HTMLResponse)` 返回内联 HTML。

---

## 三、实现优先级

| 阶段 | 内容 | 状态 |
|------|------|------|
| P0 | 新增 rules CRUD API | ✓ |
| P1 | 规则编辑器 HTML 页面（列表 + 表单） | ✓ |
| P2 | 场景切换、激活区域 | ✓ |
| P3 | 编辑、删除确认、错误提示优化 | ✓ |

访问 `http://<API>:8765/rules` 或 `/editor` 使用规则编辑器。
