#!/usr/bin/env bash
# listening TCP/UDP ports
set -u
if ! command -v ss >/dev/null; then
  echo "ss not found"
  exit 0
fi
out=$(ss -lntup 2>/dev/null | awk 'NR>1{print}')
[[ -n $out ]] && printf '%s\n' "$out" || echo "(none)"
