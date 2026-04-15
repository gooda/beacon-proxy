"""Management interface abstraction."""

from typing import List, Optional, Protocol

from llm_proxy.models import InterceptRule, NetworkCondition, ProxyConfig, ProxyState


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
