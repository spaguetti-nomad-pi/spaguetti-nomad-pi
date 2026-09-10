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

## First Pi

NVMe flash: [FLASH.md](../FLASH.md). Then once:

```bash
curl -fsSL https://raw.githubusercontent.com/spaguetti-nomad-pi/spaguetti-nomad-pi/main/setup.sh | bash
```

Or, from a clone: `sudo ./setup.sh`. That is clone (if needed) + `apps/install.sh` + `apps up`. Do not use `setup.sh` to update later.
