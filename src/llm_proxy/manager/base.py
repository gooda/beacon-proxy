"""Management interface abstraction."""

from pathlib import Path
from typing import List, Optional, Protocol

from llm_proxy.models import InterceptRule, NetworkCondition, ProxyConfig, ProxyState, RemoteApiCall


class ManagementInterface(Protocol):
    """Management abstraction - proxy core depends on this."""

    def get_intercept_rules(self, scenario_id: Optional[str] = None) -> List[InterceptRule]:
        """Get intercept rules, optionally for a specific scenario."""
        ...

    def get_intercept_rules_for_client(self, client_ip: str) -> List[InterceptRule]:
        """Get rules for client by IP (activation). Returns [] if not activated."""
        ...

    def get_config(self) -> ProxyConfig:
        """Get proxy config."""
        ...

    def resolve_body_file_path(self, body_file: str) -> Path:
        """Resolve body_file to an absolute path (relative paths are under rules base)."""
        ...

    def get_state(self) -> ProxyState:
        """Get proxy state."""
        ...

    def add_rule(self, rule: InterceptRule, scenario_id: Optional[str] = None) -> None:
        """Add a rule, optionally for a specific scenario."""
        ...

    def remove_rule(self, rule_id: str, scenario_id: Optional[str] = None) -> bool:
        """Remove rule by id. Returns True if removed."""
        ...

    def get_network_condition(self, client_ip: str) -> Optional[NetworkCondition]:
        """Get network condition for client IP. Returns None if not set."""
        ...

    def set_network_condition(self, client_ip: str, condition: NetworkCondition) -> None:
        """Set network condition for client IP."""
        ...

    def clear_network_condition(self, client_ip: str) -> bool:
        """Clear network condition for client IP. Returns True if existed."""
        ...

    def record_request(self, request: dict) -> None:
        """Record a request for later query."""
        ...

    def get_recorded_requests(self, url_pattern: Optional[str] = None, limit: int = 100) -> List[dict]:
        """Get recorded requests, optionally filtered by url_pattern."""
        ...

    def get_last_request_for_ip(self, client_ip: str) -> Optional[dict]:
        """Return the most recent recorded request for client IP, or None."""
        ...

    # --- Remote API calls (独立于 rules/network_condition 的出站调用配置) ---

    def list_remote_calls(self) -> List[RemoteApiCall]:
        """List all remote API call definitions."""
        ...

    def get_remote_call(self, call_id: str) -> Optional[RemoteApiCall]:
        """Get a remote API call definition by id."""
        ...

    def save_remote_call(self, call: RemoteApiCall) -> None:
        """Create or overwrite a remote API call definition."""
        ...

    def delete_remote_call(self, call_id: str) -> bool:
        """Delete a remote API call definition. Returns True if existed."""
        ...
