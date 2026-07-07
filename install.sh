#!/usr/bin/env bash
# ============================================================================
# Hermes Orchestrator Pack — one-liner installer
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/ddawnlll/hermes-pack/main/install.sh | bash
#   curl -fsSL https://raw.githubusercontent.com/ddawnlll/hermes-pack/main/install.sh | bash -s -- --adapter designforge
# ============================================================================
set -euo pipefail

INSTALL_DIR="${HERMES_PACK_DIR:-$HOME/.hermes-pack}"
BRANCH="${HERMES_PACK_BRANCH:-main}"
REPO_URL="https://github.com/ddawnlll/hermes-pack.git"
ADAPTER=""

while [ $# -gt 0 ]; do
  case "$1" in
    --adapter) ADAPTER="$2"; shift 2 ;;
    --dir) INSTALL_DIR="$2"; shift 2 ;;
    --help|-h)
      echo "Hermes Pack — one-liner installer"
      echo ""
      echo "Usage:"
      echo "  curl -fsSL https://raw.githubusercontent.com/ddawnlll/hermes-pack/main/install.sh | bash"
      echo "  curl -fsSL https://raw.githubusercontent.com/ddawnlll/hermes-pack/main/install.sh | bash -s -- --adapter designforge"
      echo ""
      echo "Options:"
      echo "  --adapter <name>  Adapter to bootstrap after install"
      echo "  --dir <path>      Install directory (default: ~/.hermes-pack)"
      echo "  --help, -h        Show this help"
      exit 0
      ;;
    *) echo "Unknown: $1"; exit 1 ;;
  esac
done

echo "[hermes-pack] Installing to $INSTALL_DIR ..."

if [ -d "$INSTALL_DIR" ]; then
  echo "[hermes-pack] Updating existing install..."
  cd "$INSTALL_DIR"
  git pull origin "$BRANCH"
else
  git clone --branch "$BRANCH" "$REPO_URL" "$INSTALL_DIR"
fi

echo "[hermes-pack] Installed at $INSTALL_DIR"
echo ""

if [ -n "$ADAPTER" ]; then
  echo "[hermes-pack] Running bootstrap with adapter: $ADAPTER"
  echo ""
  echo "  Usage: bash $INSTALL_DIR/bootstrap.sh /path/to/your/repo --adapter $ADAPTER"
  echo ""
  echo "Or if you're in the target repo directory:"
  echo "  bash $INSTALL_DIR/bootstrap.sh . --adapter $ADAPTER"
else
  echo "Available adapters:"
  ls "$INSTALL_DIR/adapters/" 2>/dev/null || echo "  (none)"
  echo ""
  echo "To bootstrap a project:"
  echo "  bash $INSTALL_DIR/bootstrap.sh /path/to/repo --adapter <name>"
  echo ""
  echo "For dry-run (preview without changes):"
  echo "  bash $INSTALL_DIR/bootstrap.sh --dry-run /path/to/repo --adapter <name>"
fi
