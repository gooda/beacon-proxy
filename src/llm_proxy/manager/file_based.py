"""File-based manager - supports single-file, multi-scenario, and rule reuse (definitions + scenarios)."""

import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Type, TypeVar

import yaml
from pydantic import BaseModel

from llm_proxy.models import InterceptRule, NetworkCondition, ProxyConfig, ProxyState

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
    """Schema for single-file or legacy scenario rules."""

    rules: List[InterceptRule] = []


class ScenarioConfigSchema(BaseModel):
    """Schema for scenario config - references rule_ids, optional overrides."""

    rule_ids: List[str] = []
    overrides: Dict[str, Dict[str, Any]] = {}


class ActivationsSchema(BaseModel):
    """Schema for activations - IP to scenario mapping, optional rule overrides."""

    ip_to_scenario: Dict[str, str] = {}  # client_ip -> scenario_id
    scenario_rule_overrides: Dict[str, List[str]] = {}  # scenario_id -> rule_ids (override scenarios/*.yaml)
    network_conditions: Dict[str, Dict[str, Any]] = {}  # client_ip -> NetworkCondition dict


def _safe_filename(name: str) -> str:
    """Sanitize rule_id for use as filename."""
    return re.sub(r'[^\w\-.]', '_', name).strip("_") or "rule"


class FileBasedManager:
    """Manager supporting: single-file, multi-scenario, and rule reuse (definitions + scenarios)."""

    def __init__(self, rules_path: str, config: Optional[ProxyConfig] = None):
        self._rules_base = Path(str(rules_path).rstrip("/"))
        self._config = config or ProxyConfig()
        self._state = ProxyState()
        self._single_file = self._rules_base.suffix in (".yaml", ".yml")
        self._reuse_mode = not self._single_file  # directory => definitions + scenarios
        # Inline rules from APPAUTO activate API (scenario_id -> rules), ephemeral, not persisted
        self._scenario_inline_rules: Dict[str, List[InterceptRule]] = {}

    def _definitions_dir(self) -> Path:
        return self._rules_base / "definitions"

    def _scenarios_dir(self) -> Path:
        return self._rules_base / "scenarios"

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

    def _scenario_path(self, scenario_id: str) -> Path:
        return self._scenarios_dir() / f"{_safe_filename(scenario_id)}.yaml"

    def _get_rules_path(self, scenario_id: Optional[str] = None) -> Path:
        """Legacy: path for single-file or old multi-scenario format."""
        if self._single_file:
            return self._rules_base
        filename = f"{scenario_id or 'default'}.yaml"
        return self._rules_base / filename

    def _load_scenario_config(self, scenario_id: str) -> ScenarioConfigSchema:
        path = self._scenario_path(scenario_id)
        if path.exists():
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            return _pydantic_validate(ScenarioConfigSchema, data)
        if scenario_id and scenario_id != "default":
            return self._load_scenario_config("default")
        return ScenarioConfigSchema()

    def _save_scenario_config(self, scenario_id: str, config: ScenarioConfigSchema) -> None:
        path = self._scenario_path(scenario_id)
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

    def get_definition(self, rule_id: str) -> Optional[InterceptRule]:
        """Load rule definition by id."""
        return self._load_definition(rule_id)

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
        scenario_id: Optional[str] = None,
        rule_ids_override: Optional[List[str]] = None,
    ) -> List[InterceptRule]:
        """Get rules for scenario. rule_ids_override: use these instead of scenario config (reuse mode)."""
        if self._single_file:
            path = self._get_rules_path()
            if path.exists():
                data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
                schema = _pydantic_validate(RulesFileSchema, data)
                return schema.rules.copy()
            return []

        sid = scenario_id or "default"
        rule_ids = rule_ids_override
        if rule_ids is None:
            config = self._load_scenario_config(sid)
            rule_ids = config.rule_ids
        else:
            config = self._load_scenario_config(sid)

        result: List[InterceptRule] = []
        for rid in rule_ids:
            rule = self._load_definition(rid)
            if rule:
                over = config.overrides.get(rid, {})
                if over:
                    rule = rule.model_copy(update=over)
                result.append(rule)
        inline = self._scenario_inline_rules.get(sid, [])
        return result + inline

    def get_scenario_id_by_client_ip(self, client_ip: str) -> Optional[str]:
        """Get scenario_id for client IP from activations."""
        acts = self._load_activations()
        return acts.ip_to_scenario.get(client_ip)

    def get_intercept_rules_for_client(self, client_ip: str) -> List[InterceptRule]:
        """Get rules for client by IP (activation). Returns [] if not activated."""
        acts = self._load_activations()
        scenario_id = acts.ip_to_scenario.get(client_ip)
        if not scenario_id:
            return []
        file_rules: List[InterceptRule]
        if self._single_file:
            file_rules = self.get_intercept_rules()
        else:
            rule_ids = acts.scenario_rule_overrides.get(scenario_id)
            file_rules = self.get_intercept_rules(scenario_id, rule_ids)
        inline = self._scenario_inline_rules.get(scenario_id, [])
        return file_rules + inline

    def activate(
        self,
        scenario_id: str,
        client_ip: str,
        rule_ids: Optional[List[str]] = None,
        inline_rules: Optional[List[InterceptRule]] = None,
    ) -> None:
        """Activate scenario for client IP. rule_ids overrides scenario config (reuse mode).
        inline_rules: ephemeral rules from APPAUTO (networkMock, networkDomainRewrite)."""
        acts = self._load_activations()
        acts.ip_to_scenario[client_ip] = scenario_id
        if rule_ids is not None and self._reuse_mode:
            acts.scenario_rule_overrides[scenario_id] = rule_ids
        elif scenario_id in acts.scenario_rule_overrides:
            del acts.scenario_rule_overrides[scenario_id]
        if inline_rules:
            self._scenario_inline_rules[scenario_id] = inline_rules.copy()
        else:
            self._scenario_inline_rules.pop(scenario_id, None)
        self._save_activations(acts)

    def deactivate(self, scenario_id: Optional[str] = None, client_ip: Optional[str] = None) -> bool:
        """Deactivate. By scenario_id or client_ip."""
        acts = self._load_activations()
        changed = False
        if client_ip and client_ip in acts.ip_to_scenario:
            scenario_from_ip = acts.ip_to_scenario[client_ip]
            del acts.ip_to_scenario[client_ip]
            changed = True
            if scenario_from_ip in self._scenario_inline_rules:
                del self._scenario_inline_rules[scenario_from_ip]
        if client_ip and client_ip in acts.network_conditions:
            del acts.network_conditions[client_ip]
            changed = True
        if scenario_id:
            to_remove = [ip for ip, sid in acts.ip_to_scenario.items() if sid == scenario_id]
            for ip in to_remove:
                del acts.ip_to_scenario[ip]
                changed = True
            if scenario_id in acts.scenario_rule_overrides:
                del acts.scenario_rule_overrides[scenario_id]
                changed = True
            if scenario_id in self._scenario_inline_rules:
                del self._scenario_inline_rules[scenario_id]
                changed = True
        if changed:
            self._save_activations(acts)
        return changed

    def deactivate_all(self) -> int:
        """Deactivate all activations. Returns count of cleared IP bindings."""
        acts = self._load_activations()
        count = len(acts.ip_to_scenario)
        has_conditions = bool(acts.network_conditions)
        if count == 0 and not acts.scenario_rule_overrides and not self._scenario_inline_rules and not has_conditions:
            return 0
        acts.ip_to_scenario.clear()
        acts.scenario_rule_overrides.clear()
        acts.network_conditions.clear()
        self._scenario_inline_rules.clear()
        self._save_activations(acts)
        return count

    def list_activations(self) -> Dict[str, Any]:
        """List all activations."""
        acts = self._load_activations()
        return _pydantic_dump(acts)

    def get_config(self) -> ProxyConfig:
        return self._config

    def get_state(self) -> ProxyState:
        return self._state.model_copy(deep=True)

    def add_rule(self, rule: InterceptRule, scenario_id: Optional[str] = None) -> None:
        """Add rule. In reuse mode: save to definitions, optionally bind to scenario."""
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
        if scenario_id:
            self.bind_rule(rule.id, scenario_id)

    def remove_rule(self, rule_id: str, scenario_id: Optional[str] = None) -> bool:
        """Remove rule. If scenario_id: unbind from scenario. Else: delete definition and unbind from all."""
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

        if scenario_id:
            return self.unbind_rule(rule_id, scenario_id)

        self._delete_definition(rule_id)
        for p in self._scenarios_dir().glob("*.yaml"):
            sid = p.stem
            config = self._load_scenario_config(sid)
            if rule_id in config.rule_ids:
                config.rule_ids = [x for x in config.rule_ids if x != rule_id]
                config.overrides.pop(rule_id, None)
                self._save_scenario_config(sid, config)
        return True

    def bind_rule(self, rule_id: str, scenario_id: str) -> bool:
        """Bind rule to scenario (reuse mode only)."""
        if not self._reuse_mode:
            return False
        if not self._load_definition(rule_id):
            return False
        config = self._load_scenario_config(scenario_id)
        if rule_id not in config.rule_ids:
            config.rule_ids.append(rule_id)
            self._save_scenario_config(scenario_id, config)
        return True

    def unbind_rule(self, rule_id: str, scenario_id: str) -> bool:
        """Unbind rule from scenario (reuse mode only)."""
        if not self._reuse_mode:
            return False
        config = self._load_scenario_config(scenario_id)
        if rule_id in config.rule_ids:
            config.rule_ids = [x for x in config.rule_ids if x != rule_id]
            config.overrides.pop(rule_id, None)
            self._save_scenario_config(scenario_id, config)
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

    def list_scenarios(self) -> List[str]:
        """List scenario ids from scenarios directory (reuse mode only)."""
        if not self._reuse_mode:
            return []
        scenarios_dir = self._scenarios_dir()
        if not scenarios_dir.exists():
            return []
        return sorted(p.stem for p in scenarios_dir.glob("*.yaml"))

    def create_scenario(self, scenario_id: str) -> Optional[str]:
        """Create empty scenario config. Returns None if created, else error reason."""
        if not self._reuse_mode:
            return "not_reuse_mode"
        path = self._scenario_path(scenario_id)
        if path.exists():
            return "exists"
        self._save_scenario_config(scenario_id, ScenarioConfigSchema())
        return None

    def update_rule(self, rule_id: str, updates: Dict[str, Any]) -> Optional[InterceptRule]:
        """Update a rule definition. Returns updated rule or None if not found. id cannot be changed."""
        existing = self._load_definition(rule_id)
        if not existing:
            return None
        allowed = {"url_pattern", "description", "status_code", "body", "use_regex", "upstream_host", "upstream_port", "delay_ms", "throttle_kbps", "packet_loss_rate"}
        d = _pydantic_dump(existing)
        d.update({k: v for k, v in updates.items() if k in allowed})
        updated = _pydantic_validate(InterceptRule, d)
        self._save_definition(updated)
        return updated

    def set_network_condition(self, client_ip: str, condition: NetworkCondition) -> None:
        """Set network condition for a client IP. Persisted to activations.yaml."""
        acts = self._load_activations()
        acts.network_conditions[client_ip] = _pydantic_dump(condition)
        self._save_activations(acts)

    def get_network_condition(self, client_ip: str) -> Optional[NetworkCondition]:
        """Get network condition for a client IP. Returns None if not set."""
        acts = self._load_activations()
        data = acts.network_conditions.get(client_ip)
        if data:
            return _pydantic_validate(NetworkCondition, data)
        return None

    def clear_network_condition(self, client_ip: str) -> bool:
        """Clear network condition for a client IP. Returns True if existed."""
        acts = self._load_activations()
        if client_ip in acts.network_conditions:
            del acts.network_conditions[client_ip]
            self._save_activations(acts)
            return True
        return False

    def list_network_conditions(self) -> Dict[str, NetworkCondition]:
        """List all active network conditions, keyed by client IP."""
        acts = self._load_activations()
        result: Dict[str, NetworkCondition] = {}
        for ip, data in acts.network_conditions.items():
            result[ip] = _pydantic_validate(NetworkCondition, data)
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
