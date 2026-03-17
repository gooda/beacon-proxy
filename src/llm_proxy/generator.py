"""从代理需求自动生成拦截规则。"""

import re
from typing import List, Optional

from llm_proxy.models import InterceptRule

# 预设：需求描述 -> 规则
PRESETS: dict[str, InterceptRule] = {
    "登录失败": InterceptRule(
        id="login_500",
        url_pattern="/api/login",
        description="登录接口返回500",
        status_code=500,
        body=None,
        use_regex=False,
    ),
    "登录500": InterceptRule(
        id="login_500",
        url_pattern="/api/login",
        description="登录接口返回500",
        status_code=500,
        body=None,
        use_regex=False,
    ),
    "购物车空": InterceptRule(
        id="cart_empty",
        url_pattern="/api/cart",
        description="购物车返回空",
        status_code=200,
        body="[]",
        use_regex=False,
    ),
    "购物车空数组": InterceptRule(
        id="cart_empty",
        url_pattern="/api/cart",
        description="购物车返回空数组",
        status_code=200,
        body="[]",
        use_regex=False,
    ),
}

# 中文/简写 -> URL 路径映射
URL_HINTS: dict[str, str] = {
    "登录": "/api/login",
    "login": "/api/login",
    "购物车": "/api/cart",
    "cart": "/api/cart",
    "用户": "/api/user",
    "user": "/api/user",
    "列表": "/api/list",
    "list": "/api/list",
}


def _slug(s: str) -> str:
    """生成规则 id 的 slug。"""
    s = re.sub(r"[^\w\u4e00-\u9fff\-]", "_", s.strip())
    return re.sub(r"_+", "_", s).strip("_") or "rule"


def generate_rules_from_requirement(requirement: str) -> List[InterceptRule]:
    """
    从自然语言需求生成规则列表。

    支持格式：
    - 预设：登录失败、购物车空
    - "X 返回 Y"：X 为 URL 提示，Y 为状态码
    - "X 空"：X 为 URL 提示，返回空数组
    - 直接 URL：/api/xxx
    """
    req = requirement.strip()
    if not req:
        return []

    # 1. 预设匹配（忽略大小写、空格）
    key = re.sub(r"\s+", "", req.lower())
    for preset_key, rule in PRESETS.items():
        if re.sub(r"\s+", "", preset_key.lower()) == key:
            return [rule]

    # 2. "X 返回 Y" 或 "X 返回Y"
    m = re.match(r"^(.+?)\s*返回\s*(\d{3})\s*$", req, re.IGNORECASE)
    if m:
        hint, code = m.group(1).strip(), int(m.group(2))
        url = URL_HINTS.get(hint) or (hint if hint.startswith("/") else f"/api/{_slug(hint).replace('_', '/')}")
        rid = _slug(hint) + "_" + str(code)
        return [
            InterceptRule(
                id=rid,
                url_pattern=url,
                description=req,
                status_code=code,
                body=None,
                use_regex=False,
            )
        ]

    # 3. "X 空" 或 "X空"
    m = re.match(r"^(.+?)\s*空\s*$", req) or re.match(r"^(.+?)空$", req)
    if m:
        hint = m.group(1).strip()
        url = URL_HINTS.get(hint) or (hint if hint.startswith("/") else f"/api/{_slug(hint).replace('_', '/')}")
        rid = _slug(hint) + "_empty"
        return [
            InterceptRule(
                id=rid,
                url_pattern=url,
                description=req,
                status_code=200,
                body="[]",
                use_regex=False,
            )
        ]

    # 4. 直接作为 URL 模式，默认 500
    url = req if req.startswith("/") or "://" in req else f"/api/{_slug(req).replace('_', '/')}"
    rid = _slug(req) or "rule"
    return [
        InterceptRule(
            id=rid,
            url_pattern=url,
            description=req,
            status_code=500,
            body=None,
            use_regex=False,
        )
    ]
