# WiFi fallback

If the Pi has no internet, it raises a WPA2 AP and a captive portal so you can pick a venue network. It is an app: `apps/wifi-fallback`. First Pi: [FLASH.md](../../FLASH.md) then `setup.sh` at the repo root (`wifi-fallback` is enabled by default).

| | |
| --- | --- |
| SSID | `{hostname}-setup` |
| Password | `raspi-setup` |
| Portal | `http://10.42.0.1` |

1. Ethernet and saved WiFi are tried first.
2. Still offline after ~45s (or ~120s after boot if a saved client network exists), the AP comes up.
3. Join from your phone. If the portal does not open, go to `http://10.42.0.1`.
4. Submit SSID + password. The AP goes down; that network is saved in NetworkManager (`autoconnect`).

Ethernet with a working link: the AP does **not** start (SSH still works).

```bash
apps status
sudo apps logs wifi-fallback
# journalctl -u wifi-fallback -f
```

Live config is `/etc/wifi-fallback/wifi-fallback.env` (not overwritten on `apps up`). Optional gitignored copy: `wifi-fallback.env` next to this README.

## Test

1. With Ethernet: the AP must not appear.
2. Unplug Ethernet and forget/disable known WiFi: after the grace, `{hostname}-setup` appears.
3. Submit a network in the portal and SSH on the LAN again.

## Uninstall

```bash
sudo apps disable wifi-fallback
sudo ./apps/wifi-fallback/uninstall.sh
```

Client WiFi profiles added from the portal stay in NetworkManager.
