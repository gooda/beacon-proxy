"""Entry point for mitmproxy -s run_addon.py."""

import os

from llm_proxy.addon import LLMProxyAddon
from llm_proxy.manager.file_based import FileBasedManager
from llm_proxy.models import ProxyConfig

_rules_path = os.environ.get("LLM_PROXY_RULES", "rules.yaml")
_config = ProxyConfig(
    device_id_header=os.environ.get("BEACON_PROXY_DEVICE_ID_HEADER", "X-Device-ID"),
)
_manager = FileBasedManager(_rules_path, _config)
addons = [LLMProxyAddon(_manager)]
