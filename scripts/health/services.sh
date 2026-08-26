#!/usr/bin/env bash
# systemd units for this Pi
set -u
for u in wifi-fallback telegram ssh; do
  if state=$(systemctl is-active "$u" 2>/dev/null); then
    echo "$u $state"
  else
    echo "$u ${state:-unknown}"
  fi
done
