"""CLI for proxy service - automation use."""

import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

import typer

from llm_proxy.manager.file_based import FileBasedManager
from llm_proxy.models import InterceptRule, ProxyConfig

# 默认忽略的系统/分析域名（隧道转发，不解密），减少无意义的拦截
DEFAULT_IGNORE_SYSTEM = [
    r".*\.icloud\.com",           # Apple iCloud
    r".*\.apple\.com",            # Apple 系统
    r".*\.itunes\.apple\.com",    # App Store
    r".*sentry.*",               # Sentry 错误上报
    r".*collect.*",              # 通用采集/埋点
    r".*metric.*",               # 指标上报
    r".*analytics.*",            # 分析
    r".*telemetry.*",            # 遥测
    r"httpdns\..*",              # HTTPDNS
    r".*\.googletagmanager\.com",
    r".*\.google-analytics\.com",
    r".*\.firebaseio\.com",
    r"statistic\.live\.126\.net",  # 网易统计
    r"c\.ws\.126\.net",           # 网易采集
    r"mam\.netease\.com",         # 网易指标
    r"nstool\.netease\.com",      # 网易网络工具
]

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
    upstream_host: Optional[str] = typer.Option(None, "--upstream-host", help="Rewrite to this host (A域名->B域名)"),
    upstream_port: Optional[int] = typer.Option(None, "--upstream-port", help="Target port (default 443/80)"),
    scenario_id: Optional[str] = typer.Option(None, "--scenario-id", "-d", help="Bind to scenario (reuse mode)"),
    rules_file: Optional[str] = typer.Option(None, "--rules", help="Rules file or directory path"),
) -> None:
    """Add an intercept rule. In reuse mode (rules dir): creates definition, optionally binds to device."""
    manager = _get_manager(rules_file)
    rules = manager.get_intercept_rules(scenario_id)
    rid = rule_id or f"rule_{len(rules) + 1}"
    rule = InterceptRule(
        id=rid,
        url_pattern=url_pattern,
        description=description,
        status_code=status_code,
        body=body,
        use_regex=regex,
        upstream_host=upstream_host,
        upstream_port=upstream_port,
    )
    manager.add_rule(rule, scenario_id)
    target = f" (scenario={scenario_id})" if scenario_id else ""
    typer.echo(f"Added rule {rid}: {url_pattern}{target}")


@app.command("add-rewrite")
def add_rewrite(
    from_host: str = typer.Argument(..., help="源域名（A），如 api.prod.example.com"),
    to_host: str = typer.Argument(..., help="目标域名（B），如 api.staging.example.com"),
    rule_id: Optional[str] = typer.Option(None, "--id", "-i", help="Rule id (default: auto)"),
    port: int = typer.Option(443, "--port", "-p", help="目标端口"),
    scenario_id: Optional[str] = typer.Option(None, "--scenario-id", "-d", help="绑定到场景"),
    rules_file: Optional[str] = typer.Option(None, "--rules", help="Rules file or directory path"),
) -> None:
    """添加域名重写规则：将 A 域名的请求代理转发到 B 域名。"""
    manager = _get_manager(rules_file)
    rules = manager.get_intercept_rules(scenario_id)
    rid = rule_id or f"rewrite_{len(rules) + 1}"
    rule = InterceptRule(
        id=rid,
        url_pattern=from_host,
        description=f"{from_host} -> {to_host}",
        upstream_host=to_host,
        upstream_port=port,
        use_regex=False,
    )
    manager.add_rule(rule, scenario_id)
    target = f" (scenario={scenario_id})" if scenario_id else ""
    typer.echo(f"Added rewrite {rid}: {from_host} -> {to_host}:{port}{target}")


@app.command()
def remove_rule(
    rule_id: str = typer.Argument(..., help="Rule id to remove"),
    scenario_id: Optional[str] = typer.Option(None, "--scenario-id", "-d", help="Unbind from scenario only (reuse mode). Omit to delete definition."),
    rules_file: Optional[str] = typer.Option(None, "--rules", help="Rules file or directory path"),
) -> None:
    """Remove an intercept rule. With --device-id: unbind from device. Without: delete definition."""
    manager = _get_manager(rules_file)
    if manager.remove_rule(rule_id, scenario_id):
        typer.echo(f"Removed rule {rule_id}")
    else:
        typer.echo(f"Rule {rule_id} not found", err=True)
        raise typer.Exit(1)


@app.command()
def bind_rule(
    rule_id: str = typer.Argument(..., help="Rule id to bind"),
    scenario_id: str = typer.Argument(..., help="Scenario id"),
    rules_file: Optional[str] = typer.Option(None, "--rules", help="Rules directory path"),
) -> None:
    """Bind a rule definition to a device (reuse mode only)."""
    manager = _get_manager(rules_file)
    if manager.bind_rule(rule_id, scenario_id):
        typer.echo(f"Bound {rule_id} to {scenario_id}")
    else:
        typer.echo(f"Failed: rule {rule_id} not found or not in reuse mode", err=True)
        raise typer.Exit(1)


@app.command()
def unbind_rule(
    rule_id: str = typer.Argument(..., help="Rule id to unbind"),
    scenario_id: str = typer.Argument(..., help="Scenario id"),
    rules_file: Optional[str] = typer.Option(None, "--rules", help="Rules directory path"),
) -> None:
    """Unbind a rule from a device (reuse mode only)."""
    manager = _get_manager(rules_file)
    if manager.unbind_rule(rule_id, scenario_id):
        typer.echo(f"Unbound {rule_id} from {scenario_id}")
    else:
        typer.echo(f"Rule {rule_id} not bound to {scenario_id}", err=True)
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
        rewrite = f" -> {r.upstream_host}" if r.upstream_host else ""
        typer.echo(f"  {r.id}: {r.url_pattern}{rewrite} -> status={r.status_code}, body={r.body is not None}{desc}")


@app.command()
def list_rules(
    scenario_id: Optional[str] = typer.Option(None, "--scenario-id", "-d", help="Scenario id for per-scenario rules"),
    rules_file: Optional[str] = typer.Option(None, "--rules", help="Rules file or directory path"),
) -> None:
    """List intercept rules for device (or default)."""
    manager = _get_manager(rules_file)
    rules = manager.get_intercept_rules(scenario_id)
    if not rules:
        typer.echo("No rules")
        return
    header = f" (scenario={scenario_id})" if scenario_id else ""
    typer.echo(f"Rules{header}:")
    for r in rules:
        desc = f" ({r.description})" if r.description else ""
        rewrite = f" -> {r.upstream_host}" if r.upstream_host else ""
        typer.echo(f"  {r.id}: {r.url_pattern}{rewrite} -> status={r.status_code}, body={r.body is not None}{desc}")


@app.command()
def api(
    port: int = typer.Option(8765, "--port", "-p", help="API server port"),
    host: str = typer.Option("0.0.0.0", "--host", "-H", help="API bind address (0.0.0.0=remote access, 127.0.0.1=local only)"),
    rules_file: Optional[str] = typer.Option(None, "--rules", help="Rules file or directory path"),
) -> None:
    """Start activation API server. UI automation calls this to activate scenario rules by IP."""
    path = rules_file or os.environ.get("LLM_PROXY_RULES", "rules.yaml")
    env = os.environ.copy()
    env["LLM_PROXY_RULES"] = str(Path(path).absolute())
    try:
        from llm_proxy.api_server import run_api_server
        typer.echo(f"规则编辑器: http://<本机IP>:{port}/rules")
        typer.echo(f"Certificate install: http://{host}:{port}/certificate")
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
    api_host: str = typer.Option("0.0.0.0", "--api-host", help="API bind address (0.0.0.0=remote access, 127.0.0.1=local only)"),
    ssl_insecure: bool = typer.Option(
        False, "--ssl-insecure", "-k",
        help="Skip upstream server cert verification (for IP-direct/HTTPDNS connections)",
    ),
    ignore_hosts: Optional[str] = typer.Option(
        None, "--ignore-hosts",
        help="Regex patterns for hosts to tunnel (no TLS intercept). Use for cert-pinned apps. Example: '.*\\.apple\\.com'",
    ),
    ignore_system: bool = typer.Option(
        True, "--ignore-system/--no-ignore-system",
        help="Ignore common system/analytics domains (iCloud, Sentry, metrics, etc.) - tunnel without intercept",
    ),
    rules_file: Optional[str] = typer.Option(None, "--rules", help="Rules file path"),
) -> None:
    """Start the proxy server."""
    path = rules_file or os.environ.get("LLM_PROXY_RULES", "rules.yaml")
    rules_abs = str(Path(path).absolute())
    os.environ["LLM_PROXY_RULES"] = rules_abs  # API 线程与 mitmdump 子进程均需此变量
    env = os.environ.copy()
    env["LLM_PROXY_RULES"] = rules_abs
    src_dir = str(Path(__file__).parent.parent)
    env["PYTHONPATH"] = src_dir + os.pathsep + env.get("PYTHONPATH", "")

    if with_api:
        import threading
        from llm_proxy.api_server import run_api_server
        def run_api():
            run_api_server(host=api_host, port=api_port)
        t = threading.Thread(target=run_api, daemon=True)
        t.start()
        typer.echo(f"API server: http://{api_host}:{api_port}")
        typer.echo(f"规则编辑器: http://<本机IP>:{api_port}/rules")
        typer.echo(f"证书下载: http://<本机IP>:{api_port}/certificate")

    addon_path = Path(__file__).parent / "run_addon.py"
    cmd = ["mitmdump", "-s", str(addon_path), "-p", str(port)]
    if ssl_insecure:
        cmd.append("-k")
        typer.echo("SSL insecure: upstream cert verification disabled (for IP-direct/HTTPDNS)")

    patterns: list[str] = []
    if ignore_system:
        patterns.extend(DEFAULT_IGNORE_SYSTEM)
        typer.echo("Ignore system: enabled (iCloud, Sentry, metrics, analytics, etc.)")
    if ignore_hosts:
        patterns.extend(p.strip() for p in ignore_hosts.split(",") if p.strip())
        typer.echo(f"Ignore hosts (extra): {ignore_hosts}")
    for pattern in patterns:
        cmd.extend(["--set", f"ignore_hosts={pattern}"])

    subprocess.run(cmd, env=env)


if __name__ == "__main__":
    app()
