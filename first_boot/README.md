# First boot

NVMe flash, first boot, and WiFi fallback. CI/CD (fork → your Pi): [cicd/README.md](../cicd/README.md).

**OS:** Raspberry Pi OS Lite 64-bit (Bookworm) on NVMe

## First boot

If you start from an SD card with Desktop and want Lite on the NVMe, follow [steps.MD](steps.MD).

## WiFi fallback

On boot the Pi tries known networks (and Ethernet). If there is no internet for ~45s, it raises a WPA2 AP:

| | |
| --- | --- |
| SSID | `{hostname}-setup` |
| Password | `raspi-setup` |
| Portal | `http://10.42.0.1` |

Join from your phone, pick the venue WiFi, and the AP shuts down.

On the Pi (clones public `main` if this tree is not already there):

```bash
curl -fsSL https://raw.githubusercontent.com/spaguetti-nomad-pi/spaguetti-nomad-pi/main/first_boot/setup.sh | bash
```

Or, from a clone:

```bash
sudo ./first_boot/setup.sh
```

Logs: `journalctl -u wifi-fallback -f`

To try the AP: disconnect Ethernet and forget/disable saved WiFi. After ~45s join `{hostname}-setup` / `raspi-setup` and open `http://10.42.0.1`.

Details: [wifi-fallback/README.md](wifi-fallback/README.md).

Telegram bot (talk to the Pi with no UI): [telegram/README.md](../telegram/README.md).
