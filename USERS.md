# Users, credentials, and who got in

[FINDING.md](FINDING.md) is how you reach the box. This is who you are *on* the box: accounts, hashes, sudo, SSH keys, and the audit trail that says someone logged in.

A Unix user is not a profile picture. It is a uid, a set of groups, a password hash (or none), a shell, and a home directory whose `~/.ssh/authorized_keys` is a second, independent authenticator. Confuse those pieces and you will “change the password” while still being wide open on a key you forgot, or lock yourself out of SSH while `root` is fine on a serial console you do not have.

On this Pi there is no default `pi`/`raspberry`. Raspberry Pi OS since Bookworm creates the first user at imaging time (`userconf`). Whatever name you typed in Imager is the only human account until you add another.

Telegram `/logins` runs [scripts/security/logins.sh](scripts/security/logins.sh): current sessions, `last`, failed SSH in the last 7 days. Read-only. This document is what those numbers *mean*, and how to change the underlying state.

---

## 1. The files that *are* the user

| File | Role |
| --- | --- |
| `/etc/passwd` | public map: `name:x:uid:gid:gecos:home:shell`. The `x` means “hash lives in shadow” |
| `/etc/shadow` | hashes, aging, lock flags. mode `640`, group `shadow`. If you can read this, you can offline-crack |
| `/etc/group` | group name → gid → members |
| `/etc/gshadow` | group passwords (almost unused; sudo is the real gate) |
| `/etc/sudoers`, `/etc/sudoers.d/*` | who may become uid 0, and how |
| `/etc/ssh/sshd_config`, `sshd_config.d/*` | which authenticators `sshd` will even *try* |
| `~/.ssh/authorized_keys` | user keys `sshd` accepts for that account |
| `/etc/hostname` | not a user. Changing it does not change logins |

`getent passwd` is the right reader: it goes through NSS (`/etc/nsswitch.conf`). `cat /etc/passwd` is usually the same on a stock Pi; it is not the same if you ever add SSSD/LDAP.

A row you will see on every Debian box:

```
root:x:0:0:root:/root:/bin/bash
```

uid 0 is root, regardless of the name. `toor`, `admin`, a renamed `root` — if the third field is `0`, it is root. Do not “hide root” by renaming it and call that security.

Human accounts start at uid 1000. Everything below is a service user (`sshd`, `avahi`, `messagebus`). They should have `/usr/sbin/nologin` or `/bin/false`. A service user with `/bin/bash` and a hash is a gift.

---

## 2. Authentication is a stack, not a password

When you `ssh grekoebb@spagueti.local`:

```
sshd
  ├─ host key  (is this the machine you think?  → known_hosts)
  └─ user auth
       ├─ publickey  → ~/.ssh/authorized_keys  (PAM is not in this path by default)
       └─ password   → PAM → pam_unix → /etc/shadow
```

Two consequences people miss:

1. **Changing the password does not revoke keys.** A laptop that still has a line in `authorized_keys` will keep getting in. Revoke keys by deleting lines, or `ssh-keygen -R` on the *client* does nothing to the server.
2. **Installing a key does not disable the password.** `PasswordAuthentication yes` (the Raspberry Pi OS default) means the hash in shadow is still a live door. After the key works, close that door.

`sshd -T` dumps the *effective* config (includes drop-ins). Believe that, not a comment in a file you did not read.

```bash
sudo sshd -T | grep -E '^(passwordauthentication|pubkeyauthentication|permitrootlogin|kbdinteractiveauthentication|maxauthtries|allowusers|denyusers|port) '
```

Bookworm’s OpenSSH uses `KbdInteractiveAuthentication` as the modern name for keyboard-interactive / PAM prompts. If that is `yes` and `PasswordAuthentication` is `no`, you can still get a password prompt. Set both.

---

## 3. Passwords: hash, lock, age

### Change yours

```bash
passwd
```

It asks for the current one, then the new one twice. PAM enforces quality (`pam_unix` + `pam_pwquality` if installed). A 12-character memorable sentence beats a short password that has ever lived in a chat screenshot.

### Change someone else’s

```bash
sudo passwd alice
```

No old password required. You are already uid 0.

Non-interactive (scripts, first-boot only — the password hits the process list and the journal if you are sloppy):

```bash
echo 'alice:newpass' | sudo chpasswd
```

Prefer `chpasswd` over `passwd` in pipes. Never commit the string. Never put it in Telegram.

### What `shadow` actually stores

```
alice:$y$j9T$...salt...$...hash...:20000:0:99999:7:::
```

Fields: name, hash, last-change (days since 1970-01-01), min age, max age, warn, inactive, expire, reserved.

`$y$` is yescrypt (Debian 12 default). `$6$` is SHA-512 crypt. `$1$` is MD5 crypt — treat as plaintext. An empty hash field or `!` / `*` means “no password auth”:

| Hash field | Meaning |
| --- | --- |
| `$y$…` / `$6$…` | password login possible |
| `!` or `!!` | locked (`passwd -l` / `usermod -L`). Key login still works |
| `*` | locked at creation, typical for service users |
| empty | passwordless — a bug on a networked host |

`passwd -l alice` prefixes `!` to the hash. It does **not** remove keys. `passwd -u` unlocks.

`chage -l alice` is the readable view of aging. `sudo chage -d 0 alice` forces a change at next login — useful after you set a bootstrap password.

If you ever pasted a password into chat, mail, or a screenshot: it is burned. `passwd`, then assume the old one is public.

---

## 4. Users and groups

Debian has two families of tools. On the Pi, use the `adduser` / `deluser` wrappers; they create a home, copy `/etc/skel`, and pick the next uid.

```bash
sudo adduser bob                 # interactive: home, hash, gecos
sudo adduser bob sudo            # secondary group
sudo deluser --remove-home bob   # only when you mean it
```

`useradd` is the low-level binary. It will happily create an account with no home and a locked hash if you omit flags. Fine in Ansible; easy to botch by hand.

```bash
id                              # uid, gid, groups of the current process
id bob
getent passwd bob
groups bob
```

Groups that matter on a Pi:

| Group | Why it exists |
| --- | --- |
| `sudo` | passworded uid 0 via `/etc/sudoers` |
| `adm` | read `/var/log` |
| `netdev` | NetworkManager / `nmcli` without root on some setups |
| `gpio` `spi` `i2c` `video` `render` `input` | hardware nodes in `/dev` |
| `docker` | **equivalent to root.** The socket is uid 0. Do not treat this as a convenience group |

`usermod -aG docker alice` is a privilege escalation you chose. Same for writing `/etc/sudoers.d/alice` with `NOPASSWD: ALL`.

### sudo, correctly

```bash
sudo -l                         # what *you* may run
sudo visudo                     # edit sudoers with a syntax check
sudo visudo -f /etc/sudoers.d/alice
```

Stock Raspberry Pi OS:

```
%sudo   ALL=(ALL:ALL) ALL
```

That is “members of `sudo` may run anything, after their *user* password.” It is not the root password. If you never set a root hash (`sudo passwd -l root` is the default posture), there is no root password to steal — only your user’s.

`NOPASSWD` is for units and scripts (`telegram` should not need it; the bot drops to a dedicated user or uses specific commands). Do not put `NOPASSWD: ALL` on the human account “because it is a Pi.”

---

## 5. SSH keys: the credential that should replace the password

On the **laptop**, one key per role, not one key for the universe:

```bash
ssh-keygen -t ed25519 -f ~/.ssh/id_ed25519_raspi -C "raspi"
```

The private half never copies to the Pi. The public half does.

On the **Pi**, as the user you SSH into:

```bash
umask 077
mkdir -p ~/.ssh
# one line, the entire .pub file
echo 'ssh-ed25519 AAAA... raspi' >> ~/.ssh/authorized_keys
chmod 700 ~/.ssh
chmod 600 ~/.ssh/authorized_keys
```

`sshd` refuses the file if the home or `.ssh` is group/world writable. That looks like “key does not work.” It is permissions.

`authorized_keys` accepts options. Use them when the key is on a machine you do not fully trust:

```
from="192.168.0.0/16,10.0.0.0/8",restrict ssh-ed25519 AAAA... laptop
```

`restrict` turns on a pile of `no-agent-forwarding,no-port-forwarding,no-pty,…`. You will add back `pty` if you want a shell. `command="/opt/telegram/…"` is how you make a key that can only run one thing.

Prove the key *before* you disable passwords:

```bash
ssh -o BatchMode=yes -o IdentitiesOnly=yes -i ~/.ssh/id_ed25519_raspi user@host 'echo ok'
```

Then, on the Pi, drop a snippet — do not edit the vendor file:

```bash
sudo tee /etc/ssh/sshd_config.d/99-hardening.conf >/dev/null <<'EOF'
PasswordAuthentication no
KbdInteractiveAuthentication no
PermitRootLogin no
AllowUsers grekoebb
EOF
sudo sshd -t && sudo systemctl reload ssh
```

Keep one session open until a second session with the key works. `AllowUsers` is a default-deny on account names; a guessed `pi` or `ubuntu` dies before PAM.

`IdentitiesOnly yes` on the **client** (`~/.ssh/config`) stops the agent from offering every key. `sshd` counts each failed key toward `MaxAuthTries` (default 6). Six keys in the agent plus a password attempt is a lockout that looks like “the password is wrong.”

Client stanza that matches this repo’s machine:

```
Host raspi
    HostName spagueti.local
    HostKeyAlias spagueti
    User grekoebb
    IdentityFile ~/.ssh/id_ed25519_raspi
    IdentitiesOnly yes
    ServerAliveInterval 60
```

---

## 6. Who is on the box, and who tried

These are different databases. Do not use one as a proxy for the others.

| Command | Source | What it answers |
| --- | --- | --- |
| `who` / `w` | `/var/run/utmp` | sessions **now** (pts, source IP, idle) |
| `loginctl` | systemd-logind | same idea, including lingering / graphical |
| `last` | `/var/log/wtmp` | historical logins, including `still logged in` and reboots (`last reboot`) |
| `lastlog` | `/var/log/lastlog` | last login **per account**, sparse file indexed by uid |
| `lastb` | `/var/log/btmp` | failed logins. needs root. empty if `sshd` never wrote it |
| `journalctl -u ssh` | journal | what `sshd` actually said: accepted publickey, failed password, invalid user |

```bash
who
w
last -n 20
sudo lastb -n 20
lastlog
sudo journalctl -u ssh --since "7 days ago" | grep -E 'Accepted|Failed|Invalid'
```

`wtmp`/`btmp` rotate (`/etc/logrotate.d/wtmp`). `last` without `-f` only sees the current file. For a longer horizon:

```bash
last -F -f /var/log/wtmp
sudo last -F -f /var/log/wtmp.1
```

`journalctl` survives that. It is the source of truth for SSH; `last` is the source of truth for “a login session existed” (including local console). A successful key login appears in **both**. A failed password appears in the journal and usually `btmp`, never in `wtmp`.

Reading a line:

```
grekoebb  pts/0  192.168.0.163  Wed Sep  9 18:47  still logged in
```

- user
- tty (`pts/0` = SSH, `tty1` = local)
- origin (`192.168.0.163` or a hostname). `0.0.0.0` or empty on some failed records
- start, end / `still logged in` / `crash`

`sshd` logs `Accepted publickey for grekoebb from 192.168.0.163 port 52311 ssh2: ED25519 SHA256:…`. That fingerprint is the key that got in. Compare it with `ssh-keygen -lf ~/.ssh/id_ed25519_raspi.pub` on the laptop.

Invalid users (`Failed password for invalid user admin`) are noise on a password-open `sshd` facing a LAN. They become a signal if the Pi is ever on a prefix you do not control. Count them; do not obsess.

The Telegram command is a summary, not a SIEM:

```bash
./scripts/security/logins.sh
./scripts/security/ports.sh
```

`/ports` (`ss -lntup`) tells you what is *listening*. A login story without a listen story is incomplete: `sshd` on `0.0.0.0:22` is expected; something bound to `*:0` you do not recognize is not.

---

## 7. Procedure: from “I got in with a chat password” to a sane box

You have a shell as the human user. Do this in order. Do not skip the verify step.

1. **See who you are.** `id`, `sudo -l`, `getent passwd $USER`. Confirm you are in `sudo`.
2. **Install the laptop key** (section 5). Leave this SSH session open.
3. **From a second terminal**, `ssh raspi` with `BatchMode` and `IdentitiesOnly`. If that fails, stop. Do not disable passwords.
4. **`passwd`** — new hash, not a variation of the old one, not a string that has ever been in a chat.
5. **Drop `99-hardening.conf`**, `sshd -t`, `systemctl reload ssh`. Third terminal: key still works. Password from a fourth: `Permission denied (publickey)`.
6. **Lock root’s password** if it was ever set: `sudo passwd -l root`. Keep `PermitRootLogin no`.
7. **Audit keys:** `cat ~/.ssh/authorized_keys`. One line per machine you own. Delete the rest.
8. **Audit accounts:** `getent passwd | awk -F: '$3>=1000 && $3<65534 {print}'`. Every extra human is a decision. `sudo passwd -l` leftovers; `deluser` what you do not want.
9. **Look back:** `last -n 20`, `sudo journalctl -u ssh --since today`. You should see *your* key acceptances and nothing else you cannot explain.

If you need a second human: `adduser`, put them in `sudo` only if they get uid 0, give them *their* key, never share `id_ed25519_raspi`.

---

## 8. Things that look like security and are not

**Renaming `root` or the human user “so they cannot guess it.”** `AllowUsers` is the filter. Security by obscure account names dies on `getent`.

**A long password and `PasswordAuthentication yes` on every café LAN.** The hash is strong; the prompt is still a door. Keys + `PasswordAuthentication no`.

**`passwd -l` on an account you are angry at, leaving their keys.** They will be back.

**Disabling `sshd` “to be safe” on a headless Pi.** You just invented a brick the next time Wi‑Fi moves. Harden it; do not remove the only console.

**fail2ban on a box that is not reachable from the internet.** Harmless, usually useless. Isolation and `AllowUsers` already did the job. If you ever expose 22, then talk about banlists.

**Sharing the user password as the Wi‑Fi password, the sudo password, and the Telegram token.** One leak opens three systems. The strings in a notes app from first boot are a museum, not a vault.

**`chmod 777 ~/.ssh` to “make the key work.”** `sshd` will ignore the file. The fix is tighter, not looser: `700` / `600`, owner = the user.

---

## 9. What “secure enough” means on a portable Pi

This machine will sit on networks you do not own. The threat is not a nation-state; it is the next guest on the same AP and whoever has your old WhatsApp backup.

Minimum that matches the rest of this repo:

- one human account, in `sudo`, key-only SSH
- `PermitRootLogin no`, `PasswordAuthentication no`, `AllowUsers` that account
- host key pinned on the laptop (`HostKeyAlias`, see [FINDING.md](FINDING.md))
- no inbound from the internet; Telegram polls out; later an overlay mesh
- `/logins` and `/ports` as a habit, not a dashboard you never open

Everything else (2FA, hardware keys, SELinux) is optional until the above is true. Do the boring things first.
