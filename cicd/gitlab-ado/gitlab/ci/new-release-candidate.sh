#!/bin/sh
# Linux Runner entry point; no PowerShell dependency.
set -eu
exec python3 "$(dirname "$0")/bridge.py" package "$@"
