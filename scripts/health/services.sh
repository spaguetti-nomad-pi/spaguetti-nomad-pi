#!/usr/bin/env bash
# platform units and enabled apps
set -u
if command -v apps >/dev/null; then
  exec apps status
fi
for u in wifi-fallback telegram ssh; do
  if state=$(systemctl is-active "$u" 2>/dev/null); then
    echo "$u $state"
  else
    echo "$u ${state:-unknown}"
  fi
done
