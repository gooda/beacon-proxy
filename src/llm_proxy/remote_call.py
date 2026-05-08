"""远端 API 调用执行器。

P0：同步执行 + 错误透传。
P1：{{var}} 模板渲染 + variables 注入。
P2：device 上下文（由 api_server 构建后注入 variables）。
P3：async 模式 + 内存调用记录 buffer（100 条 / 10 分钟 TTL）。
"""

from __future__ import annotations

import re
import secrets
import threading
import time
from collections import OrderedDict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import httpx

from llm_proxy.models import RemoteApiCall, RemoteCallResult


MAX_CALL_BUFFER = 100
CALL_TTL_SECONDS = 600
MAX_PENDING = 50


class _CallStore:
    """线程安全的环形 buffer，记录最近调用结果。支持 TTL 过期。"""

    def __init__(self, max_size: int = MAX_CALL_BUFFER, ttl_seconds: int = CALL_TTL_SECONDS):
        self._max_size = max_size
        self._ttl = ttl_seconds
        self._entries: "OrderedDict[str, Tuple[float, RemoteCallResult]]" = OrderedDict()
        self._lock = threading.Lock()
        self._pending = 0

    def _evict(self) -> None:
        now = time.time()
        # TTL expire
        expired = [cid for cid, (ts, _) in self._entries.items() if now - ts > self._ttl]
        for cid in expired:
            del self._entries[cid]
        # Size cap — evict oldest
        while len(self._entries) > self._max_size:
            self._entries.popitem(last=False)

    def put(self, result: RemoteCallResult) -> None:
        with self._lock:
            self._entries[result.call_id] = (time.time(), result)
            self._entries.move_to_end(result.call_id)
            self._evict()

    def update(self, result: RemoteCallResult) -> None:
        """Update existing entry (async result arrival)."""
        with self._lock:
            self._entries[result.call_id] = (time.time(), result)
            self._entries.move_to_end(result.call_id)
            self._evict()

    def get(self, call_id: str) -> Optional[RemoteCallResult]:
        with self._lock:
            self._evict()
            entry = self._entries.get(call_id)
            return entry[1] if entry else None

    def list(self, limit: int = 100) -> List[RemoteCallResult]:
        with self._lock:
            self._evict()
            items = list(self._entries.values())
        items.sort(key=lambda x: x[0], reverse=True)
        return [r for _, r in items[:limit]]

    def inc_pending(self) -> bool:
        """Reserve a pending slot. Returns False if over limit."""
        with self._lock:
            if self._pending >= MAX_PENDING:
                return False
            self._pending += 1
            return True

    def dec_pending(self) -> None:
        with self._lock:
            if self._pending > 0:
                self._pending -= 1


_store = _CallStore()


def get_call(call_id: str) -> Optional[RemoteCallResult]:
    return _store.get(call_id)


def list_calls(limit: int = 100) -> List[RemoteCallResult]:
    return _store.list(limit)


_TEMPLATE_RE = re.compile(r"\{\{\s*([\w.]+)\s*\}\}")


def _gen_call_id() -> str:
    return f"rc_{secrets.token_hex(4)}"


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _resolve_var(name: str, ctx: Dict[str, Any]) -> Optional[str]:
    """支持点号路径，如 device.client_ip / user.profile.name。返回 None 表示未解析。"""
    cur: Any = ctx
    for part in name.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return None
    if cur is None:
        return None
    return str(cur)


def _render_string(s: str, ctx: Dict[str, Any], unresolved: List[str]) -> str:
    """渲染字符串中的 {{var}}。未解析变量保留原样并记录到 unresolved 列表。"""
    def repl(m: "re.Match[str]") -> str:
        name = m.group(1)
        v = _resolve_var(name, ctx)
        if v is None:
            unresolved.append(name)
            return m.group(0)
        return v
    return _TEMPLATE_RE.sub(repl, s)


def _render_any(value: Any, ctx: Dict[str, Any], unresolved: List[str]) -> Any:
    """递归渲染 dict/list/str。其它类型原样返回。"""
    if isinstance(value, str):
        return _render_string(value, ctx, unresolved)
    if isinstance(value, dict):
        return {k: _render_any(v, ctx, unresolved) for k, v in value.items()}
    if isinstance(value, list):
        return [_render_any(v, ctx, unresolved) for v in value]
    return value


def _render_call(
    call: RemoteApiCall, variables: Optional[Dict[str, Any]]
) -> Tuple[str, Dict[str, str], Dict[str, str], Any, List[str]]:
    """对 url / headers / query / body 做模板渲染，返回 (url, headers, params, body, unresolved)。"""
    ctx: Dict[str, Any] = dict(variables or {})
    unresolved: List[str] = []
    url = _render_string(call.url, ctx, unresolved)
    headers = {k: _render_string(v, ctx, unresolved) for k, v in (call.headers or {}).items()}
    params = {k: _render_string(v, ctx, unresolved) for k, v in (call.query_params or {}).items()}
    body = _render_any(call.body, ctx, unresolved) if call.body is not None else None
    return url, headers, params, body, unresolved


def _execute(
    call: RemoteApiCall,
    variables: Optional[Dict[str, Any]],
    timeout_ms_override: Optional[int],
    call_id: str,
) -> RemoteCallResult:
    """Internal executor used by both sync and async paths."""
    started_at = _iso_now()
    timeout_ms = timeout_ms_override or call.timeout_ms
    timeout_s = timeout_ms / 1000.0

    url, headers, params, body, unresolved = _render_call(call, variables)

    request_kwargs: Dict[str, Any] = {
        "method": call.method,
        "url": url,
        "headers": headers,
        "params": params,
        "timeout": timeout_s,
    }
    if body is not None:
        if call.body_type == "json":
            request_kwargs["json"] = body
        elif call.body_type == "form":
            request_kwargs["data"] = body
        else:
            request_kwargs["content"] = body if isinstance(body, (bytes, str)) else str(body)

    t0 = time.monotonic()
    try:
        with httpx.Client() as client:
            resp = client.request(**request_kwargs)
        duration_ms = int((time.monotonic() - t0) * 1000)
        # 未解析变量提示（不阻断，仅警告）
        warn = (
            f" (unresolved template vars: {sorted(set(unresolved))})" if unresolved else ""
        )
        resp_body: Any
        ctype = resp.headers.get("content-type", "")
        if "application/json" in ctype:
            try:
                resp_body = resp.json()
            except Exception:
                resp_body = resp.text
        else:
            resp_body = resp.text
        ok = 200 <= resp.status_code < 400
        return RemoteCallResult(
            ok=ok,
            call_id=call_id,
            status="success" if ok else "failed",
            status_code=resp.status_code,
            headers=dict(resp.headers),
            body=resp_body,
            error=None if ok else "upstream_error",
            error_detail=(
                f"Unresolved template vars: {sorted(set(unresolved))}" if unresolved and ok
                else (None if ok else f"Upstream returned {resp.status_code}{warn}")
            ),
            duration_ms=duration_ms,
            request_url=url,
            started_at=started_at,
        )
    except httpx.TimeoutException as e:
        return RemoteCallResult(
            ok=False, call_id=call_id, status="failed",
            error="upstream_timeout",
            error_detail=f"Read timeout after {timeout_ms}ms ({type(e).__name__})",
            duration_ms=int((time.monotonic() - t0) * 1000),
            request_url=url,
            started_at=started_at,
        )
    except httpx.HTTPError as e:
        return RemoteCallResult(
            ok=False, call_id=call_id, status="failed",
            error="network_error",
            error_detail=f"{type(e).__name__}: {e}",
            duration_ms=int((time.monotonic() - t0) * 1000),
            request_url=url,
            started_at=started_at,
        )


def execute_sync(
    call: RemoteApiCall,
    variables: Optional[Dict[str, Any]] = None,
    timeout_ms_override: Optional[int] = None,
) -> RemoteCallResult:
    """同步执行一次远端调用。结果同时写入内存 buffer，供 GET /calls/{id} 查询。"""
    call_id = _gen_call_id()
    result = _execute(call, variables, timeout_ms_override, call_id)
    _store.put(result)
    return result


def submit_async(
    call: RemoteApiCall,
    variables: Optional[Dict[str, Any]] = None,
    timeout_ms_override: Optional[int] = None,
) -> RemoteCallResult:
    """异步触发远端调用。立即返回 pending，后台线程执行后更新 buffer。

    并发上限达到时返回 failed + error=too_many_pending。
    """
    call_id = _gen_call_id()
    started_at = _iso_now()

    if not _store.inc_pending():
        result = RemoteCallResult(
            ok=False, call_id=call_id, status="failed",
            error="too_many_pending",
            error_detail=f"Pending call limit {MAX_PENDING} reached",
            started_at=started_at,
        )
        _store.put(result)
        return result

    pending = RemoteCallResult(ok=True, call_id=call_id, status="pending", started_at=started_at)
    _store.put(pending)

    def _run() -> None:
        try:
            result = _execute(call, variables, timeout_ms_override, call_id)
            _store.update(result)
        finally:
            _store.dec_pending()

    threading.Thread(target=_run, daemon=True).start()
    return pending
