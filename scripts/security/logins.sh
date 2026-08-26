#!/usr/bin/env bash
# current sessions, recent logins, failed SSH (7d)
set -u
echo "now:"
who 2>/dev/null || echo "(none)"
echo
echo "last:"
last -n 8 2>/dev/null | head -8
echo
fails=$(journalctl -u ssh --since "7 days ago" -g "Failed password" --no-pager 2>/dev/null | wc -l)
echo "ssh fails (7d): $fails"
if command -v lastb >/dev/null; then
  echo
  echo "lastb:"
  lastb -n 5 2>/dev/null | head -5
fi
