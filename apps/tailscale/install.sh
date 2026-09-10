#!/usr/bin/env bash
set -euo pipefail

if [[ ${EUID} -ne 0 ]]; then
  echo "Run as root: sudo $0" >&2
  exit 1
fi

if ! command -v tailscale >/dev/null; then
  curl -fsSL https://tailscale.com/install.sh | sh
fi

systemctl enable --now tailscaled.service

if tailscale status >/dev/null 2>&1; then
  echo "tailscale: $(tailscale ip -4 2>/dev/null || echo up)"
  exit 0
fi

echo "tailscaled is running. Login once (same account as Mac and phone):"
echo "  sudo tailscale up"
echo "Then: tailscale ip -4"
