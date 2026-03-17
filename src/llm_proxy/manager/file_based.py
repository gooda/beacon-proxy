"""File-based manager - supports single-file, multi-device, and rule reuse (definitions + devices)."""

import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Type, TypeVar

import yaml
from pydantic import BaseModel

from llm_proxy.models import InterceptRule, ProxyConfig, ProxyState

T = TypeVar("T", bound=BaseModel)


def _pydantic_validate(model: Type[T], data: Any) -> T:
    """Pydantic v1/v2 compatible validation."""
    if hasattr(model, "model_validate"):
        return model.model_validate(data)
    return model.parse_obj(data)


def _pydantic_dump(obj: BaseModel) -> Dict[str, Any]:
    """Pydantic v1/v2 compatible dump to dict."""
    return obj.model_dump() if hasattr(obj, "model_dump") else obj.dict()


class RulesFileSchema(BaseModel):
    """Schema for single-file or legacy device rules."""

    rules: List[InterceptRule] = []


class DeviceConfigSchema(BaseModel):
    """Schema for device config - references rule_ids, optional overrides."""

    rule_ids: List[str] = []
    overrides: Dict[str, Dict[str, Any]] = {}


class ActivationsSchema(BaseModel):
    """Schema for activations - IP to device mapping, optional rule overrides."""

    ip_to_device: Dict[str, str] = {}  # client_ip -> device_id
    device_rule_overrides: Dict[str, List[str]] = {}  # device_id -> rule_ids (override devices/*.yaml)


def _safe_filename(name: str) -> str:
    """Sanitize rule_id for use as filename."""
    return re.sub(r'[^\w\-.]', '_', name).strip("_") or "rule"


class FileBasedManager:
    """Manager supporting: single-file, multi-device, and rule reuse (definitions + devices)."""

    def __init__(self, rules_path: str, config: Optional[ProxyConfig] = None):
        self._rules_base = Path(str(rules_path).rstrip("/"))
        self._config = config or ProxyConfig()
        self._state = ProxyState()
        self._single_file = self._rules_base.suffix in (".yaml", ".yml")
        self._reuse_mode = not self._single_file  # directory => definitions + devices

    def _definitions_dir(self) -> Path:
        return self._rules_base / "definitions"

    def _devices_dir(self) -> Path:
        return self._rules_base / "devices"

    def _activations_path(self) -> Path:
        """Activations file: same dir as rules.yaml, or rules/activations.yaml."""
        if self._single_file:
            return self._rules_base.parent / "activations.yaml"
        return self._rules_base / "activations.yaml"

    def _load_activations(self) -> ActivationsSchema:
        path = self._activations_path()
        if path.exists():
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            return _pydantic_validate(ActivationsSchema, data)
        return ActivationsSchema()

    def _save_activations(self, schema: ActivationsSchema) -> None:
        path = self._activations_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            yaml.dump(_pydantic_dump(schema), allow_unicode=True, default_flow_style=False),
            encoding="utf-8",
        )

    def _definition_path(self, rule_id: str) -> Path:
        return self._definitions_dir() / f"{_safe_filename(rule_id)}.yaml"

    def _device_path(self, device_id: str) -> Path:
        return self._devices_dir() / f"{_safe_filename(device_id)}.yaml"

    def _get_rules_path(self, device_id: Optional[str] = None) -> Path:
        """Legacy: path for single-file or old multi-device format."""
        if self._single_file:
            return self._rules_base
        filename = f"{device_id or 'default'}.yaml"
        return self._rules_base / filename

    def _load_device_config(self, device_id: str) -> DeviceConfigSchema:
        path = self._device_path(device_id)
        if path.exists():
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            return _pydantic_validate(DeviceConfigSchema, data)
        if device_id and device_id != "default":
            return self._load_device_config("default")
        return DeviceConfigSchema()

    def _save_device_config(self, device_id: str, config: DeviceConfigSchema) -> None:
        path = self._device_path(device_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            yaml.dump(_pydantic_dump(config), allow_unicode=True, default_flow_style=False),
            encoding="utf-8",
        )

    def _load_definition(self, rule_id: str) -> Optional[InterceptRule]:
        path = self._definition_path(rule_id)
        if path.exists():
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            return _pydantic_validate(InterceptRule, data)
        return None

    def _save_definition(self, rule: InterceptRule) -> None:
        path = self._definition_path(rule.id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            yaml.dump(_pydantic_dump(rule), allow_unicode=True, default_flow_style=False),
            encoding="utf-8",
        )

    def _delete_definition(self, rule_id: str) -> bool:
        path = self._definition_path(rule_id)
        if path.exists():
            path.unlink()
            return True
        return False

    def get_intercept_rules(
        self,
        device_id: Optional[str] = None,
        rule_ids_override: Optional[List[str]] = None,
    ) -> List[InterceptRule]:
        """Get rules for device. rule_ids_override: use these instead of device config (reuse mode)."""
        if self._single_file:
            path = self._get_rules_path()
            if path.exists():
                data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
                schema = _pydantic_validate(RulesFileSchema, data)
                return schema.rules.copy()
            return []

        dev_id = device_id or "default"
        rule_ids = rule_ids_override
        if rule_ids is None:
            config = self._load_device_config(dev_id)
            rule_ids = config.rule_ids
        else:
            config = self._load_device_config(dev_id)

        result: List[InterceptRule] = []
        for rid in rule_ids:
            rule = self._load_definition(rid)
            if rule:
                over = config.overrides.get(rid, {})
                if over:
                    rule = rule.model_copy(update=over)
                result.append(rule)
        return result

    def get_device_id_by_client_ip(self, client_ip: str) -> Optional[str]:
        """Get device_id for client IP from activations."""
        acts = self._load_activations()
        return acts.ip_to_device.get(client_ip)

    def get_intercept_rules_for_client(self, client_ip: str) -> List[InterceptRule]:
        """Get rules for client by IP (activation). Returns [] if not activated."""
        acts = self._load_activations()
        device_id = acts.ip_to_device.get(client_ip)
        if not device_id:
            return []
        if self._single_file:
            return self.get_intercept_rules()
        rule_ids = acts.device_rule_overrides.get(device_id)
        return self.get_intercept_rules(device_id, rule_ids)

    def activate(
        self,
        device_id: str,
        client_ip: str,
        rule_ids: Optional[List[str]] = None,
    ) -> None:
        """Activate device for client IP. rule_ids overrides device config (reuse mode)."""
        acts = self._load_activations()
        acts.ip_to_device[client_ip] = device_id
        if rule_ids is not None and self._reuse_mode:
            acts.device_rule_overrides[device_id] = rule_ids
        elif device_id in acts.device_rule_overrides:
            del acts.device_rule_overrides[device_id]
        self._save_activations(acts)

    def deactivate(self, device_id: Optional[str] = None, client_ip: Optional[str] = None) -> bool:
        """Deactivate. By device_id or client_ip."""
        acts = self._load_activations()
        changed = False
        if client_ip and client_ip in acts.ip_to_device:
            del acts.ip_to_device[client_ip]
            changed = True
        if device_id:
            to_remove = [ip for ip, did in acts.ip_to_device.items() if did == device_id]
            for ip in to_remove:
                del acts.ip_to_device[ip]
                changed = True
            if device_id in acts.device_rule_overrides:
                del acts.device_rule_overrides[device_id]
                changed = True
        if changed:
            self._save_activations(acts)
        return changed

    def list_activations(self) -> Dict[str, Any]:
        """List all activations."""
        acts = self._load_activations()
        return _pydantic_dump(acts)

    def get_config(self) -> ProxyConfig:
        return self._config

    def get_state(self) -> ProxyState:
        return self._state.model_copy(deep=True)

    def add_rule(self, rule: InterceptRule, device_id: Optional[str] = None) -> None:
        """Add rule. In reuse mode: save to definitions, optionally bind to device."""
        if self._single_file:
            path = self._get_rules_path()
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {} if path.exists() else {}
            schema = _pydantic_validate(RulesFileSchema, data)
            schema.rules = [r for r in schema.rules if r.id != rule.id]
            schema.rules.append(rule)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                yaml.dump(_pydantic_dump(schema), allow_unicode=True, default_flow_style=False),
                encoding="utf-8",
            )
            return

        self._save_definition(rule)
        if device_id:
            self.bind_rule(rule.id, device_id)

    def remove_rule(self, rule_id: str, device_id: Optional[str] = None) -> bool:
        """Remove rule. If device_id: unbind from device. Else: delete definition and unbind from all."""
        if self._single_file:
            path = self._get_rules_path()
            if not path.exists():
                return False
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            schema = _pydantic_validate(RulesFileSchema, data)
            before = len(schema.rules)
            schema.rules = [r for r in schema.rules if r.id != rule_id]
            if len(schema.rules) < before:
                path.write_text(
                    yaml.dump(_pydantic_dump(schema), allow_unicode=True, default_flow_style=False),
                    encoding="utf-8",
                )
                return True
            return False

        if device_id:
            return self.unbind_rule(rule_id, device_id)

        self._delete_definition(rule_id)
        for p in self._devices_dir().glob("*.yaml"):
            dev_id = p.stem
            config = self._load_device_config(dev_id)
            if rule_id in config.rule_ids:
                config.rule_ids = [x for x in config.rule_ids if x != rule_id]
                config.overrides.pop(rule_id, None)
                self._save_device_config(dev_id, config)
        return True

    def bind_rule(self, rule_id: str, device_id: str) -> bool:
        """Bind rule to device (reuse mode only)."""
        if not self._reuse_mode:
            return False
        if not self._load_definition(rule_id):
            return False
        config = self._load_device_config(device_id)
        if rule_id not in config.rule_ids:
            config.rule_ids.append(rule_id)
            self._save_device_config(device_id, config)
        return True

    def unbind_rule(self, rule_id: str, device_id: str) -> bool:
        """Unbind rule from device (reuse mode only)."""
        if not self._reuse_mode:
            return False
        config = self._load_device_config(device_id)
        if rule_id in config.rule_ids:
            config.rule_ids = [x for x in config.rule_ids if x != rule_id]
            config.overrides.pop(rule_id, None)
            self._save_device_config(device_id, config)
            return True
        return False

    def list_definitions(self) -> List[InterceptRule]:
        """List all rule definitions (reuse mode only)."""
        if not self._reuse_mode:
            return []
        result: List[InterceptRule] = []
        def_dir = self._definitions_dir()
        if def_dir.exists():
            for p in def_dir.glob("*.yaml"):
                data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
                try:
                    result.append(_pydantic_validate(InterceptRule, data))
                except Exception:
                    pass
        return result

    def record_request(self, request: dict) -> None:
        self._state.recorded_requests.append(request)

    def get_recorded_requests(
        self, url_pattern: Optional[str] = None, limit: int = 100
    ) -> List[dict]:
        requests = self._state.recorded_requests[-limit:]
        if url_pattern:
            requests = [r for r in requests if url_pattern in r.get("url", "")]
        return list(reversed(requests))
