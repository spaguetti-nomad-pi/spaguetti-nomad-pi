# spaguetti-nomad-pi

A Raspberry Pi 5 you take from network to network. It self-hosts. It has no public IP. If the internal NVMe dies, you buy another, flash Lite, clone this repo, unlock the data disk, and start the apps. **Photos and files do not live on the NVMe.**

Upstream: [spaguetti-nomad-pi/spaguetti-nomad-pi](https://github.com/spaguetti-nomad-pi/spaguetti-nomad-pi). Everyone **forks**. The self-hosted runner and the Pi belong to the fork, never to upstream.

**OS:** Raspberry Pi OS Lite 64-bit on NVMe.

This file is the map. How-to for a single piece lives next to that piece.

---

## The machine, in one picture

```
                    you (Mac / phone)
                         |
         +---------------+----------------+
         |               |                |
      same WiFi      Tailscale        Telegram
      .local / SSH    100.x mesh      outbound poll
         |               |                |
         +---------------+----------------+
                         |
                    Raspberry Pi
                         |
     +-------------------+-------------------+
     |                   |                   |
   NVMe                USB A               USB B
   OS, Docker,         LUKS vault          backups of A
   repo, runner        (the real data)     (and maybe /etc)
```

Three jobs, three disks. One overlay network that is *yours*, not the café’s. One catalog of apps so adding Immich is the same shape as adding the WiFi fallback.

---

## Three disks

| Disk | Role | If it dies |
| --- | --- | --- |
| **NVMe** (inside the Pi) | Raspberry Pi OS, `/opt`, Docker images, git clone, GitHub runner. Cattle. | Buy another, flash Lite ([docs/FLASH.md](docs/FLASH.md)), `setup.sh`, unlock USB A, `apps up`. Time lost, not data. |
| **USB A — vault** | Seafile, Immich, Postgres, anything you actually care about. Bind-mounted at `/vault`. | Restore from USB B. No backup → gone. |
| **USB B — backup** | Encrypted snapshots of `/vault` (restic or similar). Optionally a copy of `/etc/wifi-fallback`, `/etc/telegram`, `/etc/apps` so tokens are not retyped. | You lose history. USB A is still the live copy. |

Cloning the whole NVMe onto B is almost never worth it. Recovery is already “image + repo + apps”. B exists so the **vault** survives.

LUKS on A (and B, or restic’s own encryption) means: Pi stolen while powered off, without the passphrase, the data disk is noise. A keyfile sitting on the NVMe is the same as not encrypting — anyone with the backpack opens the vault. Unlock with a passphrase (SSH or Telegram) or a key USB that does not travel plugged in all the time.

Two extra USB drives plus the NVMe draw current. A powered hub or low-draw disks matter more than “tuning ext4”. Under heavy `apt` the NVMe has already thrown I/O errors; backups should not run at the same time as a transcode.

USB B can already be LUKS + ext4 at `/backup` ([docs/BACKUP.md](docs/BACKUP.md)). **Restic** (the actual sync of A → B) waits until Drive/Photos write into `/vault` — there is nothing useful to snapshot yet. USB A (`/vault`, `/unlock`) is not built. `apps` already fails closed if an app sets `NEEDS_VAULT=1` and `/vault` is not mounted.

---

## How you reach the Pi

There are three paths. They are not the same layer.

### 1. The venue LAN (today)

Same Wi‑Fi (or Ethernet), no client isolation:

```bash
ssh YOUR_USER@YOUR_HOSTNAME.local
```

DHCP leases change every building. Put `HostName hostname.local` in `~/.ssh/config`, not last week’s `192.168.x.x`. Keys, not passwords: [docs/USERS.md](docs/USERS.md). How to *find* a box that does not answer ping: [docs/FINDING.md](docs/FINDING.md).

Same SSID does not mean you can talk to the Pi. Guest networks often allow multicast (mDNS) and drop unicast. That looks like “I see `pi.local` but SSH says no route.”

### 2. Setup AP (today)

If there is no internet for ~45s (~120s after boot when a saved Wi‑Fi profile exists), the Pi raises a WPA2 AP:

| | |
| --- | --- |
| SSID | `{hostname}-setup` |
| Password | `raspi-setup` |
| Portal | `http://10.42.0.1` |

You join from the phone, pick the venue network, the AP goes down, NetworkManager **keeps** that profile (`autoconnect`). Next boot it should come back online without the portal — unless the radio is stolen by the AP too early; that race is why boot grace exists.

This AP is how you **teach the Pi a Wi‑Fi**. It is not how you serve photos to the rest of the apartment.

Details: [apps/wifi-fallback/README.md](apps/wifi-fallback/README.md).

### 3. Overlay — Tailscale (today)

Does not need the USB disks. Pi, laptop, and phone join the same tailnet.

Tailscale is **not** “a LAN carved out of the café Wi‑Fi.” The venue router is not involved. You do not ask it for port forwards.

You install Tailscale on the Pi, the Mac, and the phone, **same account**. Each device opens an **outbound** connection (like Telegram) and joins a private mesh. Each gets a stable `100.x` address and a MagicDNS name (`pi.tailnet.ts.net`).

Pi app: [apps/tailscale/README.md](apps/tailscale/README.md).

That mesh exists whether:

- the Pi is on the apartment Wi‑Fi,
- the Mac is on another network,
- the phone is on LTE.

On the *same* Wi‑Fi you can already SSH with `.local`. Tailscale is the path that **still works** when that LAN does not exist, or isolates clients.

Traffic between your nodes is WireGuard. Tailscale the company coordinates identity and NAT traversal; it does not decrypt your SSH session. Protect the Tailscale account (2FA). A stolen unlocked phone is a foot in the mesh — true of any overlay.

SSH, Immich, and Seafile should bind to the Tailscale IP (or localhost behind a proxy on that IP), never `0.0.0.0` on `wlan0`. The café LAN is not yours.

---

## One HTTP door (not built yet)

Each app wants a port. Publishing them on `wlan0` shows them to everyone on that Wi‑Fi.

Pattern: Caddy (or nginx) listens **only** on the Tailscale address. Apps listen on `127.0.0.1`. Caddy terminates TLS and routes by name:

```
photos.<tailnet>  →  127.0.0.1:2283   Immich
files.<tailnet>   →  127.0.0.1:8082   Seafile
```

A new app is a compose file plus a Caddy snippet. The phone is already on Tailscale; it opens `https://photos.…`.

---

## Apps catalog (today)

Every service is a folder. wifi-fallback, Telegram, and Tailscale are in; Immich and Drive use the same shape.

```
apps/<name>/
  app.conf      UNIT=…  and/or  NEEDS_VAULT=1
  compose.yml   optional
  install.sh    optional, run on `apps up`
```

Which apps run is **not** in git. On the Pi: `/etc/apps/enabled`. Live secrets live under `/etc/…` (and later `/vault/…`), never in the public repo.

```bash
sudo ./apps/install.sh    # once; enables wifi-fallback
apps status
sudo apps enable telegram
sudo apps up              # all enabled
sudo apps up immich       # one
sudo apps down
sudo apps logs wifi-fallback
```

Telegram `/services` is `apps status`. Deploy is rsync + `apps/install.sh` + `apps up`.

Full convention: [apps/README.md](apps/README.md).

---

## Control plane: Telegram (today)

The Pi has no screen. The bot **polls** Telegram over HTTPS out. No webhook, no public IP, no tunnel.

Only your `TELEGRAM_CHAT_ID` is answered. Message text is never passed to the shell. Commands are scripts in `scripts/<category>/<name>.sh`.

Live config is `/etc/telegram/telegram.env` (the copy in the clone is only the first-install template).

Read-only for now: `/status`, `/net`, `/updates`, `/services`, `/ports`, `/logins`. No reboot or `apt` from chat.

Setup: [apps/telegram/README.md](apps/telegram/README.md).

---

## First boot and install (today)

1. Flash Lite on the NVMe: [docs/FLASH.md](docs/FLASH.md).
2. SSH in ([docs/FINDING.md](docs/FINDING.md) if `.local` is shy).
3. Once:

```bash
curl -fsSL https://raw.githubusercontent.com/spaguetti-nomad-pi/spaguetti-nomad-pi/main/setup.sh | bash
```

That is `git clone` of public `main` (if needed) + `apps/install.sh` + `apps up`. Do not use `setup.sh` as an updater.

Same thing from an existing clone: `sudo ./setup.sh`.

Later updates: git on the fork + the runner, or `git pull` on the Pi and `sudo apps up`.

---

## Deploy: the Pi pulls (today)

GitHub never SSHs in. A self-hosted runner on **your fork** pulls jobs, rsyncs the tree (skipping personal `.env` files), then `apps up`.

Do not register a runner on the public upstream.

[cicd/README.md](cicd/README.md).

---

## Security, stacked

| Layer | Job |
| --- | --- |
| Disk (USB A/B) | LUKS / restic. Theft of a powered-off backpack. |
| Network | No inbound from the internet. Services on Tailscale, not `wlan0`. Setup AP only when offline. |
| SSH | One user, one key, `IdentitiesOnly`. Password off once the key works. [docs/USERS.md](docs/USERS.md). |
| Telegram | One chat id. Scripts, not a shell. |
| Tailscale account | 2FA; only your devices. |
| Apps | Secrets in `/etc` or `/vault`, gitignored. Public repo is recipes. |

The NVMe holds tokens in `/etc` because the machine has to boot. Those are annoying to redo, not the photo library. Rotate them after a rebuild.

---

## Build order

**Done:** Lite on NVMe, SSH keys, wifi-fallback (boot grace), Telegram, `apps` catalog, `setup.sh`, fork deploy, Tailscale on Pi + laptop + phone, USB B formatted (LUKS / `/backup`).

**Next:**

1. USB A: LUKS, `/vault`, unlock
2. Caddy on the tailnet address
3. Photos (Immich, no ML on the Pi) and Drive (Seafile) on `/vault`
4. Restic A → B — the sync, once those apps actually write data

AdGuard, Home Assistant, and opening 443 to the world are out of scope until the above is boring.

---

## Repo map

| | |
| --- | --- |
| [docs/FLASH.md](docs/FLASH.md) | SD → Lite on NVMe |
| [docs/FINDING.md](docs/FINDING.md) | Finding and reaching the Pi on a LAN |
| [docs/USERS.md](docs/USERS.md) | Accounts, passwords, SSH keys, who logged in |
| [docs/BACKUP.md](docs/BACKUP.md) | USB B: LUKS, open/close, UAS |
| [apps/README.md](apps/README.md) | Catalog and `apps` CLI |
| [apps/wifi-fallback/README.md](apps/wifi-fallback/README.md) | Offline AP + portal |
| [apps/telegram/README.md](apps/telegram/README.md) | Bot |
| [apps/tailscale/README.md](apps/tailscale/README.md) | Mesh overlay |
| [cicd/README.md](cicd/README.md) | Runner on your fork |
