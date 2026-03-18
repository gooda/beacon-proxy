"""MCP server - interactive debugging use."""

import os
from typing import Optional

from llm_proxy.generator import generate_rules_from_requirement
from llm_proxy.manager.file_based import FileBasedManager
from llm_proxy.models import InterceptRule, ProxyConfig

try:
    from mcp.server.fastmcp import FastMCP
except ImportError:
    FastMCP = None  # type: ignore


def _get_manager() -> FileBasedManager:
    path = os.environ.get("LLM_PROXY_RULES", "rules.yaml")
    return FileBasedManager(path, ProxyConfig())


def create_mcp_server() -> "FastMCP":
    """Create MCP server with proxy tools. Requires: pip install mcp"""
    if FastMCP is None:
        raise ImportError("MCP not installed. Run: pip install mcp")

    mcp = FastMCP("LLM Proxy")

    @mcp.tool()
    def add_rule(
        url_pattern: str,
        rule_id: Optional[str] = None,
        description: Optional[str] = None,
        status_code: Optional[int] = None,
        body: Optional[str] = None,
        use_regex: bool = False,
        upstream_host: Optional[str] = None,
        upstream_port: Optional[int] = None,
        device_id: Optional[str] = None,
    ) -> str:
        """Add an intercept rule. url_pattern: URL to match. upstream_host: rewrite to this host (A域名->B域名). status_code, body: response override. device_id: for per-device rules."""
        manager = _get_manager()
        rules = manager.get_intercept_rules(device_id)
        rid = rule_id or f"rule_{len(rules) + 1}"
        rule = InterceptRule(
            id=rid,
            url_pattern=url_pattern,
            description=description,
            status_code=status_code,
            body=body,
            use_regex=use_regex,
            upstream_host=upstream_host,
            upstream_port=upstream_port,
        )
        manager.add_rule(rule, device_id)
        target = f" (device={device_id})" if device_id else ""
        return f"Added rule {rid}: {url_pattern}{target}"

    @mcp.tool()
    def add_domain_rewrite(
        from_host: str,
        to_host: str,
        rule_id: Optional[str] = None,
        port: int = 443,
        device_id: Optional[str] = None,
    ) -> str:
        """添加域名重写规则：将 A 域名的请求代理转发到 B 域名。from_host: 源域名。to_host: 目标域名。port: 目标端口。device_id: 绑定到设备。"""
        manager = _get_manager()
        rules = manager.get_intercept_rules(device_id)
        rid = rule_id or f"rewrite_{len(rules) + 1}"
        rule = InterceptRule(
            id=rid,
            url_pattern=from_host,
            description=f"{from_host} -> {to_host}",
            upstream_host=to_host,
            upstream_port=port,
            use_regex=False,
        )
        manager.add_rule(rule, device_id)
        target = f" (device={device_id})" if device_id else ""
        return f"Added rewrite {rid}: {from_host} -> {to_host}:{port}{target}"

    @mcp.tool()
    def remove_rule(rule_id: str, device_id: Optional[str] = None) -> str:
        """Remove an intercept rule. device_id: unbind from device only. Omit to delete definition."""
        manager = _get_manager()
        if manager.remove_rule(rule_id, device_id):
            return f"Removed rule {rule_id}"
        return f"Rule {rule_id} not found"

    @mcp.tool()
    def bind_rule(rule_id: str, device_id: str) -> str:
        """Bind a rule definition to a device (reuse mode)."""
        manager = _get_manager()
        if manager.bind_rule(rule_id, device_id):
            return f"Bound {rule_id} to {device_id}"
        return f"Failed: rule {rule_id} not found"

    @mcp.tool()
    def unbind_rule(rule_id: str, device_id: str) -> str:
        """Unbind a rule from a device (reuse mode)."""
        manager = _get_manager()
        if manager.unbind_rule(rule_id, device_id):
            return f"Unbound {rule_id} from {device_id}"
        return f"Rule {rule_id} not bound to {device_id}"

    @mcp.tool()
    def list_definitions() -> str:
        """List all rule definitions (reuse mode)."""
        manager = _get_manager()
        rules = manager.list_definitions()
        if not rules:
            return "No definitions"
        lines = []
        for r in rules:
            rewrite = f" -> {r.upstream_host}" if r.upstream_host else ""
            lines.append(f"  {r.id}: {r.url_pattern}{rewrite} -> status={r.status_code}" + (f" ({r.description})" if r.description else ""))
        return "\n".join(lines)

    @mcp.tool()
    def activate(device_id: str, client_ip: str, rule_ids: Optional[list] = None) -> str:
        """Activate device rules for client IP. UI automation calls before test. rule_ids: optional override."""
        manager = _get_manager()
        manager.activate(device_id, client_ip, rule_ids)
        return f"Activated {device_id} for IP {client_ip}"

    @mcp.tool()
    def deactivate(device_id: Optional[str] = None, client_ip: Optional[str] = None) -> str:
        """Deactivate. Provide device_id or client_ip."""
        manager = _get_manager()
        if manager.deactivate(device_id=device_id, client_ip=client_ip):
            return "Deactivated"
        return "Not found in activations"

    @mcp.tool()
    def list_activations() -> str:
        """List all activations (ip_to_device, device_rule_overrides)."""
        manager = _get_manager()
        acts = manager.list_activations()
        if not acts.get("ip_to_device"):
            return "No activations"
        lines = [f"  {ip} -> {did}" for ip, did in acts["ip_to_device"].items()]
        return "\n".join(lines)

    @mcp.tool()
    def list_rules(device_id: Optional[str] = None) -> str:
        """List intercept rules for device. device_id: device to list."""
        manager = _get_manager()
        rules = manager.get_intercept_rules(device_id)
        if not rules:
            return "No rules"
        lines = []
        for r in rules:
            rewrite = f" -> {r.upstream_host}" if r.upstream_host else ""
            lines.append(f"  {r.id}: {r.url_pattern}{rewrite} -> status={r.status_code}, body={r.body is not None}" + (f" ({r.description})" if r.description else ""))
        return "\n".join(lines)

    @mcp.tool()
    def generate_from_requirement(
        requirement: str,
        device_id: str = "default",
        client_ip: str = "",
    ) -> str:
        """根据代理需求自动生成规则并生效。requirement: 自然语言，如 登录失败、购物车空、/api/xxx 返回 500。device_id: 设备ID。client_ip: 被测设备IP，必填以激活。"""
        if not client_ip:
            return "client_ip 必填，用于激活规则"
        manager = _get_manager()
        rules = generate_rules_from_requirement(requirement)
        if not rules:
            return "无法解析需求，请使用：登录失败、购物车空、X 返回 Y、X 空 或 /api/xxx"
        rule_ids = []
        for rule in rules:
            manager.add_rule(rule, device_id)
            rule_ids.append(rule.id)
        manager.activate(device_id, client_ip, rule_ids)
        return f"已生成并激活 {rule_ids}：{device_id} -> {client_ip}"

    return mcp


def run_mcp_server() -> None:
    """Run MCP server. Use with: python -m llm_proxy.mcp_server"""
    mcp = create_mcp_server()
    mcp.run(transport="stdio")
