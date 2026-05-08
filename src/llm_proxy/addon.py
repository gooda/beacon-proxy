"""mitmproxy addon - intercept and rewrite responses."""

import random
import re
import time
from typing import TYPE_CHECKING, Optional

from mitmproxy import ctx

from llm_proxy.models import InterceptRule

if TYPE_CHECKING:
    from mitmproxy.http import HTTPFlow

    from llm_proxy.manager.base import ManagementInterface


class LLMProxyAddon:
    """Addon that intercepts responses and rewrites by rules."""

    def __init__(self, manager: "ManagementInterface"):
        self.manager = manager

    def _get_scenario_id(self, flow: "HTTPFlow") -> Optional[str]:
        """Extract scenario id from request header."""
        header = self.manager.get_config().scenario_id_header
        return flow.request.headers.get(header)

    def _get_client_ip(self, flow: "HTTPFlow") -> Optional[str]:
        """Extract client IP from connection."""
        try:
            peername = getattr(flow.client_conn, "peername", None)
            if peername:
                return str(peername[0])
        except Exception:
            pass
        return None

    def request(self, flow: "HTTPFlow") -> None:
        """网络条件检查、域名重写（upstream_host）与请求记录。"""
        url = flow.request.pretty_url
        client_ip = self._get_client_ip(flow)

        # 1. Per-client 网络条件检查（飞行模式、全局丢包）
        if client_ip:
            condition = self.manager.get_network_condition(client_ip)
            if condition:
                if condition.airplane_mode:
                    flow.kill()
                    return
                if condition.packet_loss_rate and random.random() < condition.packet_loss_rate:
                    flow.kill()
                    return

        # 2. 获取规则
        rules = self.manager.get_intercept_rules_for_client(client_ip) if client_ip else []
        if not rules:
            scenario_id = self._get_scenario_id(flow)
            rules = self.manager.get_intercept_rules(scenario_id)

        # 3. 域名重写 + per-rule 丢包检查
        for rule in rules:
            if self._match_url(url, rule):
                if rule.packet_loss_rate and random.random() < rule.packet_loss_rate:
                    flow.kill()
                    return
                if rule.upstream_host:
                    flow.request.host = rule.upstream_host
                    flow.request.port = rule.upstream_port or (443 if flow.request.scheme == "https" else 80)
                    flow.request.headers["Host"] = rule.upstream_host
                break

        # 4. 记录请求（含 client_ip / headers / query，供远端调用模板的 device 上下文使用）
        try:
            self.manager.record_request(
                {
                    "url": url,
                    "method": flow.request.method,
                    "path": flow.request.path,
                    "scenario_id": self._get_scenario_id(flow),
                    "client_ip": client_ip,
                    "headers": {k.lower(): v for k, v in dict(flow.request.headers).items()},
                    "query": dict(flow.request.query) if flow.request.query else {},
                    "ts": time.time(),
                }
            )
        except Exception:
            pass

    def response(self, flow: "HTTPFlow") -> None:
        """Rewrite response + 网络模拟（延迟、限速）。Activation (by IP) takes precedence over X-Scenario-ID."""
        client_ip = self._get_client_ip(flow)

        # 1. Per-client 网络条件作为默认值
        effective_delay_ms = None
        effective_throttle_kbps = None
        if client_ip:
            condition = self.manager.get_network_condition(client_ip)
            if condition:
                effective_delay_ms = condition.delay_ms
                effective_throttle_kbps = condition.throttle_kbps

        # 2. 获取规则
        rules = self.manager.get_intercept_rules_for_client(client_ip) if client_ip else []
        if not rules:
            scenario_id = self._get_scenario_id(flow)
            rules = self.manager.get_intercept_rules(scenario_id)
        url = flow.request.pretty_url

        # 3. 规则匹配：响应覆写 + per-rule 网络模拟覆盖
        for rule in rules:
            if self._match_url(url, rule):
                if rule.status_code is not None:
                    flow.response.status_code = rule.status_code
                content: Optional[bytes] = None
                if rule.body_file:
                    try:
                        path = self.manager.resolve_body_file_path(rule.body_file)
                        content = path.read_bytes()
                        if path.suffix.lower() in (".html", ".htm"):
                            flow.response.headers["Content-Type"] = "text/html; charset=utf-8"
                    except OSError as e:
                        ctx.log.warn(f"beacon-proxy: body_file unreadable ({rule.body_file}): {e}")
                elif rule.body is not None:
                    raw = rule.body
                    content = raw.encode("utf-8") if isinstance(raw, str) else raw
                if content is not None:
                    flow.response.content = content
                if rule.delay_ms is not None:
                    effective_delay_ms = rule.delay_ms
                if rule.throttle_kbps is not None:
                    effective_throttle_kbps = rule.throttle_kbps
                break

        # 4. 应用延迟注入
        if effective_delay_ms and effective_delay_ms > 0:
            time.sleep(effective_delay_ms / 1000.0)

        # 5. 应用限速（按响应大小计算传输耗时）
        if effective_throttle_kbps and effective_throttle_kbps > 0:
            content_length = len(flow.response.content or b"")
            if content_length > 0:
                transfer_time = content_length / (effective_throttle_kbps * 1024)
                time.sleep(transfer_time)

    def _match_url(self, url: str, rule: InterceptRule) -> bool:
        """Check if url matches rule's url_pattern."""
        if rule.use_regex:
            return bool(re.search(rule.url_pattern, url))
        return rule.url_pattern in url
