# Beacon Proxy AI Coding 使用指南

面向 AI 辅助编程（Cursor、Copilot 等）场景的代理工具使用指南。AI 通过 **Skills** 使用 CLI 或 REST API 配置代理。

---

## 1. 核心价值

在 AI 辅助开发中，Beacon Proxy 让大模型能够：

- **动态注入 mock**：无需改代码，通过规则即可模拟接口异常、空数据等
- **快速验证边界**：登录失败、网络超时、空列表等场景一键切换
- **网络模拟**：弱网（延迟/限速/丢包）、飞行模式，按设备或接口级别设置
- **与 Skills 联动**：AI 依据 skill 使用 CLI/REST API 添加/激活规则，实现「对话式调试」

---

## 2. 典型应用场景

### 2.1 场景一：编写「登录失败」用例

**需求**：为登录页编写「服务异常时显示错误提示」的 E2E 用例。

**AI 工作流**：

1. 用户：帮我写一个登录失败时显示错误提示的测试用例
2. AI 分析：需要 mock `/api/login` 返回 500
3. AI 调用 CLI：`beacon-proxy add-rule "/api/login" --id login_500 --status 500 --body '{"code":500,"message":"Internal Server Error"}'`
4. AI 生成测试代码（Playwright/Puppeteer），配置代理 `127.0.0.1:8080`
5. 运行用例，验证前端正确展示错误信息

---

### 2.2 场景二：调试「空购物车」UI

**需求**：开发购物车空状态展示，需要 mock 接口返回空列表。

**AI 工作流**：

1. 用户：帮我 mock 购物车接口返回空数组
2. AI 调用 CLI：`beacon-proxy add-rule "/api/cart" --id cart_empty --status 200 --body '{"items":[],"total":0}'`
3. 用户刷新页面（通过代理），即可看到空购物车 UI
4. 调试完成后，AI 可调用 `beacon-proxy remove-rule cart_empty` 清理

---

### 2.3 场景三：多设备并行测试（APP）

**需求**：两台模拟器同时跑用例，设备 A 模拟登录失败，设备 B 模拟正常。

**AI 工作流**：

1. 用户：设备 A (192.168.1.101) 要登录失败，设备 B (192.168.1.102) 正常
2. AI 调用 REST API 或 CLI：`curl -X POST http://127.0.0.1:8765/api/activate -H "Content-Type: application/json" -d '{"scenario_id":"scenario_A","client_ip":"192.168.1.101","rule_ids":["login_500"]}'`
3. 设备 A 的流量经代理时自动应用 `login_500`，设备 B 透传
4. 用例结束后调用 `curl -X DELETE http://127.0.0.1:8765/api/activate/ip/192.168.1.101` 清理

---

### 2.4 场景四：TDD 驱动开发

**需求**：先定义「接口返回 404 时前端展示」的预期，再实现逻辑。

**AI 工作流**：

1. 用户：我要 TDD 开发「资源不存在时显示 404 页」功能
2. AI 建议：先添加 mock 规则，再写用例
3. AI 调用 CLI：`beacon-proxy add-rule "/api/resource/123" --status 404`
4. AI 生成测试：断言页面显示「资源不存在」
5. 用户实现前端逻辑，运行用例验证

---

### 2.5 场景五：弱网 / 飞行模式测试

**需求**：验证 APP 在弱网或断网条件下的表现。

**AI 工作流**：

1. 用户：设备 192.168.1.101 模拟弱网 3G
2. AI 调用 REST API：`curl -X POST http://127.0.0.1:8765/api/network-condition -d '{"client_ip":"192.168.1.101","delay_ms":400,"throttle_kbps":50,"packet_loss_rate":0.02}'`
3. 用户执行用例，验证 APP 弱网表现（加载动画、超时提示等）
4. 用户：切换为飞行模式
5. AI 调用：`curl -X POST http://127.0.0.1:8765/api/network-condition -d '{"client_ip":"192.168.1.101","airplane_mode":true}'`
6. 验证 APP 断网处理（离线提示、缓存展示等）
7. 测试完成：`curl -X DELETE http://127.0.0.1:8765/api/network-condition/192.168.1.101`

也可通过 generate API 一步完成：`POST /api/generate -d '{"requirement":"弱网3G","client_ip":"192.168.1.101"}'`

---

### 2.6 场景六：对话式切换 mock 场景

**需求**：在对话中快速切换不同 mock 组合，观察 UI 变化。

**AI 工作流**：

1. 用户：切换到「登录成功 + 空购物车」
2. AI 调用 `add_rule` 或 REST API `activate` 指定 rule_ids
3. 用户刷新页面即可看到新场景
4. 用户：再切换到「登录失败」
5. AI 调用 `remove_rule` 移除 cart_empty，或 `activate` 仅含 login_500

---

## 3. Skills 与 AI 协作

### 3.1 Skills 说明

项目内 `skills/beacon-proxy/SKILL.md` 提供 CLI/REST API 的完整对照。AI 依据该 skill 使用 CLI 或 REST API 完成规则配置。详见 `skills/beacon-proxy/reference/tools-reference.md`。

### 3.2 操作对照表

| 操作 | CLI | REST API |
|------|-----|----------|
| 添加规则 | `beacon-proxy add-rule` | `POST /api/rules` |
| 域名重写 | `beacon-proxy add-rewrite` | `POST /api/rules` |
| 删除规则 | `beacon-proxy remove-rule` | `DELETE /api/rules/{id}` |
| 激活场景 | — | `POST /api/activate` |
| 设置网络条件 | — | `POST /api/network-condition` |
| 清除网络条件 | — | `DELETE /api/network-condition/{ip}` |
| 生成规则/网络条件 | — | `POST /api/generate` |

### 3.3 与 AI 的协作提示词

在对话中可这样引导 AI 使用代理：

- 「登录失败，设备 192.168.1.101」（调用 `generate_from_requirement` 一步完成）
- 「将 api.prod.example.com 代理到 api.staging.example.com」（调用 `add_domain_rewrite`）
- 「用 Beacon Proxy mock 一下 /api/user 返回 401」
- 「帮我添加一个规则：/api/orders 返回空数组，状态码 200」
- 「设备 192.168.1.101 需要应用 login_500 规则，请激活」
- 「列出当前所有 mock 规则」
- 「设备 192.168.1.101 模拟弱网 3G」（设置网络条件）
- 「设备 192.168.1.101 飞行模式」（设置飞行模式）
- 「清除 192.168.1.101 的网络条件」

---

## 4. 快速启动清单

### 4.1 本地开发（单机）

```bash
# 1. 安装
pip install -e .

# 2. 启动代理 + API
beacon-proxy start --with-api --port 8080 --api-port 8765

# 3. 配置被测应用使用代理 127.0.0.1:8080
```

### 4.2 浏览器 / Playwright

```javascript
// Playwright 配置代理并注入 X-Scenario-ID
const browser = await chromium.launch({
  proxy: { server: 'http://127.0.0.1:8080' }
});
const context = await browser.newContext({
  extraHTTPHeaders: { 'X-Scenario-ID': 'scenario_A' }
});
```

### 4.3 APP / 模拟器

```bash
# 用例前：激活设备
curl -X POST http://127.0.0.1:8765/api/activate \
  -H "Content-Type: application/json" \
  -d '{"scenario_id":"scenario_A","client_ip":"<模拟器IP>"}'

# 配置模拟器 HTTP 代理为 宿主机IP:8080

# 用例后：取消激活（可选）
curl -X DELETE http://127.0.0.1:8765/api/activate/ip/<模拟器IP>
```

---

## 5. 规则设计建议

### 5.1 命名约定

| 规则 ID | 含义 | 示例 |
|---------|------|------|
| `{接口}_500` | 模拟服务异常 | `login_500` |
| `{接口}_401` | 模拟未授权 | `user_401` |
| `{接口}_empty` | 模拟空数据 | `cart_empty` |
| `{接口}_404` | 模拟资源不存在 | `order_404` |

### 5.2 常用 mock 模板

```yaml
# 登录失败
- id: login_500
  url_pattern: /api/login
  status_code: 500
  body: '{"code":500,"message":"Internal Server Error"}'

# 未登录
- id: auth_401
  url_pattern: /api/user
  status_code: 401
  body: '{"code":401,"message":"Unauthorized"}'

# 空列表
- id: list_empty
  url_pattern: /api/items
  status_code: 200
  body: '{"items":[],"total":0}'
```

---

## 6. 与 AI 协作的最佳实践

1. **先启动代理**：在请求 AI 添加规则前，确保 `beacon-proxy start` 已运行
2. **明确 URL 模式**：告诉 AI 要 mock 的接口路径，如 `/api/login`、`/api/cart`
3. **用例结束清理**：临时规则用完后，可让 AI 调用 `remove_rule` 或 `deactivate`
4. **规则持久化**：常用场景可写入 `rules/definitions/*.yaml`，由 AI 通过 `add_rule` 创建
5. **多设备时用 activate**：APP 场景无法注入 Header，用 REST API `POST /api/activate` 按 IP 绑定

---

## 7. 故障排查

| 现象 | 可能原因 | 处理 |
|------|----------|------|
| 规则不生效 | 代理未启动或端口错误 | 确认 `beacon-proxy start` 且应用配置了代理 8080 |
| 激活 API 404 | API 未启动 | 使用 `--with-api` 或单独 `beacon-proxy api` |
| 多设备规则混乱 | 未按 IP 激活 | 用例前调用 `POST /api/activate` 绑定 client_ip |
| API 无响应 | 规则路径错误或 API 未启动 | 检查 `LLM_PROXY_RULES`、确认 `beacon-proxy start --with-api` |

---

## 8. 延伸阅读

- [使用规范 (INTEGRATION.md)](INTEGRATION.md) — REST API、集成模式
- [README](../README.md) — 安装、CLI、规则文件结构
