#!/bin/bash
# Beacon Proxy 自测脚本
# 用法: ./scripts/self_test.sh
# 需先安装: pip install -e .

set -e
cd "$(dirname "$0")/.."
PROXY_PORT=8080
RULES="examples/mock-rules.yaml"

echo ">>> 启动代理 (端口 $PROXY_PORT)..."
beacon-proxy start --rules "$RULES" --port $PROXY_PORT &
PROXY_PID=$!
trap "kill $PROXY_PID 2>/dev/null || true" EXIT

sleep 3

echo ""
echo ">>> 1. /api/login 应返回 500 + mock body"
RES=$(curl -s -x http://127.0.0.1:$PROXY_PORT -w "%{http_code}" -o /tmp/beacon_resp.txt "http://httpbin.org/api/login")
BODY=$(cat /tmp/beacon_resp.txt)
if [ "$RES" = "500" ] && echo "$BODY" | grep -q "Internal Server Error"; then
  echo "  OK: HTTP $RES, body 含 mock 内容"
else
  echo "  FAIL: HTTP $RES, body=$BODY"
  exit 1
fi

echo ""
echo ">>> 2. /api/cart 应返回 200 + 空购物车"
RES=$(curl -s -x http://127.0.0.1:$PROXY_PORT -w "%{http_code}" -o /tmp/beacon_resp.txt "http://httpbin.org/api/cart")
BODY=$(cat /tmp/beacon_resp.txt)
if [ "$RES" = "200" ] && echo "$BODY" | grep -q '"items":\[\]'; then
  echo "  OK: HTTP $RES, body 含空购物车"
else
  echo "  FAIL: HTTP $RES, body=$BODY"
  exit 1
fi

echo ""
echo ">>> 3. /get 应返回原始响应（无 mock）"
RES=$(curl -s -x http://127.0.0.1:$PROXY_PORT -w "%{http_code}" -o /tmp/beacon_resp.txt "http://httpbin.org/get")
if [ "$RES" = "200" ]; then
  echo "  OK: HTTP $RES, 透传成功"
else
  echo "  FAIL: HTTP $RES"
  exit 1
fi

echo ""
echo ">>> 4. CLI list-rules"
beacon-proxy list-rules --rules "$RULES" | head -5

echo ""
echo ">>> 自测通过"
