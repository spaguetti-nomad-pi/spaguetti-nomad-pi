#!/usr/bin/env bash
# Clone public main if needed, then install the WiFi fallback AP.
set -euo pipefail

REPO_URL=https://github.com/spaguetti-nomad-pi/spaguetti-nomad-pi.git
OWNER=${SUDO_USER:-$USER}
HOME_DIR=$(getent passwd "$OWNER" | cut -d: -f6)
DEST=${SETUP_DIR:-$HOME_DIR/spaguetti-nomad-pi}

as_user() {
  if [[ $EUID -eq 0 && $OWNER != root ]]; then
    sudo -u "$OWNER" -- "$@"
  else
    "$@"
  fi
}

self=$(readlink -f "${BASH_SOURCE[0]:-/dev/null}" 2>/dev/null || true)
if [[ -n $self && -x $(dirname "$self")/wifi-fallback/install.sh ]]; then
  ROOT=$(cd "$(dirname "$self")/.." && pwd)
else
  if ! command -v git >/dev/null; then
    export DEBIAN_FRONTEND=noninteractive
    sudo apt-get update -qq
    sudo apt-get install -y -qq git
  fi
  if [[ -d $DEST/.git ]]; then
    as_user git -C "$DEST" fetch --depth 1 origin main
    as_user git -C "$DEST" checkout -q -B main origin/main
  else
    as_user git clone --depth 1 --branch main "$REPO_URL" "$DEST"
  fi
  ROOT=$DEST
fi

exec sudo "$ROOT/first_boot/wifi-fallback/install.sh"
