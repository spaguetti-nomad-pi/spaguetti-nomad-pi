#!/usr/bin/env bash
set -euo pipefail

if [[ ${EUID} -ne 0 ]]; then
  echo "Run as root: sudo $0" >&2
  exit 1
fi

ETC=/etc/wifi-fallback
ENV_FILE=$ETC/wifi-fallback.env
HOSTNAME=$(hostname -s 2>/dev/null || hostname)
CONN="${HOSTNAME}-setup"

if [[ -f $ENV_FILE ]]; then
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  CONN=${AP_CONNECTION:-${AP_SSID:-$CONN}}
elif [[ -f /etc/spagueti/wifi-fallback.env ]]; then
  # shellcheck disable=SC1091
  source /etc/spagueti/wifi-fallback.env
  CONN=${AP_CONNECTION:-${AP_SSID:-$CONN}}
fi

systemctl disable --now wifi-fallback.service 2>/dev/null || true
rm -f /etc/systemd/system/wifi-fallback.service
systemctl daemon-reload

nmcli connection down "$CONN" 2>/dev/null || true
nmcli connection delete "$CONN" 2>/dev/null || true
nft delete table ip wifi_fallback 2>/dev/null || true
nft delete table ip spagueti_wifi 2>/dev/null || true

rm -f /etc/NetworkManager/dnsmasq-shared.d/wifi-fallback-captive.conf
rm -f /etc/NetworkManager/dnsmasq-shared.d/spagueti-captive.conf
rm -rf /opt/wifi-fallback /opt/spagueti
rm -f "$ENV_FILE" /etc/spagueti/wifi-fallback.env
rmdir "$ETC" /etc/spagueti 2>/dev/null || true

echo "Uninstalled wifi-fallback."
