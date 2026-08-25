#!/usr/bin/env bash
set -euo pipefail

if [[ ${EUID} -ne 0 ]]; then
  echo "Run as root: sudo $0" >&2
  exit 1
fi

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
PREFIX=/opt/wifi-fallback
ETC=/etc/wifi-fallback
UNIT=/etc/systemd/system/wifi-fallback.service
DNSMASQ_DIR=/etc/NetworkManager/dnsmasq-shared.d
HOSTNAME=$(hostname -s 2>/dev/null || hostname)
DEFAULT_SSID="${HOSTNAME}-setup"

export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq dnsmasq-base nftables python3 network-manager

install -d -m 0755 "$PREFIX/src" "$PREFIX/portal" "$ETC" "$DNSMASQ_DIR"

install -m 0644 "$SCRIPT_DIR/src/wifi_fallback.py" "$PREFIX/src/wifi_fallback.py"
install -m 0644 "$SCRIPT_DIR/portal/index.html" "$PREFIX/portal/index.html"
install -m 0644 "$SCRIPT_DIR/portal/app.js" "$PREFIX/portal/app.js"
install -m 0644 "$SCRIPT_DIR/portal/style.css" "$PREFIX/portal/style.css"
install -m 0644 "$SCRIPT_DIR/wifi-fallback.service" "$UNIT"

if [[ ! -f $ETC/wifi-fallback.env ]]; then
  ENV_SRC=$SCRIPT_DIR/wifi-fallback.env
  if [[ ! -f $ENV_SRC ]]; then
    ENV_SRC=$SCRIPT_DIR/wifi-fallback.env.example
  fi
  install -m 0644 "$ENV_SRC" "$ETC/wifi-fallback.env"
fi

# shellcheck disable=SC1091
source "$ETC/wifi-fallback.env"

if [[ ${#AP_PASSWORD} -lt 8 ]]; then
  echo "AP_PASSWORD must be at least 8 characters (WPA2)." >&2
  exit 1
fi

IFACE=${AP_IFACE:-wlan0}
if ! nmcli -t -f DEVICE,TYPE device status | grep -q "^${IFACE}:wifi$"; then
  DETECTED=$(nmcli -t -f DEVICE,TYPE device status | awk -F: '$2=="wifi"{print $1; exit}')
  if [[ -n ${DETECTED} ]]; then
    echo "Using WiFi interface ${DETECTED} (not ${IFACE})"
    sed -i "s/^AP_IFACE=.*/AP_IFACE=${DETECTED}/" "$ETC/wifi-fallback.env"
    IFACE=$DETECTED
  fi
fi

ADDR=${AP_ADDRESS:-10.42.0.1}
cat > "$DNSMASQ_DIR/wifi-fallback-captive.conf" <<EOF
address=/#/${ADDR}
EOF

rfkill unblock wifi || true
systemctl enable --now NetworkManager.service
systemctl daemon-reload
systemctl enable wifi-fallback.service
systemctl restart wifi-fallback.service

echo
echo "Installed wifi-fallback."
echo "  AP SSID:     ${AP_SSID:-$DEFAULT_SSID}"
echo "  AP password: ${AP_PASSWORD}"
echo "  Portal:      http://${ADDR}"
echo "  Logs:        journalctl -u wifi-fallback -f"
