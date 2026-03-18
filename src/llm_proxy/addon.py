"""mitmproxy addon - intercept and rewrite responses."""

import re
from typing import TYPE_CHECKING, Optional

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
        """域名重写（upstream_host）与请求记录。"""
        url = flow.request.pretty_url
        client_ip = self._get_client_ip(flow)
        rules = self.manager.get_intercept_rules_for_client(client_ip) if client_ip else []
        if not rules:
            scenario_id = self._get_scenario_id(flow)
            rules = self.manager.get_intercept_rules(scenario_id)

        for rule in rules:
            if rule.upstream_host and self._match_url(url, rule):
                flow.request.host = rule.upstream_host
                flow.request.port = rule.upstream_port or (443 if flow.request.scheme == "https" else 80)
                flow.request.headers["Host"] = rule.upstream_host
                break

        try:
            self.manager.record_request(
                {
                    "url": url,
                    "method": flow.request.method,
                    "path": flow.request.path,
                    "scenario_id": self._get_scenario_id(flow),
                }
            )
        except Exception:
            pass

    def response(self, flow: "HTTPFlow") -> None:
        """Rewrite response if matched by rule. Activation (by IP) takes precedence over X-Scenario-ID."""
        client_ip = self._get_client_ip(flow)
        rules = self.manager.get_intercept_rules_for_client(client_ip) if client_ip else []
        if not rules:
            scenario_id = self._get_scenario_id(flow)
            rules = self.manager.get_intercept_rules(scenario_id)
        url = flow.request.pretty_url

        for rule in rules:
            if self._match_url(url, rule):
                if rule.status_code is not None:
                    flow.response.status_code = rule.status_code
                if rule.body is not None:
                    content = rule.body
                    if isinstance(content, str):
                        content = content.encode("utf-8")
                    flow.response.content = content
                break

    def _match_url(self, url: str, rule: InterceptRule) -> bool:
        """Check if url matches rule's url_pattern."""
        if rule.use_regex:
            return bool(re.search(rule.url_pattern, url))
        return rule.url_pattern in url
