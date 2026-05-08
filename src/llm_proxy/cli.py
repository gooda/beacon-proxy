"""CLI for proxy service - automation use."""

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import typer

from llm_proxy.manager.file_based import FileBasedManager
from llm_proxy.models import InterceptRule, NetworkCondition, ProxyConfig, RemoteApiCall

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
    body_file: Optional[str] = typer.Option(None, "--body-file", help="Read response body from file"),
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
        body_file=body_file,
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
    web: bool = typer.Option(False, "--web", help="Use mitmweb (browser UI) instead of mitmdump"),
    web_port: int = typer.Option(8081, "--web-port", help="mitmweb UI port (when --web)"),
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
    proxy_cmd = "mitmweb" if web else "mitmdump"
    cmd = [proxy_cmd, "-s", str(addon_path), "-p", str(port)]
    if web:
        cmd.extend(["--web-port", str(web_port), "--web-host", "0.0.0.0", "--no-web-open-browser"])
        typer.echo(f"mitmweb UI: http://0.0.0.0:{web_port}")
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


# --- 激活管理 ---


@app.command()
def activate(
    scenario_id: str = typer.Argument(..., help="场景 ID"),
    client_ip: str = typer.Argument(..., help="客户端 IP（被测设备）"),
    rule_ids: Optional[str] = typer.Option(None, "--rule-ids", help="覆盖场景规则，逗号分隔"),
    rules_file: Optional[str] = typer.Option(None, "--rules", help="Rules 路径"),
) -> None:
    """激活：将客户端 IP 与场景绑定（写入 activations.yaml）。"""
    manager = _get_manager(rules_file)
    rids = [s.strip() for s in rule_ids.split(",") if s.strip()] if rule_ids else None
    manager.activate(scenario_id, client_ip, rids)
    extra = f" (rule_ids={rids})" if rids else ""
    typer.echo(f"Activated {client_ip} -> {scenario_id}{extra}")


@app.command()
def deactivate(
    scenario_id: Optional[str] = typer.Option(None, "--scenario", "-s", help="按场景取消"),
    client_ip: Optional[str] = typer.Option(None, "--ip", "-i", help="按 IP 取消"),
    all: bool = typer.Option(False, "--all", help="清除所有激活"),
    rules_file: Optional[str] = typer.Option(None, "--rules", help="Rules 路径"),
) -> None:
    """取消激活。--scenario / --ip / --all 三选一。"""
    if sum(bool(x) for x in (scenario_id, client_ip, all)) != 1:
        typer.echo("必须且只能指定 --scenario / --ip / --all 之一", err=True)
        raise typer.Exit(2)
    manager = _get_manager(rules_file)
    if all:
        n = manager.deactivate_all()
        typer.echo(f"Cleared all activations ({n} IPs)")
    elif manager.deactivate(scenario_id=scenario_id, client_ip=client_ip):
        target = f"scenario {scenario_id}" if scenario_id else f"IP {client_ip}"
        typer.echo(f"Deactivated {target}")
    else:
        target = f"scenario {scenario_id}" if scenario_id else f"IP {client_ip}"
        typer.echo(f"{target} not found in activations", err=True)
        raise typer.Exit(1)


@app.command("list-activations")
def list_activations(
    rules_file: Optional[str] = typer.Option(None, "--rules", help="Rules 路径"),
) -> None:
    """列出所有激活（IP↔场景映射）。"""
    manager = _get_manager(rules_file)
    acts = manager.list_activations()
    ips = acts.get("ip_to_scenario", {}) or {}
    overrides = acts.get("scenario_rule_overrides", {}) or {}
    if not ips:
        typer.echo("No activations")
        return
    typer.echo("Activations:")
    for ip, sid in ips.items():
        ov = overrides.get(sid)
        suffix = f"  rule_ids={ov}" if ov else ""
        typer.echo(f"  {ip} -> {sid}{suffix}")


# --- 网络条件 ---

_NET_PRESETS: Dict[str, Dict[str, Any]] = {
    "airplane": {"airplane_mode": True},
    "3g":       {"delay_ms": 400, "throttle_kbps": 50, "packet_loss_rate": 0.02},
    "4g":       {"delay_ms": 150, "throttle_kbps": 200, "packet_loss_rate": 0.01},
    "latency":  {"delay_ms": 2000},
}


@app.command("set-net-condition")
def set_net_condition(
    client_ip: str = typer.Argument(..., help="客户端 IP"),
    preset: Optional[str] = typer.Option(None, "--preset", help="预设：airplane / 3g / 4g / latency"),
    airplane: bool = typer.Option(False, "--airplane", help="飞行模式"),
    delay_ms: Optional[int] = typer.Option(None, "--delay", help="延迟(ms)"),
    throttle_kbps: Optional[int] = typer.Option(None, "--throttle", help="限速(KB/s)"),
    packet_loss_rate: Optional[float] = typer.Option(None, "--loss", help="丢包率 0.0-1.0"),
    rules_file: Optional[str] = typer.Option(None, "--rules", help="Rules 路径"),
) -> None:
    """为客户端 IP 设置网络条件（写入 activations.yaml）。"""
    fields: Dict[str, Any] = {}
    if preset:
        if preset not in _NET_PRESETS:
            typer.echo(f"未知 preset: {preset}（可选：{', '.join(_NET_PRESETS)}）", err=True)
            raise typer.Exit(2)
        fields.update(_NET_PRESETS[preset])
    if airplane:
        fields["airplane_mode"] = True
    if delay_ms is not None: fields["delay_ms"] = delay_ms
    if throttle_kbps is not None: fields["throttle_kbps"] = throttle_kbps
    if packet_loss_rate is not None: fields["packet_loss_rate"] = packet_loss_rate
    if not fields:
        typer.echo("请提供 --preset 或 --airplane / --delay / --throttle / --loss 至少一项", err=True)
        raise typer.Exit(2)
    manager = _get_manager(rules_file)
    manager.set_network_condition(client_ip, NetworkCondition(**fields))
    typer.echo(f"Set network condition for {client_ip}: {fields}")


@app.command("clear-net-condition")
def clear_net_condition(
    client_ip: Optional[str] = typer.Option(None, "--ip", "-i", help="按 IP 清除"),
    all: bool = typer.Option(False, "--all", help="清除所有 IP 的网络条件"),
    rules_file: Optional[str] = typer.Option(None, "--rules", help="Rules 路径"),
) -> None:
    """清除网络条件。--ip 或 --all 二选一。"""
    if sum(bool(x) for x in (client_ip, all)) != 1:
        typer.echo("必须且只能指定 --ip 或 --all", err=True)
        raise typer.Exit(2)
    manager = _get_manager(rules_file)
    if all:
        conditions = manager.list_network_conditions()
        for ip in list(conditions.keys()):
            manager.clear_network_condition(ip)
        typer.echo(f"Cleared {len(conditions)} network conditions")
    elif manager.clear_network_condition(client_ip):
        typer.echo(f"Cleared network condition for {client_ip}")
    else:
        typer.echo(f"No network condition for {client_ip}", err=True)
        raise typer.Exit(1)


@app.command("list-net-conditions")
def list_net_conditions(
    rules_file: Optional[str] = typer.Option(None, "--rules", help="Rules 路径"),
) -> None:
    """列出所有客户端的网络条件。"""
    manager = _get_manager(rules_file)
    conditions = manager.list_network_conditions()
    if not conditions:
        typer.echo("No network conditions")
        return
    typer.echo("Network conditions:")
    for ip, c in conditions.items():
        d = c.model_dump() if hasattr(c, "model_dump") else c.dict()
        nonnull = {k: v for k, v in d.items() if v not in (None, False)}
        typer.echo(f"  {ip}: {nonnull}")


# --- 自然语言生成规则 / 网络条件 ---


@app.command()
def generate(
    requirement: str = typer.Argument(..., help="自然语言需求，如：登录失败 / 弱网3G / 飞行模式"),
    scenario_id: str = typer.Option("default", "--scenario", "-s", help="场景 ID"),
    client_ip: str = typer.Option(..., "--ip", "-i", help="客户端 IP（用于激活）"),
    rules_file: Optional[str] = typer.Option(None, "--rules", help="Rules 路径"),
) -> None:
    """根据自然语言需求生成规则或网络条件，并激活到 IP。"""
    from llm_proxy.generator import generate_network_condition, generate_rules_from_requirement
    manager = _get_manager(rules_file)
    condition = generate_network_condition(requirement)
    if condition:
        manager.set_network_condition(client_ip, condition)
        typer.echo(f"Set network condition for {client_ip}: {requirement}")
        return
    rules = generate_rules_from_requirement(requirement)
    if not rules:
        typer.echo(f"无法解析需求：{requirement}", err=True)
        raise typer.Exit(1)
    rule_ids: List[str] = []
    for rule in rules:
        manager.add_rule(rule, scenario_id)
        rule_ids.append(rule.id)
    manager.activate(scenario_id, client_ip, rule_ids)
    typer.echo(f"Generated {len(rule_ids)} rule(s) and activated: {scenario_id} -> {client_ip}")
    for rid in rule_ids:
        typer.echo(f"  {rid}")


# --- 远端调用 ---

remote_call_app = typer.Typer(help="远端 API 调用管理与触发")
app.add_typer(remote_call_app, name="remote-call")


def _parse_kv(items: Optional[List[str]]) -> Optional[Dict[str, str]]:
    """Parse list of K=V strings into dict. None if items is None or empty."""
    if not items:
        return None
    out: Dict[str, str] = {}
    for it in items:
        if "=" not in it:
            raise typer.BadParameter(f"必须是 K=V 形式：{it}")
        k, v = it.split("=", 1)
        out[k.strip()] = v
    return out or None


def _parse_body(body: Optional[str], body_type: str) -> Any:
    if body is None:
        return None
    if body_type == "json":
        try:
            return json.loads(body)
        except json.JSONDecodeError as e:
            raise typer.BadParameter(f"--body 不是合法 JSON：{e}")
    return body


@remote_call_app.command("add")
def remote_call_add(
    call_id: str = typer.Argument(..., help="调用 ID，如 reset_login"),
    url: str = typer.Option(..., "--url", "-u", help="完整 URL，支持 {{var}} 模板"),
    method: str = typer.Option("GET", "--method", "-X", help="HTTP 方法"),
    description: Optional[str] = typer.Option(None, "--description", "-D"),
    header: Optional[List[str]] = typer.Option(None, "--header", "-H", help="K=V，可重复"),
    query: Optional[List[str]] = typer.Option(None, "--query", "-q", help="K=V，可重复"),
    body: Optional[str] = typer.Option(None, "--body", "-b", help="请求体（json 类型时需为合法 JSON）"),
    body_type: str = typer.Option("json", "--body-type", help="json / text / form"),
    timeout_ms: int = typer.Option(10000, "--timeout", help="超时 ms"),
    rules_file: Optional[str] = typer.Option(None, "--rules", help="Rules 路径"),
) -> None:
    """新增远端调用定义。"""
    manager = _get_manager(rules_file)
    if manager.get_remote_call(call_id):
        typer.echo(f"Remote call {call_id} 已存在，使用 update 命令", err=True)
        raise typer.Exit(1)
    call = RemoteApiCall(
        id=call_id,
        description=description,
        method=method.upper(),
        url=url,
        headers=_parse_kv(header),
        query_params=_parse_kv(query),
        body=_parse_body(body, body_type),
        body_type=body_type,
        timeout_ms=timeout_ms,
    )
    manager.save_remote_call(call)
    typer.echo(f"Added remote call {call_id}: {method.upper()} {url}")


@remote_call_app.command("update")
def remote_call_update(
    call_id: str = typer.Argument(..., help="调用 ID"),
    url: Optional[str] = typer.Option(None, "--url", "-u"),
    method: Optional[str] = typer.Option(None, "--method", "-X"),
    description: Optional[str] = typer.Option(None, "--description", "-D"),
    header: Optional[List[str]] = typer.Option(None, "--header", "-H", help="K=V，可重复（覆盖整个 headers）"),
    query: Optional[List[str]] = typer.Option(None, "--query", "-q", help="K=V，可重复（覆盖整个 query_params）"),
    body: Optional[str] = typer.Option(None, "--body", "-b"),
    body_type: Optional[str] = typer.Option(None, "--body-type"),
    timeout_ms: Optional[int] = typer.Option(None, "--timeout"),
    rules_file: Optional[str] = typer.Option(None, "--rules", help="Rules 路径"),
) -> None:
    """部分更新远端调用定义。仅更新提供的字段。"""
    manager = _get_manager(rules_file)
    existing = manager.get_remote_call(call_id)
    if not existing:
        typer.echo(f"Remote call {call_id} 不存在", err=True)
        raise typer.Exit(1)
    d = existing.model_dump() if hasattr(existing, "model_dump") else existing.dict()
    if url is not None: d["url"] = url
    if method is not None: d["method"] = method.upper()
    if description is not None: d["description"] = description
    if header is not None: d["headers"] = _parse_kv(header)
    if query is not None: d["query_params"] = _parse_kv(query)
    if body_type is not None: d["body_type"] = body_type
    if body is not None: d["body"] = _parse_body(body, d["body_type"])
    if timeout_ms is not None: d["timeout_ms"] = timeout_ms
    updated = RemoteApiCall(**d)
    manager.save_remote_call(updated)
    typer.echo(f"Updated remote call {call_id}")


@remote_call_app.command("list")
def remote_call_list(
    rules_file: Optional[str] = typer.Option(None, "--rules", help="Rules 路径"),
) -> None:
    """列出所有远端调用定义。"""
    manager = _get_manager(rules_file)
    calls = manager.list_remote_calls()
    if not calls:
        typer.echo("No remote calls")
        return
    typer.echo("Remote calls:")
    for c in calls:
        desc = f" ({c.description})" if c.description else ""
        typer.echo(f"  {c.id}: {c.method} {c.url}{desc}")


@remote_call_app.command("get")
def remote_call_get(
    call_id: str = typer.Argument(..., help="调用 ID"),
    rules_file: Optional[str] = typer.Option(None, "--rules", help="Rules 路径"),
) -> None:
    """查看单个远端调用定义。"""
    manager = _get_manager(rules_file)
    c = manager.get_remote_call(call_id)
    if not c:
        typer.echo(f"Remote call {call_id} not found", err=True)
        raise typer.Exit(1)
    d = c.model_dump() if hasattr(c, "model_dump") else c.dict()
    typer.echo(json.dumps(d, indent=2, ensure_ascii=False))


@remote_call_app.command("delete")
def remote_call_delete(
    call_id: str = typer.Argument(..., help="调用 ID"),
    rules_file: Optional[str] = typer.Option(None, "--rules", help="Rules 路径"),
) -> None:
    """删除远端调用定义。"""
    manager = _get_manager(rules_file)
    if manager.delete_remote_call(call_id):
        typer.echo(f"Deleted remote call {call_id}")
    else:
        typer.echo(f"Remote call {call_id} not found", err=True)
        raise typer.Exit(1)


def _api_post(api_url: str, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    import httpx
    try:
        r = httpx.post(api_url.rstrip("/") + path, json=payload, timeout=30)
    except httpx.HTTPError as e:
        typer.echo(f"无法连接到 API ({api_url})：{e}", err=True)
        raise typer.Exit(2)
    if r.status_code >= 400:
        typer.echo(f"HTTP {r.status_code}: {r.text}", err=True)
        raise typer.Exit(1)
    return r.json()


def _api_get(api_url: str, path: str) -> Dict[str, Any]:
    import httpx
    try:
        r = httpx.get(api_url.rstrip("/") + path, timeout=30)
    except httpx.HTTPError as e:
        typer.echo(f"无法连接到 API ({api_url})：{e}", err=True)
        raise typer.Exit(2)
    if r.status_code >= 400:
        typer.echo(f"HTTP {r.status_code}: {r.text}", err=True)
        raise typer.Exit(1)
    return r.json()


@remote_call_app.command("invoke")
def remote_call_invoke(
    call_id: str = typer.Argument(..., help="调用 ID"),
    var: Optional[List[str]] = typer.Option(None, "--var", "-v", help="模板变量 K=V，可重复"),
    client_ip: Optional[str] = typer.Option(None, "--client-ip", help="设备 IP（用于 device.* 上下文）"),
    timeout_ms: Optional[int] = typer.Option(None, "--timeout", help="覆盖定义里的超时"),
    async_mode: bool = typer.Option(False, "--async", help="异步触发，立即返回 call_id"),
    api_url: str = typer.Option("http://127.0.0.1:8765", "--api-url", help="API 服务地址"),
) -> None:
    """触发远端调用。走 HTTP（device 上下文与 async 在 server 侧）。"""
    payload: Dict[str, Any] = {}
    variables = _parse_kv(var)
    if variables: payload["variables"] = variables
    if client_ip: payload["client_ip"] = client_ip
    if timeout_ms is not None: payload["timeout_ms"] = timeout_ms
    mode = "async" if async_mode else "sync"
    result = _api_post(api_url, f"/api/remote-calls/{call_id}/invoke?mode={mode}", payload)
    typer.echo(json.dumps(result, indent=2, ensure_ascii=False))


@remote_call_app.command("calls")
def remote_call_calls(
    limit: int = typer.Option(20, "--limit", "-n", help="返回最近 N 条"),
    api_url: str = typer.Option("http://127.0.0.1:8765", "--api-url", help="API 服务地址"),
) -> None:
    """列出最近调用记录（来自 API 进程的内存 buffer）。"""
    items = _api_get(api_url, f"/api/remote-calls/calls?limit={limit}")
    if not items:
        typer.echo("No call records")
        return
    for r in items:
        line = f"  {r['call_id']} · {r['status']}"
        if r.get("status_code"): line += f" · HTTP {r['status_code']}"
        if r.get("duration_ms") is not None: line += f" · {r['duration_ms']}ms"
        if r.get("error"): line += f" · {r['error']}"
        typer.echo(line)
        if r.get("request_url"):
            typer.echo(f"      {r['request_url']}")


@remote_call_app.command("get-call")
def remote_call_get_call(
    call_id: str = typer.Argument(..., help="call_id（rc_ 开头）"),
    api_url: str = typer.Option("http://127.0.0.1:8765", "--api-url", help="API 服务地址"),
) -> None:
    """查询单次调用结果（async 轮询用）。"""
    result = _api_get(api_url, f"/api/remote-calls/calls/{call_id}")
    typer.echo(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    app()
