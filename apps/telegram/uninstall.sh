#!/usr/bin/env bash
set -euo pipefail

if [[ ${EUID} -ne 0 ]]; then
  echo "Run as root: sudo $0" >&2
  exit 1
fi

systemctl disable --now telegram.service 2>/dev/null || true
rm -f /etc/systemd/system/telegram.service
systemctl daemon-reload
rm -rf /opt/telegram
rm -f /etc/telegram/telegram.env
rmdir /etc/telegram 2>/dev/null || true
echo "Uninstalled telegram."
