"""REST API for activation - UI automation calls to activate scenario rules."""

import os
from pathlib import Path

_EDITOR_HTML_PATH = Path(__file__).parent / "static" / "editor.html"
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel, Field

from llm_proxy.generator import generate_rules_from_requirement
from llm_proxy.manager.file_based import FileBasedManager
from llm_proxy.models import InterceptRule, ProxyConfig

app = FastAPI(title="Beacon Proxy API", version="0.1.0")


def _inline_rule_to_intercept_rule(r: Dict[str, Any]) -> InterceptRule:
    """Convert APPAUTO inline rule dict to InterceptRule."""
    rid = r.get("id") or f"inline_{hash(str(r)) % 10**8}"
    url = r.get("url") or r.get("url_pattern") or ""
    return InterceptRule(
        id=str(rid),
        url_pattern=url,
        description=r.get("description"),
        status_code=r.get("status_code"),
        body=r.get("body") or r.get("response"),
        use_regex=r.get("use_regex", False),
        upstream_host=r.get("upstream_host"),
        upstream_port=r.get("upstream_port"),
    )


def _get_cert_dir() -> Path:
    """mitmproxy 证书目录，默认 ~/.mitmproxy"""
    return Path(os.environ.get("BEACON_PROXY_CONFDIR", os.path.expanduser("~/.mitmproxy")))


def _get_manager() -> FileBasedManager:
    path = os.environ.get("LLM_PROXY_RULES", "rules.yaml")
    return FileBasedManager(path, ProxyConfig())


class ActivateRequest(BaseModel):
    scenario_id: str
    client_ip: str
    rule_ids: Optional[List[str]] = None
    rules: Optional[List[Dict[str, Any]]] = Field(
        default=None,
        description="Inline rules (APPAUTO). url/url_pattern, status_code, response/body, upstream_host, upstream_port",
    )


class ActivateResponse(BaseModel):
    ok: bool
    message: str


class GenerateRequest(BaseModel):
    """根据代理需求生成规则并生效。"""

    requirement: str = Field(..., description="自然语言需求，如：登录失败、购物车空、/api/xxx 返回 500")
    scenario_id: str = Field(default="default", description="场景 ID")
    client_ip: str = Field(..., description="客户端 IP（被测设备），用于激活")


class GenerateResponse(BaseModel):
    ok: bool
    message: str
    rule_ids: List[str] = Field(default_factory=list, description="生成的规则 ID 列表")


@app.post("/api/generate", response_model=GenerateResponse)
def generate_and_activate(req: GenerateRequest) -> GenerateResponse:
    """
    根据代理需求自动生成规则、写入服务并激活。

    支持需求格式：
    - 预设：登录失败、购物车空
    - X 返回 Y：如「登录 返回 500」
    - X 空：如「购物车 空」
    - 直接 URL：/api/login
    """
    manager = _get_manager()
    rules = generate_rules_from_requirement(req.requirement)
    if not rules:
        raise HTTPException(status_code=400, detail="无法解析需求，请使用：登录失败、购物车空、X 返回 Y、X 空 或 /api/xxx")

    rule_ids: List[str] = []
    for rule in rules:
        manager.add_rule(rule, req.scenario_id)
        rule_ids.append(rule.id)

    manager.activate(req.scenario_id, req.client_ip, rule_ids)
    return GenerateResponse(
        ok=True,
        message=f"已生成 {len(rule_ids)} 条规则并激活：{req.scenario_id} -> {req.client_ip}",
        rule_ids=rule_ids,
    )


@app.post("/api/activate", response_model=ActivateResponse)
def activate(req: ActivateRequest) -> ActivateResponse:
    """Activate scenario rules for client IP. UI automation calls this before running tests.
    Supports rule_ids (from definitions) and rules (inline from APPAUTO, incl. upstream_host for domain rewrite).
    """
    manager = _get_manager()
    inline_rules: Optional[List[InterceptRule]] = None
    if req.rules:
        inline_rules = [_inline_rule_to_intercept_rule(r) for r in req.rules]
    manager.activate(req.scenario_id, req.client_ip, req.rule_ids, inline_rules)
    rules_desc = f" rule_ids={req.rule_ids}" if req.rule_ids else ""
    if inline_rules:
        rules_desc += f" inline={len(inline_rules)}" if rules_desc else f"inline={len(inline_rules)}"
    return ActivateResponse(
        ok=True,
        message=f"Activated scenario {req.scenario_id} for IP {req.client_ip}" + (f" {rules_desc}" if rules_desc else ""),
    )


@app.delete("/api/activate/{scenario_id}", response_model=ActivateResponse)
def deactivate_by_scenario(scenario_id: str) -> ActivateResponse:
    """Deactivate all activations for scenario."""
    manager = _get_manager()
    if manager.deactivate(scenario_id=scenario_id):
        return ActivateResponse(ok=True, message=f"Deactivated scenario {scenario_id}")
    raise HTTPException(status_code=404, detail=f"Scenario {scenario_id} not found in activations")


@app.delete("/api/activate/ip/{client_ip}", response_model=ActivateResponse)
def deactivate_by_ip(client_ip: str) -> ActivateResponse:
    """Deactivate activation for client IP."""
    manager = _get_manager()
    if manager.deactivate(client_ip=client_ip):
        return ActivateResponse(ok=True, message=f"Deactivated IP {client_ip}")
    raise HTTPException(status_code=404, detail=f"IP {client_ip} not found in activations")


@app.delete("/api/activate", response_model=ActivateResponse)
def deactivate_all() -> ActivateResponse:
    """Deactivate all activations. Clears all IP-scenario bindings and rule overrides."""
    manager = _get_manager()
    count = manager.deactivate_all()
    if count > 0:
        return ActivateResponse(ok=True, message=f"Deactivated all activations ({count} IPs cleared)")
    return ActivateResponse(ok=True, message="No activations to clear")


@app.get("/api/activate")
def list_activations() -> dict:
    """List all activations (ip_to_scenario, scenario_rule_overrides)."""
    manager = _get_manager()
    return manager.list_activations()


@app.get("/api/activate/ip/{client_ip}")
def get_activation_for_ip(client_ip: str) -> dict:
    """Get scenario_id and rules for client IP."""
    manager = _get_manager()
    scenario_id = manager.get_scenario_id_by_client_ip(client_ip)
    if not scenario_id:
        raise HTTPException(status_code=404, detail=f"No activation for IP {client_ip}")
    rules = manager.get_intercept_rules_for_client(client_ip)
    return {
        "client_ip": client_ip,
        "scenario_id": scenario_id,
        "rule_count": len(rules),
        "rules": [{"id": r.id, "url_pattern": r.url_pattern} for r in rules],
    }


# --- 规则 CRUD API（编辑器用）---

def _rule_to_dict(r: InterceptRule) -> dict:
    d = r.model_dump() if hasattr(r, "model_dump") else r.dict()
    return d


class RuleCreate(BaseModel):
    """Create rule request."""

    id: Optional[str] = None
    url_pattern: str
    description: Optional[str] = None
    status_code: Optional[int] = None
    body: Optional[str] = None
    use_regex: bool = False
    upstream_host: Optional[str] = None
    upstream_port: Optional[int] = None
    scenario_id: Optional[str] = None


class RuleUpdate(BaseModel):
    """Update rule request - partial."""

    url_pattern: Optional[str] = None
    description: Optional[str] = None
    status_code: Optional[int] = None
    body: Optional[str] = None
    use_regex: Optional[bool] = None
    upstream_host: Optional[str] = None
    upstream_port: Optional[int] = None


class BindRequest(BaseModel):
    scenario_id: str


@app.get("/api/rules/definitions")
def list_rule_definitions() -> List[dict]:
    """List all rule definitions (reuse mode)."""
    manager = _get_manager()
    rules = manager.list_definitions()
    return [_rule_to_dict(r) for r in rules]


@app.get("/api/rules")
def list_rules(scenario_id: Optional[str] = None) -> List[dict]:
    """List rules for scenario (or default)."""
    manager = _get_manager()
    rules = manager.get_intercept_rules(scenario_id)
    return [_rule_to_dict(r) for r in rules]


@app.get("/api/scenarios")
def list_scenarios() -> List[str]:
    """List scenario ids (reuse mode)."""
    manager = _get_manager()
    return manager.list_scenarios()


class ScenarioCreate(BaseModel):
    scenario_id: str


@app.post("/api/scenarios", status_code=201)
def create_scenario_api(req: ScenarioCreate) -> dict:
    """Create new scenario (reuse mode)."""
    manager = _get_manager()
    err = manager.create_scenario(req.scenario_id)
    if err is None:
        return {"ok": True, "scenario_id": req.scenario_id}
    if err == "exists":
        raise HTTPException(status_code=400, detail=f"场景 {req.scenario_id} 已存在")
    raise HTTPException(
        status_code=400,
        detail="需要目录模式：请将 LLM_PROXY_RULES 或 --rules 指向 rules 目录（含 definitions/ 和 scenarios/），而非单文件",
    )


@app.post("/api/rules", status_code=201)
def create_rule(req: RuleCreate) -> dict:
    """Create rule, optionally bind to scenario."""
    manager = _get_manager()
    rid = req.id or f"rule_{len(manager.list_definitions()) + 1}"
    rule = InterceptRule(
        id=rid,
        url_pattern=req.url_pattern,
        description=req.description,
        status_code=req.status_code,
        body=req.body,
        use_regex=req.use_regex,
        upstream_host=req.upstream_host,
        upstream_port=req.upstream_port,
    )
    manager.add_rule(rule, req.scenario_id)
    return _rule_to_dict(rule)


@app.get("/api/rules/{rule_id}")
def get_rule(rule_id: str) -> dict:
    """Get single rule by id (from definitions)."""
    manager = _get_manager()
    rule = manager.get_definition(rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail=f"Rule {rule_id} not found")
    return _rule_to_dict(rule)


@app.put("/api/rules/{rule_id}")
def update_rule(rule_id: str, req: RuleUpdate) -> dict:
    """Update rule definition."""
    manager = _get_manager()
    updates = req.model_dump(exclude_none=True) if hasattr(req, "model_dump") else {k: v for k, v in req.dict().items() if v is not None}
    rule = manager.update_rule(rule_id, updates)
    if not rule:
        raise HTTPException(status_code=404, detail=f"Rule {rule_id} not found")
    return _rule_to_dict(rule)


@app.delete("/api/rules/{rule_id}")
def delete_rule(rule_id: str, scenario_id: Optional[str] = None) -> dict:
    """Delete rule. scenario_id: unbind only. Omit: delete definition."""
    manager = _get_manager()
    if scenario_id:
        if manager.unbind_rule(rule_id, scenario_id):
            return {"ok": True, "message": f"Unbound {rule_id} from {scenario_id}"}
        raise HTTPException(status_code=404, detail=f"Rule {rule_id} not bound to {scenario_id}")
    if manager.remove_rule(rule_id):
        return {"ok": True, "message": f"Deleted rule {rule_id}"}
    raise HTTPException(status_code=404, detail=f"Rule {rule_id} not found")


@app.post("/api/rules/{rule_id}/bind")
def bind_rule_to_scenario(rule_id: str, req: BindRequest) -> dict:
    """Bind rule to scenario."""
    manager = _get_manager()
    if manager.bind_rule(rule_id, req.scenario_id):
        return {"ok": True, "message": f"Bound {rule_id} to {req.scenario_id}"}
    raise HTTPException(status_code=404, detail=f"Rule {rule_id} not found or not in reuse mode")


@app.delete("/api/rules/{rule_id}/bind/{scenario_id}")
def unbind_rule_from_scenario(rule_id: str, scenario_id: str) -> dict:
    """Unbind rule from scenario."""
    manager = _get_manager()
    if manager.unbind_rule(rule_id, scenario_id):
        return {"ok": True, "message": f"Unbound {rule_id} from {scenario_id}"}
    raise HTTPException(status_code=404, detail=f"Rule {rule_id} not bound to {scenario_id}")


# --- 规则编辑器 ---

@app.get("/rules", response_class=HTMLResponse)
@app.get("/editor", response_class=HTMLResponse)
def rule_editor_page() -> HTMLResponse:
    """规则编辑器单页。"""
    if _EDITOR_HTML_PATH.exists():
        return HTMLResponse(content=_EDITOR_HTML_PATH.read_text(encoding="utf-8"))
    raise HTTPException(status_code=404, detail="Editor not found")


# --- 证书安装 ---

@app.get("/certificate", response_class=HTMLResponse)
def certificate_install_page() -> HTMLResponse:
    """证书安装说明页，含各平台下载链接。设备配置代理后访问此页面下载证书。"""
    cert_dir = _get_cert_dir()
    cer_path = cert_dir / "mitmproxy-ca-cert.cer"
    pem_path = cert_dir / "mitmproxy-ca-cert.pem"
    has_cer = cer_path.exists()
    has_pem = pem_path.exists()
    if not has_cer and not has_pem:
        html = _cert_error_html("证书尚未生成，请先启动代理 (beacon-proxy start) 后再访问。")
        return HTMLResponse(content=html, status_code=503)

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Beacon Proxy 证书安装</title>
  <style>
    body {{ font-family: -apple-system, sans-serif; max-width: 600px; margin: 2em auto; padding: 0 1em; }}
    h1 {{ font-size: 1.25em; }}
    .btn {{ display: inline-block; margin: 0.5em 0.5em 0.5em 0; padding: 0.6em 1.2em; background: #007aff; color: white; text-decoration: none; border-radius: 8px; }}
    .btn:hover {{ opacity: 0.9; }}
    .step {{ margin: 1.5em 0; padding-left: 1em; border-left: 3px solid #ddd; }}
    code {{ background: #f5f5f5; padding: 0.2em 0.4em; border-radius: 4px; }}
  </style>
</head>
<body>
  <h1>Beacon Proxy 证书安装</h1>
  <p>请根据设备类型下载并安装证书，用于 HTTPS 流量拦截。</p>

  <h2>下载证书</h2>
  <p>
    {_cert_link("cer", "iOS / 通用 (.cer)") if has_cer else ""}
    {_cert_link("pem", "Android / curl (.pem)") if has_pem else ""}
  </p>

  <h2>iOS 安装步骤</h2>
  <div class="step">
    <p>1. 点击上方「iOS / 通用 (.cer)」下载</p>
    <p>2. 安装描述文件（设置 → 已下载描述文件）</p>
    <p>3. <strong>重要</strong>：设置 → 通用 → 关于本机 → 证书信任设置 → 启用「mitmproxy」信任</p>
  </div>

  <h2>Android 安装步骤</h2>
  <div class="step">
    <p>1. 下载 .pem 文件</p>
    <p>2. 设置 → 安全 → 安装证书 → 选择 CA 证书</p>
  </div>

  <p style="color:#666; font-size:0.9em;">证书路径：<code>{cert_dir}</code></p>
</body>
</html>"""
    return HTMLResponse(content=html)


@app.get("/certificate/download")
def certificate_download(format: str = "cer"):
    """下载证书文件。format: cer (iOS) 或 pem (Android/curl)。"""
    cert_dir = _get_cert_dir()
    if format == "cer":
        path = cert_dir / "mitmproxy-ca-cert.cer"
        media_type = "application/x-x509-ca-cert"
        filename = "mitmproxy-ca-cert.cer"
    elif format == "pem":
        path = cert_dir / "mitmproxy-ca-cert.pem"
        media_type = "application/x-pem-file"
        filename = "mitmproxy-ca-cert.pem"
    else:
        raise HTTPException(status_code=400, detail="format 必须是 cer 或 pem")
    if not path.exists():
        raise HTTPException(status_code=404, detail="证书文件不存在，请先启动代理")
    return FileResponse(path=path, media_type=media_type, filename=filename)


def _cert_link(fmt: str, label: str) -> str:
    return f'<a class="btn" href="/certificate/download?format={fmt}">{label}</a>'


def _cert_error_html(msg: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="UTF-8"><title>证书安装</title></head>
<body><h1>Beacon Proxy</h1><p>{msg}</p></body>
</html>"""


def run_api_server(host: str = "127.0.0.1", port: int = 8765) -> None:
    """Run API server. Use with: beacon-proxy api"""
    import uvicorn
    uvicorn.run(app, host=host, port=port)
