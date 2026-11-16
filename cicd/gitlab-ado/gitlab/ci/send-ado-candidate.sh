#!/bin/sh
# Queue only; never wait for ADO completion inside the GitLab notify job.
set -eu
exec python3 "$(dirname "$0")/bridge.py" notify "$@"
