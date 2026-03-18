# 测试报告：device → scenario 定义调整（去掉 device 兼容后）

**测试日期**：2025-03-16  
**变更范围**：IP 映射由「设备名称」改为「场景名称」，已移除旧格式兼容

---

## 1. 测试概要

| 项目 | 结果 |
|------|------|
| 测试文件 | `tests/test_scenario_mapping.py` |
| 用例数 | 5 |
| 通过 | 5 |
| 失败 | 0 |
| 执行时间 | ~1s |

---

## 2. 用例明细

### 2.1 IP → scenario 映射

| 检查项 | 预期 | 结果 |
|--------|------|------|
| `get_scenario_id_by_client_ip("192.168.1.101")` | 返回 `scenario_A` | ✓ |
| `get_intercept_rules_for_client("192.168.1.101")` | 返回含 `login_500` 的规则列表 | ✓ |
| 未激活 IP `10.0.0.99` | 返回空列表 | ✓ |
| `activate("scenario_A", "10.0.0.5", ...)` 后查询 | IP 映射到 `scenario_A` | ✓ |
| `list_activations()` | 包含 `ip_to_scenario` 字段 | ✓ |
| `deactivate(client_ip="10.0.0.5")` | 取消后该 IP 无映射 | ✓ |

### 2.2 API Schema

| 检查项 | 预期 | 结果 |
|--------|------|------|
| `ActivateRequest(scenario_id=..., client_ip=...)` | 接受 `scenario_id` 字段 | ✓ |
| `GenerateRequest(..., scenario_id=..., client_ip=...)` | 接受 `scenario_id` 字段 | ✓ |

### 2.3 旧格式已不再支持

| 检查项 | 预期 | 结果 |
|--------|------|------|
| activations 仅含 `ip_to_device` 时 | `get_scenario_id_by_client_ip` 返回 `None` | ✓ |

### 2.4 项目 rules/ 目录

| 检查项 | 预期 | 结果 |
|--------|------|------|
| 加载 `rules/` | `list_activations` 含 `ip_to_scenario`、`scenario_rule_overrides` | ✓ |
| 有激活时按 IP 取规则 | 正常返回 | ✓ |

### 2.5 API activate 流程

| 检查项 | 预期 | 结果 |
|--------|------|------|
| `activate()` 写入 activations | 使用 `ip_to_scenario`、`scenario_rule_overrides`，不含 device 字段 | ✓ |
| 激活后 `get_intercept_rules_for_client` | 返回对应规则 | ✓ |

---

## 3. 结论

**全部自测通过**。去掉 device 兼容后，scenario 规则全部支持，旧格式 `ip_to_device` / `device_rule_overrides` 已不再生效。
