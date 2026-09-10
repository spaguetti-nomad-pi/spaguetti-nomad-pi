#!/usr/bin/env bash
set -euo pipefail

if [[ ${EUID} -ne 0 ]]; then
  echo "Run as root: sudo $0" >&2
  exit 1
fi

tailscale logout 2>/dev/null || true
systemctl disable --now tailscaled.service 2>/dev/null || true
echo "Package left installed. To remove: apt-get remove --purge tailscale"
