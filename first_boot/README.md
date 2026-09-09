# First boot

NVMe flash, first login, and the WiFi fallback AP. Later deploys (your fork → your Pi): [cicd/README.md](../cicd/README.md).

**OS:** Raspberry Pi OS Lite 64-bit (Bookworm) on NVMe

## Flash Lite onto the NVMe

If the Pi still boots Desktop from an SD card, follow [steps.MD](steps.MD). When it is on Lite and you have SSH, come back here.

```bash
ssh YOUR_USER@YOUR_HOSTNAME.local
```

## Install the WiFi fallback

On the Pi. This clones public `main` into `~/spaguetti-nomad-pi` if needed and enables the service:

```bash
curl -fsSL https://raw.githubusercontent.com/spaguetti-nomad-pi/spaguetti-nomad-pi/main/first_boot/setup.sh | bash
```

Same thing, without `curl | bash`:

```bash
sudo apt-get update && sudo apt-get install -y git
git clone --depth 1 --branch main https://github.com/spaguetti-nomad-pi/spaguetti-nomad-pi.git ~/spaguetti-nomad-pi
cd ~/spaguetti-nomad-pi
sudo ./first_boot/setup.sh
```

If the repo is already there:

```bash
cd ~/spaguetti-nomad-pi
sudo ./first_boot/setup.sh
```

A good install ends with something like:

```text
Installed wifi-fallback.
  AP SSID:     SPAGUETI-setup
  AP password: raspi-setup
  Portal:      http://10.42.0.1
  Logs:        journalctl -u wifi-fallback -f
```

SSID is `{hostname}-setup`. Password defaults to `raspi-setup`.

## Check it

```bash
systemctl status wifi-fallback --no-pager
journalctl -u wifi-fallback -f
```

The AP does **not** appear while the Pi has internet (saved WiFi or Ethernet). That is expected.

## Test the AP

1. Leave SSH open or not — it will drop.
2. Unplug Ethernet. Forget or disable the current WiFi on the Pi (or kick it off the router).
3. Wait ~45s. `{hostname}-setup` should show up on your phone.
4. Join with `raspi-setup`. If the portal does not open, go to `http://10.42.0.1`.
5. Pick the venue network. The AP goes down; SSH on the LAN should work again.

Details: [wifi-fallback/README.md](wifi-fallback/README.md).

Headless control after that: [telegram/README.md](../telegram/README.md).
