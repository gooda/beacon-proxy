"""CLI for proxy service - automation use."""

import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

import typer

from llm_proxy.manager.file_based import FileBasedManager
from llm_proxy.models import InterceptRule, ProxyConfig

app = typer.Typer(help="Beacon Proxy - UI automation testing proxy")


def _get_manager(rules_path: Optional[str] = None) -> FileBasedManager:
    path = rules_path or os.environ.get("LLM_PROXY_RULES", "rules.yaml")
    return FileBasedManager(path, ProxyConfig())


@app.command()
def add_rule(
    url_pattern: str = typer.Argument(..., help="URL pattern to match"),
    rule_id: Optional[str] = typer.Option(None, "--id", "-i", help="Rule id (default: auto)"),
    description: Optional[str] = typer.Option(None, "--description", "-D", help="Rule description"),
    status_code: Optional[int] = typer.Option(None, "--status", "-s", help="Override status code"),
    body: Optional[str] = typer.Option(None, "--body", "-b", help="Override response body"),
    regex: bool = typer.Option(False, "--regex", "-r", help="url_pattern is regex"),
    device_id: Optional[str] = typer.Option(None, "--device-id", "-d", help="Bind to device (reuse mode)"),
    rules_file: Optional[str] = typer.Option(None, "--rules", help="Rules file or directory path"),
) -> None:
    """Add an intercept rule. In reuse mode (rules dir): creates definition, optionally binds to device."""
    manager = _get_manager(rules_file)
    rules = manager.get_intercept_rules(device_id)
    rid = rule_id or f"rule_{len(rules) + 1}"
    rule = InterceptRule(
        id=rid,
        url_pattern=url_pattern,
        description=description,
        status_code=status_code,
        body=body,
        use_regex=regex,
    )
    manager.add_rule(rule, device_id)
    target = f" (device={device_id})" if device_id else ""
    typer.echo(f"Added rule {rid}: {url_pattern}{target}")


@app.command()
def remove_rule(
    rule_id: str = typer.Argument(..., help="Rule id to remove"),
    device_id: Optional[str] = typer.Option(None, "--device-id", "-d", help="Unbind from device only (reuse mode). Omit to delete definition."),
    rules_file: Optional[str] = typer.Option(None, "--rules", help="Rules file or directory path"),
) -> None:
    """Remove an intercept rule. With --device-id: unbind from device. Without: delete definition."""
    manager = _get_manager(rules_file)
    if manager.remove_rule(rule_id, device_id):
        typer.echo(f"Removed rule {rule_id}")
    else:
        typer.echo(f"Rule {rule_id} not found", err=True)
        raise typer.Exit(1)


@app.command()
def bind_rule(
    rule_id: str = typer.Argument(..., help="Rule id to bind"),
    device_id: str = typer.Argument(..., help="Device id"),
    rules_file: Optional[str] = typer.Option(None, "--rules", help="Rules directory path"),
) -> None:
    """Bind a rule definition to a device (reuse mode only)."""
    manager = _get_manager(rules_file)
    if manager.bind_rule(rule_id, device_id):
        typer.echo(f"Bound {rule_id} to {device_id}")
    else:
        typer.echo(f"Failed: rule {rule_id} not found or not in reuse mode", err=True)
        raise typer.Exit(1)


@app.command()
def unbind_rule(
    rule_id: str = typer.Argument(..., help="Rule id to unbind"),
    device_id: str = typer.Argument(..., help="Device id"),
    rules_file: Optional[str] = typer.Option(None, "--rules", help="Rules directory path"),
) -> None:
    """Unbind a rule from a device (reuse mode only)."""
    manager = _get_manager(rules_file)
    if manager.unbind_rule(rule_id, device_id):
        typer.echo(f"Unbound {rule_id} from {device_id}")
    else:
        typer.echo(f"Rule {rule_id} not bound to {device_id}", err=True)
        raise typer.Exit(1)


@app.command()
def list_definitions(
    rules_file: Optional[str] = typer.Option(None, "--rules", help="Rules directory path"),
) -> None:
    """List all rule definitions (reuse mode only)."""
    manager = _get_manager(rules_file)
    rules = manager.list_definitions()
    if not rules:
        typer.echo("No definitions")
        return
    typer.echo("Definitions:")
    for r in rules:
        desc = f" ({r.description})" if r.description else ""
        typer.echo(f"  {r.id}: {r.url_pattern} -> status={r.status_code}, body={r.body is not None}{desc}")


@app.command()
def list_rules(
    device_id: Optional[str] = typer.Option(None, "--device-id", "-d", help="Device id for per-device rules"),
    rules_file: Optional[str] = typer.Option(None, "--rules", help="Rules file or directory path"),
) -> None:
    """List intercept rules for device (or default)."""
    manager = _get_manager(rules_file)
    rules = manager.get_intercept_rules(device_id)
    if not rules:
        typer.echo("No rules")
        return
    header = f" (device={device_id})" if device_id else ""
    typer.echo(f"Rules{header}:")
    for r in rules:
        desc = f" ({r.description})" if r.description else ""
        typer.echo(f"  {r.id}: {r.url_pattern} -> status={r.status_code}, body={r.body is not None}{desc}")


@app.command()
def api(
    port: int = typer.Option(8765, "--port", "-p", help="API server port"),
    host: str = typer.Option("127.0.0.1", "--host", "-H", help="API server host"),
    rules_file: Optional[str] = typer.Option(None, "--rules", help="Rules file or directory path"),
) -> None:
    """Start activation API server. UI automation calls this to activate device rules by IP."""
    path = rules_file or os.environ.get("LLM_PROXY_RULES", "rules.yaml")
    env = os.environ.copy()
    env["LLM_PROXY_RULES"] = str(Path(path).absolute())
    try:
        from llm_proxy.api_server import run_api_server
        run_api_server(host=host, port=port)
    except ImportError as e:
        typer.echo("API dependencies not installed. Run: pip install fastapi uvicorn", err=True)
        raise typer.Exit(1) from e


@app.command()
def mcp(
    rules_file: Optional[str] = typer.Option(None, "--rules", help="Rules file path"),
) -> None:
    """Start MCP server for interactive debugging. Requires: pip install mcp"""
    path = rules_file or os.environ.get("LLM_PROXY_RULES", "rules.yaml")
    os.environ["LLM_PROXY_RULES"] = str(Path(path).absolute())
    try:
        from llm_proxy.mcp_server import run_mcp_server
        run_mcp_server()
    except ImportError as e:
        typer.echo("MCP not installed. Run: pip install 'beacon-proxy[mcp]' or pip install mcp", err=True)
        raise typer.Exit(1) from e


@app.command()
def start(
    port: int = typer.Option(8080, "--port", "-p", help="Proxy port"),
    with_api: bool = typer.Option(False, "--with-api", help="Also start activation API server"),
    api_port: int = typer.Option(8765, "--api-port", help="API server port (when --with-api)"),
    rules_file: Optional[str] = typer.Option(None, "--rules", help="Rules file path"),
) -> None:
    """Start the proxy server."""
    path = rules_file or os.environ.get("LLM_PROXY_RULES", "rules.yaml")
    env = os.environ.copy()
    env["LLM_PROXY_RULES"] = str(Path(path).absolute())
    src_dir = str(Path(__file__).parent.parent)
    env["PYTHONPATH"] = src_dir + os.pathsep + env.get("PYTHONPATH", "")

    if with_api:
        import threading
        from llm_proxy.api_server import run_api_server
        def run_api():
            run_api_server(host="127.0.0.1", port=api_port)
        t = threading.Thread(target=run_api, daemon=True)
        t.start()
        typer.echo(f"API server started at http://127.0.0.1:{api_port}")

    addon_path = Path(__file__).parent / "run_addon.py"
    # mitmdump: headless proxy (mitmproxy 9+ has no python -m mitmproxy)
    subprocess.run(
        ["mitmdump", "-s", str(addon_path), "-p", str(port)],
        env=env,
    )


if __name__ == "__main__":
    app()
