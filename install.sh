#!/usr/bin/env bash
# ============================================================================
# Hephaestus — one-liner installer
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/ddawnlll/hephaestus/main/install.sh | bash
#   curl -fsSL https://raw.githubusercontent.com/ddawnlll/hephaestus/main/install.sh | bash -s -- --adapter designforge
# ============================================================================
set -euo pipefail

INSTALL_DIR="${HEPHAESTUS_DIR:-$HOME/.hephaestus}"
BRANCH="${HEPHAESTUS_BRANCH:-main}"
REPO_URL="https://github.com/ddawnlll/hephaestus.git"
ADAPTER=""

while [ $# -gt 0 ]; do
  case "$1" in
    --adapter) ADAPTER="$2"; shift 2 ;;
    --dir) INSTALL_DIR="$2"; shift 2 ;;
    --help|-h)
      echo "Hephaestus — one-liner installer"
      echo ""
      echo "Usage:"
      echo "  curl -fsSL https://raw.githubusercontent.com/ddawnlll/hephaestus/main/install.sh | bash"
      echo "  curl -fsSL https://raw.githubusercontent.com/ddawnlll/hephaestus/main/install.sh | bash -s -- --adapter designforge"
      echo ""
      echo "Options:"
      echo "  --adapter <name>  Adapter to bootstrap after install"
      echo "  --dir <path>      Install directory (default: ~/.hephaestus)"
      echo "  --help, -h        Show this help"
      exit 0
      ;;
    *) echo "Unknown: $1"; exit 1 ;;
  esac
done

echo "[hephaestus] Installing to $INSTALL_DIR ..."

if [ -d "$INSTALL_DIR" ]; then
  echo "[hephaestus] Updating existing install..."
  cd "$INSTALL_DIR"
  git pull origin "$BRANCH"
else
  git clone --branch "$BRANCH" "$REPO_URL" "$INSTALL_DIR"
fi

echo "[hephaestus] Installed at $INSTALL_DIR"
echo ""

if [ -n "$ADAPTER" ]; then
  echo "[hephaestus] Running bootstrap with adapter: $ADAPTER"
  echo ""
  echo "  Usage: bash $INSTALL_DIR/bootstrap.sh /path/to/your/repo --adapter $ADAPTER"
  echo ""
  echo "Or if you're in the target repo directory:"
  echo "  bash $INSTALL_DIR/bootstrap.sh . --adapter $ADAPTER"
else
  echo "Available adapters (Hephaestus):"
  ls "$INSTALL_DIR/adapters/" 2>/dev/null || echo "  (none)"
  echo ""
  echo "To bootstrap a project:"
  echo "  bash $INSTALL_DIR/bootstrap.sh /path/to/repo --adapter <name>"
  echo ""
  echo "For dry-run (preview without changes):"
  echo "  bash $INSTALL_DIR/bootstrap.sh --dry-run /path/to/repo --adapter <name>"
fi
