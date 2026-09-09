# WiFi fallback

If the Pi has no internet, it raises a WPA2 AP and a captive portal so you can load the venue WiFi.

## Usage

| | |
| --- | --- |
| SSID | `{hostname}-setup` |
| Password | `raspi-setup` |
| Portal | `http://10.42.0.1` |

1. The Pi tries Ethernet and WiFi networks already saved in NetworkManager.
2. If it stays offline ~45s, `{hostname}-setup` appears.
3. Join from your phone. If the portal does not open, go to `http://10.42.0.1`.
4. Pick SSID + password. The AP goes down and the Pi is on the LAN.

Ethernet with a network: the AP **does not** start (SSH still works).

## Install

On the Pi:

```bash
curl -fsSL https://raw.githubusercontent.com/spaguetti-nomad-pi/spaguetti-nomad-pi/main/first_boot/setup.sh | bash
```

That clones public `main` if needed and runs `install.sh`. From an existing clone: `sudo ./first_boot/setup.sh`.

Copy `wifi-fallback.env.example` to `wifi-fallback.env` if you want local overrides (gitignored). On the Pi the live file is `/etc/wifi-fallback/wifi-fallback.env` (not overwritten on reinstall).

```bash
journalctl -u wifi-fallback -f
```

## Test

1. With Ethernet: the AP must not appear.
2. Unplug Ethernet and forget/disable known WiFi: after ~45s `{hostname}-setup` appears.
3. Submit a network in the portal and check SSH on the LAN again.

## Uninstall

```bash
sudo ./first_boot/wifi-fallback/uninstall.sh
```

Client WiFi networks you added from the portal stay in NetworkManager.
