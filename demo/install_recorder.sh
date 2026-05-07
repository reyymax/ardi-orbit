#!/usr/bin/env bash
# Install local recording tools (asciinema + agg) — no system-wide writes.
#
# Writes to:  ./demo/bin/agg  +  .venv/bin/asciinema
# Idempotent: re-running is safe.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

# --- asciinema -------------------------------------------------------------
if [[ ! -x .venv/bin/asciinema ]]; then
    echo "→ installing asciinema into .venv ..."
    if [[ ! -d .venv ]]; then
        echo "✗ expected ./.venv to exist — run 'python3.11 -m venv .venv && .venv/bin/pip install -e .[dev]' first"
        exit 1
    fi
    .venv/bin/pip install --quiet asciinema
fi
echo "✓ $(.venv/bin/asciinema --version)"

# --- agg (Rust, for .cast -> .gif) -----------------------------------------
AGG_BIN="demo/bin/agg"
AGG_VERSION="v1.8.1"

arch="$(uname -m)"
case "$arch" in
    x86_64 | amd64)  agg_asset="agg-x86_64-unknown-linux-musl" ;;
    aarch64 | arm64) agg_asset="agg-aarch64-unknown-linux-gnu" ;;
    armv7l | armv7)  agg_asset="agg-arm-unknown-linux-gnueabihf" ;;
    *) echo "✗ unsupported arch: $arch"; exit 1 ;;
esac

if [[ ! -x "$AGG_BIN" ]] || ! "$AGG_BIN" --version 2>/dev/null | grep -q "$AGG_VERSION"; then
    mkdir -p "$(dirname "$AGG_BIN")"
    url="https://github.com/asciinema/agg/releases/download/${AGG_VERSION}/${agg_asset}"
    echo "→ downloading agg ${AGG_VERSION} ($agg_asset) ..."
    curl -fsSL -o "$AGG_BIN" "$url"
    chmod +x "$AGG_BIN"
fi
echo "✓ $("$AGG_BIN" --version)"

# --- ffmpeg (optional, for .gif -> .mp4) -----------------------------------
if command -v ffmpeg >/dev/null 2>&1; then
    echo "✓ ffmpeg ($(ffmpeg -version 2>&1 | head -1 | cut -d' ' -f1-3))"
else
    cat <<'EOF'
ℹ  ffmpeg not found on PATH.
   The Xiaomi MiMo form accepts .gif directly — you don't need ffmpeg.
   To optionally convert the .gif into an .mp4 (smaller file, sharper):
       sudo apt-get install -y ffmpeg        # Debian/Ubuntu
       brew install ffmpeg                   # macOS
EOF
fi

echo
echo "Recorder tools ready. Next:  ./demo/record.sh"
