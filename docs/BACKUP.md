# Backup disk (USB B)

The Pi’s NVMe is disposable. USB A (`/vault`) is the live data. **USB B** is the copy of A (and, later, a small stash of `/etc` tokens). This file is how B is born, opened, closed, and why a freshly minted ext4 can still say `Structure needs cleaning`.

Restic is not here yet. Format and unlock are.

Wipe commands destroy the **target** disk. Confirm with `lsblk` every time. Never run them against `nvme0n1` (OS) or `mmcblk0` (SD).

---

## What this disk is

| | |
| --- | --- |
| Role | Encrypted restic repo of `/vault` (when A exists). Optional copy of `/etc/wifi-fallback`, `/etc/telegram`, `/etc/apps`. |
| Layout | GPT → one partition → LUKS2 → ext4 labeled `backup` → mounted at `/backup` |
| Size | At least as large as A; bigger if you want history. 500 GB is enough to start. |
| Auto-mount | **No.** Unlock is a human step. A keyfile on the NVMe would make LUKS theater. |

Restic already encrypts its repo. LUKS on B is the second door: a stray `rsync` in the clear, a zip of `/etc`, or a future file that is not restic, still sits on a locked disk.

Use a **different** passphrase from A. Same bag + same phrase = one theft opens both.

A 2.5" mechanical drive in a USB enclosure is fine for occasional snapshots. It is not a vault SSD. Expect tens of MB/s, not hundreds.

---

## Identify the device

Pi, with the USB plugged in:

```bash
lsblk -o NAME,SIZE,TYPE,FSTYPE,LABEL,MOUNTPOINT,MODEL,TRAN
ls -l /dev/disk/by-id/
```

You want the ~500 GB (or whatever) disk on `tran=usb`, **not** the NVMe, **not** the SD. Prefer a stable path:

```text
/dev/disk/by-id/ata-<MODEL>_<SERIAL>
```

`/dev/sda` moves if you plug another stick. `by-id` does not (until you change the enclosure).

Set it once per session:

```bash
DISK=/dev/disk/by-id/ata-YOUR_MODEL_YOUR_SERIAL
lsblk "$DISK"
```

If `lsblk` does not show the size you expect, **stop**.

---

## USB bridges and UAS (read this before the first `mkfs`)

Many SATA↔USB chips (ASMedia `174c:55aa` is the usual suspect) speak **UAS**. Under a large write — `mkfs.ext4` on 500 GB — the bridge aborts commands, the kernel resets SuperSpeed, and ext4’s group descriptors become garbage:

```text
mount: /backup: Structure needs cleaning.
EXT4-fs: group descriptors corrupted!
```

`dmesg` will show `uas_eh_abort_handler` and `reset SuperSpeed USB device`. That is the enclosure, not “ext4 is broken.”

```bash
lsusb
```

If you see `174c:55aa` (ASMedia ASM105x / 1153), disable UAS **before** formatting. Other `vid:pid` pairs use the same pattern.

```bash
echo 'options usb-storage quirks=174c:55aa:u' | sudo tee /etc/modprobe.d/disable-uas.conf
```

Append to the **existing single line** in `/boot/firmware/cmdline.txt` (do not add a second line):

```text
usb-storage.quirks=174c:55aa:u
```

```bash
sudo reboot
```

A good boot log:

```text
usb 2-1: UAS is ignored for this device, using usb-storage instead
usb-storage: Quirks match for vid 174c pid 55aa
```

`usb-storage` is slower than UAS and much more honest. Throughput of ~10 MB/s on an old 5400 rpm disk over USB+LUKS is ugly and **real**. A `dd` that reports 2 GB/s wrote to RAM; that is not a disk test.

---

## Create (once)

Needs `cryptsetup` and `gdisk`:

```bash
sudo apt-get install -y cryptsetup gdisk
```

Unmount anything already on that disk, then wipe **only** `$DISK`:

```bash
sudo umount "${DISK}-part1" "${DISK}-part2" 2>/dev/null || true
sudo wipefs -a "$DISK"
sudo sgdisk --zap-all "$DISK"
sudo sgdisk -n 1:0:0 -t 1:8300 -c 1:backup "$DISK"
```

LUKS (type `YES` in capitals, passphrase twice):

```bash
sudo cryptsetup luksFormat --type luks2 "${DISK}-part1"
sudo cryptsetup open "${DISK}-part1" backup
```

`backup` is the mapper name → `/dev/mapper/backup`. It is not a folder yet.

```bash
sudo mkfs.ext4 -L backup /dev/mapper/backup
```

On a mechanical USB disk, `Creating journal` can sit there for minutes. It is not a prompt. If it asks `contains a ext4 file system… Proceed anyway?` after a failed first try, `y` is the broken filesystem you are replacing.

```bash
sudo mkdir -p /backup
sudo mount /dev/mapper/backup /backup
df -h /backup
lsblk -o NAME,SIZE,FSTYPE,LABEL,MOUNTPOINT
```

You want something like: `sda1` = `crypto_LUKS`, mapper `backup` = `ext4` / `/backup`, tens or hundreds of GB `Avail`.

If `mount` says `Structure needs cleaning` and `dmesg` is full of UAS resets: close the mapper, fix quirks, reboot, `cryptsetup open` again (or `luksFormat` if the header died), `mkfs` again. Do not `e2fsck` a filesystem whose bitmaps are random.

---

## Open (every boot, when you need B)

Reboot does **not** keep the mapper. That is the point.

```bash
DISK=/dev/disk/by-id/ata-YOUR_MODEL_YOUR_SERIAL
sudo cryptsetup open "${DISK}-part1" backup
sudo mount /dev/mapper/backup /backup
```

1. `open` — passphrase in, kernel exposes the plaintext block device.
2. `mount` — ext4 appears at `/backup`.

Until both succeed, there is nothing to write to.

Not in `fstab`, not a keyfile on the NVMe. You are the key.

---

## Close (before unplug, or when idle)

```bash
sudo umount /backup
sudo cryptsetup close backup
```

1. `umount` — no process has files open; journal is flushed.
2. `close` — mapper gone; `sda1` is noise again. Safe to pull USB.

Unplugging while mounted is how you get `needs cleaning` the honest way (not UAS — you). The drive may also click in protest.

`cryptsetup close` fails if something still has `/backup` or `/dev/mapper/backup` open (`lsof /backup`, `fuser -mv /backup`).

---

## Change the passphrase

No reformat. Data stays.

```bash
sudo cryptsetup luksChangeKey "${DISK}-part1"
```

Old passphrase, then new twice.

```bash
sudo cryptsetup luksAddKey "${DISK}-part1"      # second slot
sudo cryptsetup luksRemoveKey "${DISK}-part1"   # drop one
sudo cryptsetup luksDump "${DISK}-part1"        # which slots are live
```

Lose every passphrase: the disk is a paperweight. There is no backdoor.

---

## Prove the disk, not the cache

`dd` without `oflag=direct` finishes in 0.1 s at “2 GB/s”. That was RAM. `sync` then hits the platters — if it returns, the flush worked, but you did not measure.

```bash
sudo dd if=/dev/zero of=/backup/write-test bs=1M count=256 oflag=direct status=progress
sudo rm /backup/write-test
dmesg -T | grep -iE 'uas_eh|I/O error|reset SuperSpeed' | tail
```

Read the `dd` line:

| What you see | Meaning |
| --- | --- |
| `256+0 records in/out` | 256 × 1 MiB = 256 MiB written |
| `9.2 MB/s`, ~30 s | Direct I/O to an old USB HDD + LUKS + `usb-storage`. Ugly, consistent, usable for restic now and then. |
| `2.4 GB/s`, 0.1 s | Page cache. Not a test. |
| `uas_eh` / SuperSpeed reset **during** `dd` | Bridge still flaking. Quirk missing or bad cable/power. |

`I/O error` lines **stamped at boot** (same second as USB enumerate) are the kernel poking `sda` before the partition table settled. Ignore those if the later `dd` is clean.

A healthy 2.5" 5400 rpm in a cheap enclosure over USB2-ish/`usb-storage` often lands **8–40 MB/s**. A USB3 SSD after a working UAS (or a good BOT bridge) should be **100 MB/s+**. If you need that, change the disk, not `mkfs` flags.

---

## After a reboot

`lsblk` will show `sda1` as `crypto_LUKS` and **no** `/backup`. Open as above. Leaving B locked when you are not snapshotting is correct.

---

## Later: restic

When `/vault` exists:

- Repo path: `/backup/restic` (or similar), only while B is unlocked.
- Restic password ≠ LUKS passphrase of A or B.
- A systemd timer on the Pi, not “the laptop remembers.”
- Telegram can say backup OK / stale; it should not hold the restic password in chat.

Until then, `/backup` can stay empty. An empty encrypted disk is still a finished B.

---

## Do not

- Format `nvme0n1` or `mmcblk0`.
- Put B in `fstab` with a keyfile on the NVMe “so it is convenient.”
- Use exFAT/NTFS for the restic repo (permissions, sparse files, a Pi-only workload).
- Share one passphrase across A and B.
- Trust a `mkfs` that ran during UAS resets.
- Yank the USB with `/backup` mounted.
