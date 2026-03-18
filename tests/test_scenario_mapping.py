#!/usr/bin/env python3
"""自测：去掉 device 兼容后，scenario 规则是否全部支持"""

import os
import tempfile
from pathlib import Path

# 确保能导入 src
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from llm_proxy.manager.file_based import FileBasedManager
from llm_proxy.models import InterceptRule, ProxyConfig


def test_ip_to_scenario_mapping():
    """IP 映射到 scenario_id，按 IP 获取规则"""
    with tempfile.TemporaryDirectory() as tmp:
        rules_dir = Path(tmp) / "rules"
        rules_dir.mkdir()
        (rules_dir / "definitions").mkdir()
        (rules_dir / "scenarios").mkdir()

        # 定义规则
        login_500 = InterceptRule(
            id="login_500",
            url_pattern="/api/login",
            status_code=500,
            body='{"error":"server_error"}',
        )
        rules_dir.joinpath("definitions/login_500.yaml").write_text(
            "id: login_500\nurl_pattern: /api/login\nstatus_code: 500\nbody: '{\"error\":\"server_error\"}'"
        )

        # 场景配置
        (rules_dir / "scenarios").mkdir(exist_ok=True)
        (rules_dir / "scenarios/scenario_A.yaml").write_text(
            "rule_ids:\n  - login_500\noverrides: {}"
        )

        # 激活：IP -> scenario
        acts_path = rules_dir / "activations.yaml"
        acts_path.write_text("""ip_to_scenario:
  192.168.1.101: scenario_A
scenario_rule_overrides:
  scenario_A:
  - login_500
""")

        manager = FileBasedManager(str(rules_dir), ProxyConfig())

        # 1. get_scenario_id_by_client_ip：IP 应映射到 scenario_A
        sid = manager.get_scenario_id_by_client_ip("192.168.1.101")
        assert sid == "scenario_A", f"Expected scenario_A, got {sid}"

        # 2. get_intercept_rules_for_client：按 IP 获取规则
        rules = manager.get_intercept_rules_for_client("192.168.1.101")
        assert len(rules) >= 1, f"Expected >=1 rule, got {len(rules)}"
        assert any(r.id == "login_500" for r in rules), f"Expected login_500, got {[r.id for r in rules]}"

        # 3. 未激活的 IP 返回空
        rules_empty = manager.get_intercept_rules_for_client("10.0.0.99")
        assert rules_empty == [], f"Expected [], got {len(rules_empty)} rules"

        # 4. activate：新 IP 绑定 scenario
        manager.activate("scenario_A", "10.0.0.5", rule_ids=["login_500"])
        sid2 = manager.get_scenario_id_by_client_ip("10.0.0.5")
        assert sid2 == "scenario_A", f"Expected scenario_A after activate, got {sid2}"

        # 5. list_activations：应包含 ip_to_scenario
        acts = manager.list_activations()
        assert "ip_to_scenario" in acts, f"Expected ip_to_scenario, got {list(acts.keys())}"
        assert "192.168.1.101" in acts["ip_to_scenario"]
        assert acts["ip_to_scenario"]["192.168.1.101"] == "scenario_A"

        # 6. deactivate：按 scenario 或 IP 取消
        manager.deactivate(client_ip="10.0.0.5")
        assert manager.get_scenario_id_by_client_ip("10.0.0.5") is None

        print("✓ IP -> scenario 映射自测通过")


def test_api_schema():
    """API 请求体使用 scenario_id"""
    from llm_proxy.api_server import ActivateRequest, GenerateRequest

    # ActivateRequest
    req = ActivateRequest(scenario_id="scenario_A", client_ip="192.168.1.101")
    assert req.scenario_id == "scenario_A"
    d = req.model_dump() if hasattr(req, "model_dump") else req.dict()
    assert "scenario_id" in d

    # GenerateRequest
    gen = GenerateRequest(requirement="登录失败", scenario_id="scenario_A", client_ip="192.168.1.101")
    assert gen.scenario_id == "scenario_A"
    d2 = gen.model_dump() if hasattr(gen, "model_dump") else gen.dict()
    assert "scenario_id" in d2

    print("✓ API schema (scenario_id) 自测通过")


def test_old_format_rejected():
    """旧格式 ip_to_device 不再支持，应使用 ip_to_scenario"""
    with tempfile.TemporaryDirectory() as tmp:
        rules_dir = Path(tmp) / "rules"
        rules_dir.mkdir()
        (rules_dir / "definitions").mkdir()
        (rules_dir / "scenarios").mkdir()
        rules_dir.joinpath("definitions/login_500.yaml").write_text(
            "id: login_500\nurl_pattern: /api/login\nstatus_code: 500"
        )
        (rules_dir / "scenarios/scenario_A.yaml").write_text(
            "rule_ids:\n  - login_500\noverrides: {}"
        )

        # 仅含旧字段，无 ip_to_scenario
        (rules_dir / "activations.yaml").write_text("""ip_to_device:
  192.168.1.101: scenario_A
device_rule_overrides: {}
""")

        manager = FileBasedManager(str(rules_dir), ProxyConfig())
        # Pydantic 会忽略未知字段，ActivationsSchema 只有 ip_to_scenario
        # 因此 ip_to_device 不会被加载，该 IP 无映射
        sid = manager.get_scenario_id_by_client_ip("192.168.1.101")
        assert sid is None, f"旧格式应不再生效，预期 None，实际 {sid}"

        print("✓ 旧格式 ip_to_device 已不再支持")


def test_real_rules_dir():
    """使用项目 rules/ 目录验证 scenario 流程"""
    repo_root = Path(__file__).parent.parent
    rules_path = repo_root / "rules"
    if not rules_path.exists() or not (rules_path / "scenarios").exists():
        print("⊘ 跳过：rules/scenarios 不存在")
        return

    manager = FileBasedManager(str(rules_path), ProxyConfig())
    acts = manager.list_activations()

    assert "ip_to_scenario" in acts, f"activations 应含 ip_to_scenario: {list(acts.keys())}"
    assert "scenario_rule_overrides" in acts

    # 若有激活，验证按 IP 取规则
    if acts.get("ip_to_scenario"):
        ip = next(iter(acts["ip_to_scenario"]))
        sid = manager.get_scenario_id_by_client_ip(ip)
        assert sid, f"IP {ip} 应有 scenario 映射"
        rules = manager.get_intercept_rules_for_client(ip)
        assert isinstance(rules, list)

    print("✓ 项目 rules/ 目录 scenario 流程正常")


def test_api_activate_flow():
    """API activate 流程（直接调用 manager）"""
    # 不依赖 TestClient，直接验证 activate 写入的格式
    with tempfile.TemporaryDirectory() as tmp:
        rules_dir = Path(tmp) / "rules"
        rules_dir.mkdir()
        (rules_dir / "definitions").mkdir()
        (rules_dir / "scenarios").mkdir()
        rules_dir.joinpath("definitions/login_500.yaml").write_text(
            "id: login_500\nurl_pattern: /api/login\nstatus_code: 500"
        )
        (rules_dir / "scenarios/default.yaml").write_text(
            "rule_ids:\n  - login_500\noverrides: {}"
        )

        manager = FileBasedManager(str(rules_dir), ProxyConfig())
        manager.activate("default", "192.168.1.100", rule_ids=["login_500"])

        # 验证写入格式为 scenario
        raw = (rules_dir / "activations.yaml").read_text()
        assert "ip_to_scenario" in raw
        assert "scenario_rule_overrides" in raw
        assert "ip_to_device" not in raw
        assert "device_rule_overrides" not in raw

        sid = manager.get_scenario_id_by_client_ip("192.168.1.100")
        assert sid == "default"
        rules = manager.get_intercept_rules_for_client("192.168.1.100")
        assert any(r.id == "login_500" for r in rules)

    print("✓ API activate 流程 (scenario_id) 正常")


if __name__ == "__main__":
    test_ip_to_scenario_mapping()
    test_api_schema()
    test_old_format_rejected()
    test_real_rules_dir()
    test_api_activate_flow()
    print("\n全部自测通过")
