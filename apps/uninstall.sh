#!/usr/bin/env bash
set -euo pipefail

if [[ ${EUID} -ne 0 ]]; then
  echo "Run as root: sudo $0" >&2
  exit 1
fi

rm -f /usr/local/bin/apps
echo "Removed /usr/local/bin/apps. Left enabled list in /etc/apps."
