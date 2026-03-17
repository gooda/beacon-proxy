#!/usr/bin/env bash
# Beacon Proxy 启动脚本
# 用法: ./scripts/start.sh [--port 8080] [--api-port 8765] [--rules rules]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

RULES="${LLM_PROXY_RULES:-rules}"
PORT="${BEACON_PROXY_PORT:-8080}"
API_PORT="${BEACON_PROXY_API_PORT:-8765}"
API_HOST="${BEACON_PROXY_API_HOST:-0.0.0.0}"

# 解析简单参数
while [[ $# -gt 0 ]]; do
  case $1 in
    --port) PORT="$2"; shift 2 ;;
    --api-port) API_PORT="$2"; shift 2 ;;
    --api-host) API_HOST="$2"; shift 2 ;;
    --rules) RULES="$2"; shift 2 ;;
    *) shift ;;
  esac
done

echo "Beacon Proxy 启动中..."
echo "  代理端口: $PORT"
echo "  API 端口: $API_PORT"
echo "  规则: $RULES"
echo "  证书: http://$API_HOST:$API_PORT/certificate"
echo ""

# 规则路径：优先项目内 rules，否则用传入值
if [[ -d "$PROJECT_ROOT/$RULES" || -f "$PROJECT_ROOT/$RULES" ]]; then
  RULES_PATH="$PROJECT_ROOT/$RULES"
else
  RULES_PATH="$RULES"
fi

if command -v beacon-proxy &>/dev/null; then
  exec beacon-proxy start \
    --with-api \
    --port "$PORT" \
    --api-port "$API_PORT" \
    --api-host "$API_HOST" \
    --ssl-insecure \
    --rules "$RULES_PATH"
else
  export PYTHONPATH="$PROJECT_ROOT/src"

  exec python -m llm_proxy.cli start \
    --with-api \
    --port "$PORT" \
    --api-port "$API_PORT" \
    --api-host "$API_HOST" \
    --ssl-insecure \
    --rules "$RULES_PATH"
fi
