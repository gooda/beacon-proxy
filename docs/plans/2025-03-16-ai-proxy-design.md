# 大模型调用代理服务 - 设计方案

> 基于 mitmproxy 开发代理服务，支持 **CLI + MCP** 两种调用方式：CLI 负责自动化，MCP 负责交互式调试。抽象出**调用方法**与**管理**，使两者与代理核心解耦。

---

## 1. 业务场景

**UI 自动化测试**：在自动化测试中，需对被测应用的网络请求进行拦截，以控制：

- **状态码**：模拟 4xx、5xx 等异常状态
- **响应数据**：改写响应体，构造特定测试数据

被测应用配置代理后，请求经代理转发；代理在 `response` 阶段按规则改写状态码与响应内容，供测试用例验证不同场景。

---

## 2. 服务定位

**代理服务**：基于 mitmproxy 的 HTTP 代理，支持 CLI 与 MCP 两种调用入口。

```
UI 自动化测试 ──被测应用配置代理──►  代理服务 ──拦截并改写──►  目标 API
                                        ▲
                    ┌───────────────────┴───────────────────┐
                    │                                       │
             CLI（自动化）                          MCP（交互式调试）
         测试脚本、CI 调用                        大模型实时调用
```

| 入口 | 职责 | 典型场景 |
|------|------|----------|
| **CLI** | 自动化 | 测试脚本、CI 中启动代理、添加规则、查询流量 |
| **MCP** | 交互式调试 | 人 + AI 设计/调试用例时，大模型实时配置规则、查看请求 |

- 被测应用：配置 HTTP 代理，请求经代理转发
- 代理服务：拦截请求/响应，按规则改写状态码与响应数据

---

## 3. 核心抽象

### 3.1 调用抽象 (Invocation)

**职责**：定义「如何调用服务」——CLI、MCP 两种入口的统一抽象。

```python
class InvocationInterface(Protocol):
    """调用入口抽象，CLI 与 MCP 实现此接口"""
    
    def handle(self, request: InvocationRequest) -> InvocationResponse:
        """处理调用请求，转发至代理核心"""
        ...
```

- 代理核心只依赖此接口，不感知具体入口（CLI / MCP）
- 实现：CLIAdapter（命令行）、MCPAdapter（MCP 服务）

### 3.2 管理抽象 (Management)

**职责**：定义「如何管理代理」——拦截规则（匹配条件、改写后的状态码与响应数据）、配置、状态等。

```python
class ManagementInterface(Protocol):
    """管理抽象，代理核心通过此接口获取拦截规则与状态"""
    
    def get_intercept_rules(self) -> list[InterceptRule]:
        """获取拦截规则：URL 匹配、改写后的 status_code、response_body"""
        ...
    
    def get_config(self) -> ProxyConfig:
        ...
    
    def get_state(self) -> ProxyState:
        ...
```

- 代理核心只依赖此接口，不感知管理实现方式
- 实现示例：文件配置、API 管理；规则通过 CLI 或 MCP 写入

---

## 4. 代理核心逻辑

代理核心（mitmproxy addon）：

- 在 `response` 阶段，从 ManagementInterface 获取拦截规则
- 若当前请求匹配某规则，则改写 `flow.response.status_code` 与 `flow.response.content`
- 仅依赖 InvocationInterface 与 ManagementInterface，不直接对接 CLI/MCP 或具体管理实现

---

## 5. 架构示意

```
         CLIAdapter              MCPAdapter
         (自动化)               (交互式调试)
              │                      │
              └──────────┬───────────┘
                         │ InvocationInterface
                         ▼
                  代理核心 (addon)
                         │
                         │ ManagementInterface
                         ▼
                    (规则、配置、状态)
```

---

## 6. 小结

| 抽象 | 作用 |
|------|------|
| **调用抽象** | 封装 CLI 与 MCP 入口，代理核心不关心从哪条路径调用 |
| **管理抽象** | 封装配置与状态来源，代理核心不关心管理实现方式 |

两者均通过接口与代理核心交互，新增调用方式或管理方式时，无需改动代理核心。
