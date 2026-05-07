#!/usr/bin/env bash
# Record the ardi-orbit demo into .cast, .gif, and (optional) .mp4.
#
# Outputs:
#   demo/ardi-orbit-demo.cast   (raw asciinema recording, ~30KB)
#   demo/ardi-orbit-demo.gif    (ready to upload to the grant form)
#   demo/ardi-orbit-demo.mp4    (optional, smaller, needs ffmpeg)

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

CAST="demo/ardi-orbit-demo.cast"
GIF="demo/ardi-orbit-demo.gif"
MP4="demo/ardi-orbit-demo.mp4"

ASCIINEMA="$REPO_ROOT/.venv/bin/asciinema"
AGG="$REPO_ROOT/demo/bin/agg"
PYTHON="$REPO_ROOT/.venv/bin/python"

for required in "$ASCIINEMA" "$AGG" "$PYTHON"; do
    if [[ ! -x "$required" ]]; then
        echo "✗ missing $required — run ./demo/install_recorder.sh first"
        exit 1
    fi
done

# Make sure TERM is set to something Rich likes (asciinema inherits it)
export TERM="${TERM:-xterm-256color}"
export COLUMNS="${COLUMNS:-120}"
export LINES="${LINES:-40}"
# Force Rich to use truecolor regardless of detected TTY
export FORCE_COLOR=3
export COLORTERM=truecolor

# Fresh state dir each recording
rm -rf .demo-state

echo "→ recording $CAST  (press Ctrl+D or wait for demo to finish) ..."
rm -f "$CAST"
"$ASCIINEMA" rec \
    --idle-time-limit 2 \
    --cols 120 --rows 40 \
    --title "ardi-orbit — autonomous multilingual mining agent for the Ardi WorkNet" \
    --command "$PYTHON $REPO_ROOT/demo/run_demo.py" \
    "$CAST"

echo "→ rendering $GIF ..."
rm -f "$GIF"
"$AGG" \
    --theme monokai \
    --font-size 14 \
    --speed 1.3 \
    --fps-cap 30 \
    "$CAST" "$GIF"

echo "✓ done"
ls -lh "$CAST" "$GIF"

if command -v ffmpeg >/dev/null 2>&1; then
    echo "→ converting to $MP4 ..."
    rm -f "$MP4"
    ffmpeg -y -loglevel error -i "$GIF" \
        -movflags +faststart \
        -pix_fmt yuv420p \
        -vf "scale=trunc(iw/2)*2:trunc(ih/2)*2" \
        "$MP4"
    echo "✓ $MP4"
    ls -lh "$MP4"
fi

cat <<EOF

---------------------------------------------------------------
Ready to upload to https://100t.xiaomimimo.com/:

  $GIF   $(wc -c < "$GIF" | awk '{printf "(%.1f MB)\n", $1/1024/1024}')
$( [[ -f "$MP4" ]] && echo "  $MP4   $(wc -c < "$MP4" | awk '{printf "(%.1f MB)\n", $1/1024/1024}')" )

Preview locally:
  asciinema play $CAST       # terminal replay
  xdg-open $GIF              # gif viewer
---------------------------------------------------------------
EOF
