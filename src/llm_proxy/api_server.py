"""REST API for activation - UI automation calls to activate device rules."""

import os
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel, Field

from llm_proxy.generator import generate_rules_from_requirement
from llm_proxy.manager.file_based import FileBasedManager
from llm_proxy.models import InterceptRule, ProxyConfig

app = FastAPI(title="Beacon Proxy API", version="0.1.0")


def _get_cert_dir() -> Path:
    """mitmproxy 证书目录，默认 ~/.mitmproxy"""
    return Path(os.environ.get("BEACON_PROXY_CONFDIR", os.path.expanduser("~/.mitmproxy")))


def _get_manager() -> FileBasedManager:
    path = os.environ.get("LLM_PROXY_RULES", "rules.yaml")
    return FileBasedManager(path, ProxyConfig())


class ActivateRequest(BaseModel):
    device_id: str
    client_ip: str
    rule_ids: Optional[List[str]] = None


class ActivateResponse(BaseModel):
    ok: bool
    message: str


class GenerateRequest(BaseModel):
    """根据代理需求生成规则并生效。"""

    requirement: str = Field(..., description="自然语言需求，如：登录失败、购物车空、/api/xxx 返回 500")
    device_id: str = Field(default="default", description="设备 ID")
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
        manager.add_rule(rule, req.device_id)
        rule_ids.append(rule.id)

    manager.activate(req.device_id, req.client_ip, rule_ids)
    return GenerateResponse(
        ok=True,
        message=f"已生成 {len(rule_ids)} 条规则并激活：{req.device_id} -> {req.client_ip}",
        rule_ids=rule_ids,
    )


@app.post("/api/activate", response_model=ActivateResponse)
def activate(req: ActivateRequest) -> ActivateResponse:
    """Activate device rules for client IP. UI automation calls this before running tests."""
    manager = _get_manager()
    manager.activate(req.device_id, req.client_ip, req.rule_ids)
    rules_desc = f" rules {req.rule_ids}" if req.rule_ids else ""
    return ActivateResponse(
        ok=True,
        message=f"Activated device {req.device_id} for IP {req.client_ip}{rules_desc}",
    )


@app.delete("/api/activate/{device_id}", response_model=ActivateResponse)
def deactivate_by_device(device_id: str) -> ActivateResponse:
    """Deactivate all activations for device."""
    manager = _get_manager()
    if manager.deactivate(device_id=device_id):
        return ActivateResponse(ok=True, message=f"Deactivated device {device_id}")
    raise HTTPException(status_code=404, detail=f"Device {device_id} not found in activations")


@app.delete("/api/activate/ip/{client_ip}", response_model=ActivateResponse)
def deactivate_by_ip(client_ip: str) -> ActivateResponse:
    """Deactivate activation for client IP."""
    manager = _get_manager()
    if manager.deactivate(client_ip=client_ip):
        return ActivateResponse(ok=True, message=f"Deactivated IP {client_ip}")
    raise HTTPException(status_code=404, detail=f"IP {client_ip} not found in activations")


@app.get("/api/activate")
def list_activations() -> dict:
    """List all activations (ip_to_device, device_rule_overrides)."""
    manager = _get_manager()
    return manager.list_activations()


@app.get("/api/activate/ip/{client_ip}")
def get_activation_for_ip(client_ip: str) -> dict:
    """Get device_id and rules for client IP."""
    manager = _get_manager()
    device_id = manager.get_device_id_by_client_ip(client_ip)
    if not device_id:
        raise HTTPException(status_code=404, detail=f"No activation for IP {client_ip}")
    rules = manager.get_intercept_rules_for_client(client_ip)
    return {
        "client_ip": client_ip,
        "device_id": device_id,
        "rule_count": len(rules),
        "rules": [{"id": r.id, "url_pattern": r.url_pattern} for r in rules],
    }


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
