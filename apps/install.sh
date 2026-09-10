#!/usr/bin/env bash
set -euo pipefail

if [[ ${EUID} -ne 0 ]]; then
  echo "Run as root: sudo $0" >&2
  exit 1
fi

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
ETC=/etc/apps

install -d -m 0755 "$ETC"
[[ -f $ETC/enabled ]] || install -m 0644 /dev/null "$ETC/enabled"
printf '%s\n' "$SCRIPT_DIR" > "$ETC/dir"
install -m 0755 "$SCRIPT_DIR/ctl.sh" /usr/local/bin/apps
if ! grep -qx wifi-fallback "$ETC/enabled" 2>/dev/null; then
  echo wifi-fallback >> "$ETC/enabled"
fi

echo "apps ctl → /usr/local/bin/apps"
echo "  catalog: $SCRIPT_DIR"
echo "  enabled: $ETC/enabled"
