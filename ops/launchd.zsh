#!/bin/zsh
set -e
# The owner already exports credentials here. Suppress shell startup output.
if [[ -f "$HOME/.zshrc" ]]; then
    source "$HOME/.zshrc" >/dev/null 2>&1
fi
exec "$1" run --frozen python ops/run_cycle.py --runner launchd
