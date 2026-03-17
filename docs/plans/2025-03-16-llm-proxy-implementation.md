# 大模型调用代理服务 - 实现计划

> **Goal:** 基于 mitmproxy 实现代理服务，支持 CLI + MCP 调用，用于 UI 自动化测试中的请求拦截与改写。

**Architecture:** 代理核心为 mitmproxy addon，依赖 ManagementInterface 获取拦截规则；规则以 YAML 文件存储；CLI 与 MCP 通过共享规则文件与 Manager 交互。

**Tech Stack:** Python 3.10+, mitmproxy, Pydantic, Typer (CLI), MCP SDK

---

## Task 1: 项目初始化

**Files:** Create `pyproject.toml`, `src/llm_proxy/__init__.py`

**Step 1:** 创建 pyproject.toml，依赖 mitmproxy、pydantic、typer、pyyaml

**Step 2:** 创建 src 目录结构

---

## Task 2: 数据模型

**Files:** Create `src/llm_proxy/models.py`

**Step 1:** 定义 InterceptRule（url_pattern, status_code?, body?）、ProxyConfig、ProxyState

---

## Task 3: ManagementInterface 与 FileBasedManager

**Files:** Create `src/llm_proxy/manager/base.py`, `src/llm_proxy/manager/file_based.py`

**Step 1:** 定义 ManagementInterface 协议

**Step 2:** 实现 FileBasedManager，从 YAML 加载/保存规则

---

## Task 4: mitmproxy Addon

**Files:** Create `src/llm_proxy/addon.py`

**Step 1:** 实现 LLMProxyAddon，在 response 阶段根据规则改写 status_code 与 content

---

## Task 5: CLI

**Files:** Create `src/llm_proxy/cli.py`

**Step 1:** 实现 add-rule、remove-rule、list-rules、start 等命令

---

## Task 6: MCP 服务

**Files:** Create `src/llm_proxy/mcp_server.py`

**Step 1:** 实现 MCP 工具：add_rule、remove_rule、list_rules、get_requests

---

## Task 7: 入口与配置

**Files:** Create `config/default.yaml`, Modify `pyproject.toml` (scripts)

**Step 1:** 默认 rules 配置、CLI 入口

---

## 实现完成

- 项目已实现，使用 `pip install -e .` 安装后可通过 `beacon-proxy` 命令使用
- 或使用 `PYTHONPATH=src python -m llm_proxy.cli` 直接运行
