#!/usr/bin/env bash
set -euo pipefail

if [[ ${EUID} -ne 0 ]]; then
  echo "Run as root: sudo $0" >&2
  exit 1
fi

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
PREFIX=/opt/telegram
ETC=/etc/telegram
UNIT=/etc/systemd/system/telegram.service

install -d -m 0755 "$PREFIX/src" "$ETC"
install -m 0644 "$SCRIPT_DIR/src/bot.py" "$PREFIX/src/bot.py"
install -m 0644 "$SCRIPT_DIR/telegram.service" "$UNIT"

if [[ ! -f $ETC/telegram.env ]]; then
  ENV_SRC=$SCRIPT_DIR/telegram.env
  if [[ ! -f $ENV_SRC ]]; then
    ENV_SRC=$SCRIPT_DIR/telegram.env.example
  fi
  install -m 0600 "$ENV_SRC" "$ETC/telegram.env"
fi

# shellcheck disable=SC1091
source "$ETC/telegram.env"

systemctl daemon-reload
systemctl enable telegram.service

if [[ -z ${TELEGRAM_BOT_TOKEN:-} ]]; then
  echo "Set TELEGRAM_BOT_TOKEN (and TELEGRAM_CHAT_ID) in $ETC/telegram.env"
  echo "then: sudo systemctl restart telegram"
  exit 0
fi

systemctl restart telegram.service
echo "telegram bot running. Logs: journalctl -u telegram -f"
