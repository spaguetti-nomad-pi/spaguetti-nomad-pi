# Tailscale

A private mesh between *your* machines. Not a LAN inside the café Wi‑Fi. The Pi, the laptop, and the phone join the same tailnet with outbound connections only — no public IP, no port forward.

Each node gets a stable `100.x` address and a MagicDNS name. SSH and later HTTP (Caddy) use that, not `192.168.0.x`.

## Install

**Account:** [tailscale.com](https://tailscale.com) — free plan is enough. Turn on 2FA.

**Mac:** [Tailscale for macOS](https://tailscale.com/download/mac) → log in.

**Android:** Play Store “Tailscale” → same login.

**Pi** (after this folder is on the machine):

```bash
cd ~/spaguetti-nomad-pi
sudo apps enable tailscale
sudo apps up tailscale
sudo tailscale up
```

`tailscale up` prints a URL. Open it on the Mac (already logged in) and approve the Pi. Then:

```bash
tailscale status
tailscale ip -4
```

From the laptop, with MagicDNS on (default):

```bash
ssh YOUR_USER@YOUR_HOSTNAME
# or: ssh YOUR_USER@100.x.x.x
```

Put the `100.x` or MagicDNS name in `~/.ssh/config` as a second `Host` if you want.

`apps down tailscale` stops `tailscaled` and drops the mesh. Only do that while you still have LAN SSH.

## Uninstall

```bash
sudo apps disable tailscale
sudo ./apps/tailscale/uninstall.sh
```
