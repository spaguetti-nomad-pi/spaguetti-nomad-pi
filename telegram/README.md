# Telegram bot

The Pi has no UI. You talk to it in Telegram. It **polls** Telegram (outbound HTTPS), so it works on any Wi-Fi — no public IP, no webhook, no tunnel.

```
you --message--> Telegram --getUpdates-- Pi
Pi  --sendMessage--> Telegram --you
```

Webhook needs a public HTTPS URL. This Pi moves between networks, so polling is the default. Same `handle()` later if you add a tunnel.

## Setup (once)

1. In Telegram, talk to [@BotFather](https://t.me/BotFather) → `/newbot` → copy the token.
2. Open your new bot and send `/start`.
3. On the Pi:

```bash
cp telegram/telegram.env.example telegram/telegram.env
```

Put the token in `TELEGRAM_BOT_TOKEN`, then:

```bash
sudo ./telegram/install.sh
journalctl -u telegram -f
```

Send `/start` again. The log prints `set TELEGRAM_CHAT_ID=<id> then restart`. Put that id in `/etc/telegram/telegram.env` (or `telegram/telegram.env` before install) and:

```bash
sudo systemctl restart telegram
```

Only that chat is answered. Everyone else is ignored.

`telegram.env` is gitignored. Reinstall does not overwrite `/etc/telegram/telegram.env`.

## Commands

| | |
| --- | --- |
| `/status` | hostname and uptime |
| `/start` `/help` | list commands |

## Uninstall

```bash
sudo ./telegram/uninstall.sh
```
