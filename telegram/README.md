# Telegram bot

The Pi has no UI. You talk to it in Telegram. It **polls** Telegram (outbound HTTPS), so it works on any Wi-Fi — no public IP, no webhook, no tunnel.

Commands are shell scripts in `scripts/<category>/<name>.sh`. Drop a new file there: `/name` appears after reinstall. The first `# comment` in the script is the help line. Names must be unique across categories.

```
you --message--> Telegram --getUpdates-- Pi
Pi  --sendMessage--> Telegram --you
```

Same scripts work over SSH: `./scripts/health/status.sh`.

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

Send `/start` again. The log prints `set TELEGRAM_CHAT_ID=<id> then restart`. Put that id in `/etc/telegram/telegram.env` and `sudo systemctl restart telegram`.

Only that chat is answered. User text is never passed to the shell.

## Commands

`/start` and `/help` list whatever is on disk, grouped by category.

**health**

| | |
| --- | --- |
| `/status` | hostname, load, memory, disk, SoC temp |
| `/net` | IPv4 addresses and default route |
| `/updates` | pending apt upgrades (cache only, does not install) |
| `/services` | wifi-fallback, telegram, ssh |

**security**

| | |
| --- | --- |
| `/ports` | listening TCP/UDP ports |
| `/logins` | sessions, recent logins, failed SSH (7d) |

Read-only. No reboot, upgrade, or kill from Telegram.

## Uninstall

```bash
sudo ./telegram/uninstall.sh
```
