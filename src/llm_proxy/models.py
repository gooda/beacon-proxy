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


class ProxyConfig(BaseModel):
    """Proxy configuration."""

    port: int = Field(default=8080, description="Proxy listen port")
    rules_file: str = Field(default="rules.yaml", description="Path to rules file or rules directory")
    device_id_header: str = Field(
        default="X-Device-ID",
        description="Header name to identify device for per-device rules",
    )


class ProxyState(BaseModel):
    """Proxy runtime state."""

    rules: List[InterceptRule] = Field(default_factory=list)
    recorded_requests: List[dict] = Field(default_factory=list)
