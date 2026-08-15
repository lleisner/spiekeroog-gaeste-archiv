#!/bin/sh
set -eu

LABEL="de.spiekeroog.gaestestatistik"

if [ "$(uname -s)" != "Darwin" ]; then
    echo "Die automatische Installation wird derzeit nur auf macOS unterstützt." >&2
    echo "Der Sammler selbst kann überall mit Python 3 ausgeführt werden." >&2
    exit 1
fi

REPO_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)
PYTHON_BIN=$(command -v python3 || true)
if [ -z "$PYTHON_BIN" ]; then
    echo "Python 3 wurde nicht gefunden." >&2
    exit 1
fi

DATA_DIR="$REPO_DIR/data/gaestestatistik"
AGENT_DIR="$HOME/Library/LaunchAgents"
PLIST_PATH="$AGENT_DIR/$LABEL.plist"
mkdir -p "$DATA_DIR" "$AGENT_DIR"

launchctl bootout "gui/$(id -u)/$LABEL" >/dev/null 2>&1 || true

"$PYTHON_BIN" - "$PLIST_PATH" "$REPO_DIR" "$PYTHON_BIN" <<'PY'
import plistlib
import sys
from pathlib import Path

plist_path = Path(sys.argv[1])
repo_dir = Path(sys.argv[2])
python_bin = sys.argv[3]
data_dir = repo_dir / "data" / "gaestestatistik"

configuration = {
    "Label": "de.spiekeroog.gaestestatistik",
    "ProgramArguments": [
        python_bin,
        str(repo_dir / "collect_spiekeroog.py"),
        "--once-per-day",
    ],
    "WorkingDirectory": str(repo_dir),
    "RunAtLoad": True,
    "StartCalendarInterval": {"Hour": 6, "Minute": 15},
    "StandardOutPath": str(data_dir / "collector.log"),
    "StandardErrorPath": str(data_dir / "collector.error.log"),
}

with plist_path.open("wb") as handle:
    plistlib.dump(configuration, handle, sort_keys=False)
PY

plutil -lint "$PLIST_PATH" >/dev/null
launchctl bootstrap "gui/$(id -u)" "$PLIST_PATH"
launchctl kickstart -k "gui/$(id -u)/$LABEL"

echo "Installiert: täglicher Abruf um 06:15 Uhr"
echo "Daten: $DATA_DIR"
echo "Status: launchctl print gui/$(id -u)/$LABEL"
