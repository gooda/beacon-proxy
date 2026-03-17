#!/usr/bin/env bash
# Beacon Proxy 打包脚本 - 生成可部署的 tar 包
# 用法: ./scripts/package.sh
# 输出: dist/beacon-proxy-0.1.0.tar.gz

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

# 从 pyproject 读取版本
VERSION=$(grep -E '^version\s*=' pyproject.toml | head -1 | sed 's/.*"\([^"]*\)".*/\1/' || echo "0.1.0")
NAME="beacon-proxy"
OUT_DIR="dist"
PKG_NAME="${NAME}-${VERSION}"
PKG_DIR="$OUT_DIR/$PKG_NAME"

echo "打包 Beacon Proxy v$VERSION ..."

rm -rf "$PKG_DIR"
mkdir -p "$PKG_DIR"

# 复制必要文件（排除 __pycache__）
cp -r src "$PKG_DIR/"
find "$PKG_DIR/src" -depth -name __pycache__ -type d -exec rm -rf {} \; 2>/dev/null || true
cp -r rules "$PKG_DIR/"
cp -r scripts "$PKG_DIR/"
cp pyproject.toml requirements.txt README.md "$PKG_DIR/"
cp -r docs "$PKG_DIR/" 2>/dev/null || true

# 部署说明
cat > "$PKG_DIR/DEPLOY.md" << 'DEPLOY'
# Beacon Proxy 部署说明

## 方式一：pip 安装（推荐）

```bash
pip install -r requirements.txt
pip install -e .
# 或直接: pip install .
```

## 方式二：启动

```bash
./scripts/start.sh
```

或

```bash
beacon-proxy start --with-api --port 8080 --api-port 8765 --api-host 0.0.0.0 --ssl-insecure --rules rules
```

## 端口

- 8080: 代理
- 8765: 激活 API / 证书下载

## 证书

设备配置代理后访问: http://<本机IP>:8765/certificate
DEPLOY

# 打 tar 包
mkdir -p "$OUT_DIR"
tar -czf "$OUT_DIR/${PKG_NAME}.tar.gz" -C "$OUT_DIR" "$PKG_NAME"
rm -rf "$PKG_DIR"

echo ""
echo "已生成: $OUT_DIR/${PKG_NAME}.tar.gz"
echo ""
echo "部署到其他设备:"
echo "  1. 解压: tar -xzf ${PKG_NAME}.tar.gz && cd $PKG_NAME"
echo "  2. 安装: pip install -r requirements.txt && pip install ."
echo "  3. 启动: ./scripts/start.sh"
echo ""
