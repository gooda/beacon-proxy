"""Data models for intercept rules and proxy config."""

from typing import List, Optional, Union

from pydantic import BaseModel, Field


class InterceptRule(BaseModel):
    """Intercept rule: match condition + rewrite action."""

    id: str = Field(..., description="Unique rule id")
    url_pattern: str = Field(..., description="URL pattern to match (substring or regex)")
    description: Optional[str] = Field(default=None, description="Rule description")
    status_code: Optional[int] = Field(default=None, description="Override response status code")
    body: Optional[Union[str, bytes]] = Field(default=None, description="Override response body")
    use_regex: bool = Field(default=False, description="Whether url_pattern is regex")
    # 域名重写：将匹配的请求转发到指定 host
    upstream_host: Optional[str] = Field(default=None, description="Rewrite request to this host (A域名->B域名)")
    upstream_port: Optional[int] = Field(default=None, description="Target port, default 443 for https else 80")
    # 网络模拟（per-rule，URL 匹配后生效）
    delay_ms: Optional[int] = Field(default=None, description="延迟注入(ms)")
    throttle_kbps: Optional[int] = Field(default=None, description="限速(KB/s)")
    packet_loss_rate: Optional[float] = Field(default=None, description="丢包率 0.0-1.0")


class NetworkCondition(BaseModel):
    """Per-client 网络条件（全局，作用于该 IP 的所有流量）。"""

    airplane_mode: bool = Field(default=False, description="飞行模式：阻断所有连接")
    delay_ms: Optional[int] = Field(default=None, description="全局延迟(ms)")
    throttle_kbps: Optional[int] = Field(default=None, description="全局限速(KB/s)")
    packet_loss_rate: Optional[float] = Field(default=None, description="全局丢包率 0.0-1.0")


class ProxyConfig(BaseModel):
    """Proxy configuration."""

    port: int = Field(default=8080, description="Proxy listen port")
    rules_file: str = Field(default="rules.yaml", description="Path to rules file or rules directory")
    scenario_id_header: str = Field(
        default="X-Scenario-ID",
        description="Header name to identify scenario for per-scenario rules",
    )


class ProxyState(BaseModel):
    """Proxy runtime state."""

    rules: List[InterceptRule] = Field(default_factory=list)
    recorded_requests: List[dict] = Field(default_factory=list)
