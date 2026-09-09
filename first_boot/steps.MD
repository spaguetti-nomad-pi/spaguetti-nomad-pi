# Flash Lite onto the NVMe (Raspberry Pi 5)

Move from an SD card running Raspberry Pi OS **Desktop** to **Lite** on the NVMe, then SSH in.

Wipe and flash commands destroy the target disk. Confirm the device with `lsblk` before every destructive step. The SD is `mmcblk0`; the NVMe is usually `nvme0n1`.

When Lite is up and SSH works, install the fallback AP from [README.md](README.md).

---

## 1. Update the SD system

Pi booted from the SD (Desktop):

```bash
sudo apt update && sudo apt full-upgrade -y
```

If `dpkg` is stuck:

```bash
sudo dpkg --configure -a
```

## 2. Install Imager

```bash
sudo apt install rpi-imager -y
```

## 3. Get Raspberry Pi OS Lite (64-bit)

1. Open [the Lite arm64 image index](https://downloads.raspberrypi.com/raspios_lite_arm64/images/).
2. Enter the newest folder.
3. Download `*-arm64-lite.img.xz`.

Example name (yours will differ):

```text
2025-12-04-raspios-bookworm-arm64-lite.img.xz
```

## 4. Identify the NVMe

```bash
lsblk
```

Note the whole disk (e.g. `/dev/nvme0n1`), not a partition (`nvme0n1p1`). Do not use `/dev/mmcblk0`.

## 5. Wipe the NVMe

Filesystem signatures and the partition table:

```bash
sudo wipefs -a /dev/nvme0n1
sudo sgdisk --zap-all /dev/nvme0n1
```

Replace the device if `lsblk` showed another name.

## 6. Flash Lite

```bash
sudo rpi-imager --cli 2025-12-04-raspios-bookworm-arm64-lite.img.xz /dev/nvme0n1
```

Use your `.img.xz` filename and the device from step 4. Imager writes the user, hostname, and SSH settings you configured in the UI — or pass them on the CLI if you use a fully headless flow.

## 7. Boot from NVMe first

**A — raspi-config**

```bash
sudo raspi-config
```

Advanced Options → Boot Order → NVMe/USB Boot.

**B — EEPROM by hand**

```bash
sudo rpi-eeprom-config --edit
```

Keep or add:

```text
BOOT_ORDER=0xf416
```

`0xf416` tries NVMe, then USB, then SD. See the [bootloader docs](https://www.raspberrypi.com/documentation/computers/raspberry-pi.html#BOOT_ORDER) if you need another order.

## 8. Reboot and pull the SD

```bash
sudo reboot
```

When it comes back, remove the SD. The Pi should now run from the NVMe.

## 9. SSH from another machine

Same LAN:

```bash
ssh YOUR_USER@YOUR_HOSTNAME.local
```

If `.local` does not resolve, find the lease (router DHCP table, or a scan of *your* prefix):

```bash
nmap -sn 192.168.0.0/24
ssh YOUR_USER@192.168.0.x
```

Then install the AP: [README.md](README.md).
