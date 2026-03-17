"""REST API for activation - UI automation calls to activate device rules."""

import os
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from llm_proxy.manager.file_based import FileBasedManager
from llm_proxy.models import ProxyConfig

app = FastAPI(title="Beacon Proxy API", version="0.1.0")


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


def run_api_server(host: str = "127.0.0.1", port: int = 8765) -> None:
    """Run API server. Use with: beacon-proxy api"""
    import uvicorn
    uvicorn.run(app, host=host, port=port)
