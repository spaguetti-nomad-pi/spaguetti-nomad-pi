# Apps catalog

Every service on the Pi is a folder here. wifi-fallback and Telegram are the first two; Immich and the rest join the same way.

```
apps/<name>/
  app.conf      UNIT=…  and/or  NEEDS_VAULT=1
  compose.yml   optional
  install.sh    optional, run on `apps up`
```

Which ones run is **not** in git. On the Pi: `/etc/apps/enabled`. `apps/install.sh` enables `wifi-fallback` by default. Telegram (needs a token) you enable yourself.

```bash
sudo ./apps/install.sh
apps status
sudo apps enable telegram
sudo apps up
sudo apps down
sudo apps logs wifi-fallback
```

`up`/`down` without a name apply to every enabled app. If `NEEDS_VAULT=1` and `/vault` is not mounted, `up` fails closed.

Telegram `/services` is `apps status`. Deploy is rsync + `apps/install.sh` + `apps up`.

`uninstall.sh` inside an app removes `/opt` **and** `/etc/<app>` (token, AP password). To reinstall without losing that, stop the units and delete `/opt` only.

## First Pi

NVMe flash: [FLASH.md](../FLASH.md). Then once:

```bash
curl -fsSL https://raw.githubusercontent.com/spaguetti-nomad-pi/spaguetti-nomad-pi/main/setup.sh | bash
```

Or, from a clone: `sudo ./setup.sh`. That is clone (if needed) + `apps/install.sh` + `apps up`. Do not use `setup.sh` to update later.

Telegram after that:

```bash
sudo apps enable telegram
sudo apps up telegram
```

Live env stays in `/etc/telegram/telegram.env` (not overwritten).

## Existing Pi (new tree)

```bash
sudo systemctl disable --now wifi-fallback.service telegram.service 2>/dev/null || true
sudo rm -f /etc/systemd/system/wifi-fallback.service /etc/systemd/system/telegram.service
sudo systemctl daemon-reload
sudo rm -rf /opt/wifi-fallback /opt/telegram

cd ~/spaguetti-nomad-pi
git pull --ff-only origin main
sudo ./setup.sh
sudo apps enable telegram
sudo apps up
apps status
```

`wifi-fallback` should be `active`. `telegram` too if `/etc/telegram/telegram.env` still has token and chat id.

Later updates: `git pull` and `sudo apps up`, not `setup.sh`.
