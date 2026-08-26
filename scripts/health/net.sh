#!/usr/bin/env bash
# IPv4 addresses and default route
set -u
if ! command -v ip >/dev/null; then
  echo "ip not found"
  exit 0
fi
ip -4 -o addr show 2>/dev/null | awk '{gsub(/\/[0-9]+/,"",$4); print $2, $4}'
echo
ip -4 route show default 2>/dev/null || true
