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

From the repo root (your fork; see [cicd/README.md](../cicd/README.md)):

```bash
sudo ./first_boot/wifi-fallback/install.sh
```

Logs: `journalctl -u wifi-fallback -f`

Details and tests: [wifi-fallback/README.md](wifi-fallback/README.md).
