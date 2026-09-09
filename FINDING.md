# Finding and reaching the Pi

This is not “scan the LAN and SSH.” It is how a host *exists* on a network, how discovery protocols lie, and how to tell **I found a machine** from **I can log into that machine**.

Assume you already know TCP/IP, processes, and public-key crypto. The rest is field work.

If the Pi is offline on purpose, this document does not apply: it will raise `{hostname}-setup` (see [first_boot/README.md](first_boot/README.md)) and you join *that* AP, not the venue LAN.

---

## 1. What “connected to Wi‑Fi” actually means

A station associated to an SSID has:

1. **L2 membership** — it can send 802.11 frames to the AP.
2. **Usually an IPv4 lease** — DHCP put `address/prefix` and a default route in its table.
3. **Optionally IPv6** — link-local `fe80::/10` always (if IPv6 is on); GUA only if the LAN has RA/DHCPv6.

None of that implies *you* can talk to it.

The AP is a switch with a radio. Between two clients the path is:

```
you  --802.11--  AP  --802.11--  Pi
```

The AP may:

- **bridge** clients (normal home LAN) → unicast IP works, ARP completes, SSH works.
- **isolate** clients (`AP isolation` / `client isolation` / guest network) → the AP accepts each station’s traffic toward the uplink and drops station-to-station unicast.
- **help mDNS** (Chromecast / AirPlay proxies) while still isolating unicast. Then the Pi is *visible* and *unreachable*. That is not a paradox; multicast and unicast are different forwarding rules.

Same SSID is not same L2. Band steering, a 2.4 / 5 GHz split that is two BSSIDs, a guest VLAN, or a travel router behind the venue router all produce “I joined Wi‑Fi” with no path to the other host.

**Failure classification** (memorize this; it replaces guessing):

| Symptom | Layer you are in |
| --- | --- |
| Association failed / no SSID | radio / 802.11 |
| Has an IP, `ping` → `100% loss`, ARP `(incomplete)` | L2: nobody answered `who-has` |
| `No route to host` on a *connected* prefix | almost always the above, not a missing route |
| `Operation timed out` | packet left, nothing came back (filter, wrong host, isolation that blackholes) |
| `Connection refused` | IP is right; nothing listens on that port |
| `Permission denied (publickey)` | you reached **sshd**; the credential is wrong |

On a connected route (`192.168.0.0/24 dev en0`), the kernel does not “lack a route” to `192.168.0.59`. It sends ARP. If ARP never completes, macOS/Linux surfaces `EHOSTUNREACH` — “No route to host.” The routing table is fine. The neighbor table is empty.

---

## 2. Identity: four names for the same object

DHCP addresses are ephemeral. Do not treat them as identity.

| Name | Stable? | What it actually is |
| --- | --- | --- |
| IPv4 lease | no | a row in the router’s DHCP table |
| mDNS name (`SPAGUETI.local`) | as stable as the hostname | Avahi/Bonjour publishing A/AAAA + PTR |
| MAC | yes, until you clone it | 48-bit L2 address; Raspberry Pi Trading OUIs include `2c:cf:67`, `d8:3a:dd`, `e4:5f:01`, `b8:27:eb` |
| SSH host key | yes, until you reimage | the cryptographic identity of *that* `sshd` |

The useful identity for humans is **hostname + host key**. The useful identity for L2 forensics is the **MAC**. The lease is a cache.

`~/.ssh/known_hosts` is a ledger of host keys you already accepted (TOFU). If you ever SSH’d to `spagueti.local` or to an old lease, those lines are still there. They tell you “this key existed,” not “this IP is live.”

`~/.ssh/config` `HostName 192.168.1.41` is a *stale cache with extra privileges*. It will send you to a dead address on another prefix the moment the Pi gets a new lease. Prefer:

```
Host raspi
    HostName spagueti.local
    User greko
    IdentityFile ~/.ssh/id_ed25519_raspi
    IdentitiesOnly yes
    ServerAliveInterval 60
```

`.local` is not DNS. It is multicast DNS (RFC 6762) on `224.0.0.251:5353` / `ff02::fb`. If mDNS is blocked, that `HostName` fails closed — which is better than succeeding toward the wrong box.

---

## 3. Link-local IPv6 is not optional knowledge

Every IPv6 interface has a link-local address in `fe80::/10`. It is scoped: `fe80::1` on `en0` is not `fe80::1` on `en1`. You must write the scope:

```bash
ping6 'fe80::2ecf:67ff:fef0:c7d4%en0'
ssh greko@fe80::2ecf:67ff:fef0:c7d4%en0
```

The `%en0` is part of the address in the UI. Without it the stack correctly says it does not know which link.

If the AP did not assign a useful IPv4, or IPv4 unicast is flaky, IPv6 LL still works **on the same broadcast domain**. It is often the first path that comes up.

### EUI-64 from the MAC (you can compute the LL)

SLAAC’s modified EUI-64 (RFC 4291):

1. Take the MAC: `2c:cf:67:f0:c7:d4`
2. Split in half, insert `ff:fe`: `2c:cf:67:ff:fe:f0:c7:d4`
3. Flip the U/L bit of the first byte (`2c` → `2e`)
4. Prefix `fe80::` and compress: `fe80::2ecf:67ff:fef0:c7d4`

If mDNS gives you a MAC (`SPAGUETI [2c:cf:67:f0:c7:d4]`) you already have the IPv6 LL. You do not need the IPv4 lease to try SSH.

Privacy extensions (RFC 4941) add *extra* temporaries. The EUI-64 address usually still exists next to them on a Pi.

---

## 4. Discovery is a stack, not a button

Work top-down. Each layer is cheaper and more honest than a full sweep.

### 4.1 Remembered coordinates (lowest cost, highest rot)

```bash
ssh -o ConnectTimeout=5 -o BatchMode=yes raspi 'hostname; hostname -I'
```

`BatchMode=yes` = do not prompt for a password. You want a clean fail.

If this times out, the cache is wrong. Do not “try harder” on the same IP for five minutes. Change layer.

### 4.2 mDNS / DNS-SD (the Pi advertising itself)

Raspberry Pi OS runs Avahi. It publishes at least `_workstation._tcp` (the hostname plus MAC) and, if `sshd` is integrated, sometimes `_ssh._tcp`.

macOS:

```bash
dns-sd -t 4 -B _workstation._tcp local.
dns-sd -t 4 -B _ssh._tcp local.
dscacheutil -q host -a name SPAGUETI.local
```

Linux:

```bash
avahi-browse -t _workstation._tcp
getent hosts SPAGUETI.local
```

`dns-sd` “Add” on your Wi‑Fi interface means a packet arrived on that link. That is stronger evidence than a DHCP UI screenshot.

Caveat: mDNS caches. A dead host can linger. Cross-check with a neighbor probe (next section) before you believe the IPv4.

`.local` resolution on macOS goes through the system resolver, not `/etc/hosts`. `ping SPAGUETI.local` and `dscacheutil` can disagree with `dig` — `dig` talks to your recursive DNS, which does **not** speak mDNS unless you set up a unicast-DNS bridge.

### 4.3 Neighbor tables (ARP / NDP)

```bash
# macOS
arp -an
ndp -an

# Linux
ip neigh
```

Reading the table:

- `MAC + ifscope` — you have L2 reachability *right now*.
- `(incomplete)` — you sent `who-has` and nobody answered. Isolation, wrong prefix, or the host is not there.
- empty — you have not tried yet. Absence of a row is not absence of a host.

ARP is not a discovery protocol you query globally. It is filled as a side effect of IPv4 unicast. NDP is the IPv6 analogue (`Neighbor Solicitation` to a solicited-node multicast). That is why `ping6` to the LL address can populate state that an IPv4 ping never could.

### 4.4 Active sweeps — and why they lie

A ping sweep (`for i in 1..254; ping 192.168.0.$i`) assumes:

- the host answers ICMP Echo,
- the AP forwards those unicasts,
- your process actually waited for replies (a naive `&` / `wait` loop on macOS is a good way to miss everyone).

Plenty of hosts drop ICMP. Plenty of APs drop client-to-client. You get a picture of **who answers ping**, not **who is on the LAN**.

`nmap -sn 192.168.0.0/24` on Ethernet uses ARP and is honest. On Wi‑Fi with isolation it will report *you* and maybe the AP. That is a true picture of reachable L3, not of associated stations.

`nmap -Pn -p 22 192.168.0.59` skips the host-discovery guess and hits the port. Use it when you already have a candidate from mDNS.

Do not port-scan the whole prefix “to be sure.” You already have better oracles.

### 4.5 The router’s DHCP table

The only authoritative IPv4 list is the DHCP server (the AP’s admin UI, `Status → LAN`, etc.). Use it when multicast is dead. Treat it as a hint: a lease can be held by a host that is no longer associated.

---

## 5. A real session (compressed)

Laptop: `192.168.0.163/24` on `en0`. SSH config pointed at `192.168.1.41` (another prefix, from another building). That IP was a black hole — correct: it was a **previous lease on a previous LAN**.

mDNS names (`SPAGUETI.local`, `raspberrypi.local`) did not resolve at first. A ping-sweep and `nmap -sn` saw only the laptop. Conclusion “the Pi is not on this network” was **wrong**. Conclusion “nothing on this network answers IPv4 unicast discovery” was **right**.

Then `_workstation._tcp` published:

```
SPAGUETI [2c:cf:67:f0:c7:d4]
```

`dscacheutil` returned `192.168.0.59` and `fe80::2ecf:67ff:fef0:c7d4`. IPv4 ping: `No route to host`, ARP incomplete. IPv6 LL ping: 7–44 ms RTT. After that, ARP filled (`2c:cf:67:f0:c7:d4`) and `nmap -Pn -p 22` showed `open`.

SSH:

```
Permission denied (publickey,password).
```

That is success at every layer except auth. The host key was accepted into `known_hosts`. The *user* key in `IdentityFile` is not in that account’s `authorized_keys` (or the user is not `greko`).

Three distinct bugs, one afternoon:

1. **Stale unicast cache** (`HostName` on the old prefix).
2. **Asymmetric visibility** (mDNS yes, IPv4 neighbor no, IPv6 LL yes).
3. **Credential mismatch** after the path existed.

If you only remember one thing: stop when the error changes layer. Do not keep tweaking SSH options while ARP is incomplete.

---

## 6. Reaching: SSH as a precision tool

### 6.1 One candidate, one identity, no prompts

```bash
ssh -o ConnectTimeout=8 \
    -o BatchMode=yes \
    -o IdentitiesOnly=yes \
    -o StrictHostKeyChecking=accept-new \
    -i ~/.ssh/id_ed25519_raspi \
    greko@192.168.0.59 \
    'hostname; hostname -I; uptime'
```

| Option | Why |
| --- | --- |
| `BatchMode` | fail instead of hanging on a password prompt |
| `IdentitiesOnly` + `-i` | offer **one** key. Otherwise the agent sprays every key; `sshd` may `MaxAuthTries` you out; you also leak how many keys you own |
| `accept-new` | TOFU for a new lease without disabling host-key checks on *known* names |
| remote argv | a one-shot command proves the session, not just the banner |

`Connection refused` → `sshd` is down (`sudo systemctl status ssh`).  
`Permission denied (publickey)` → fix keys on the Pi, do not scan more IPs.  
`WARNING: REMOTE HOST IDENTIFICATION HAS CHANGED` → you are not talking to the same disk image. That is a security event, not an inconvenience.

### 6.2 Install a key from the console (once)

On the Pi, as the user you want:

```bash
mkdir -p ~/.ssh && chmod 700 ~/.ssh
# paste the public half of id_ed25519_raspi
echo 'ssh-ed25519 AAAA... comment' >> ~/.ssh/authorized_keys
chmod 600 ~/.ssh/authorized_keys
```

The private key never leaves the laptop. If you typed a password over SSH “just this once,” rotate it.

On the laptop, after a new lease:

```bash
ssh-keygen -R 192.168.0.59   # only if you must drop a stale line
```

Better: pin the host key you already trust:

```
Host raspi
    HostName spagueti.local
    HostKeyAlias spagueti
    User greko
    IdentityFile ~/.ssh/id_ed25519_raspi
    IdentitiesOnly yes
```

`HostKeyAlias` makes `known_hosts` follow the *machine*, not the lease.

### 6.3 What you should run first, once you are in

```bash
hostname; hostname -I
ip -br addr
nmcli -t -f NAME,TYPE,DEVICE,STATE connection show --active
ping -c 1 -W 2 1.1.1.1 && echo internet:ok
```

That answers: who I am, which addresses I own, which NM connection is live, whether upstream works. Everything else is optional.

---

## 7. Procedure (do this in order)

You are on the same radio network you believe the Pi joined. You have a console on the Pi *or* you previously installed an SSH key.

1. **Refuse the stale IP.** If `ssh raspi` dies toward an address not in your current prefix, ignore `~/.ssh/config` for this session.
2. **Ask the Pi to announce.** `dns-sd -B _workstation._tcp local.` (or `avahi-browse`). Note hostname, MAC, interface index.
3. **Resolve.** `dscacheutil -q host -a name <hostname>.local`. Record IPv4 and IPv6 LL.
4. **Prove L2.** `ping6 '<ll>%en0'`. If that fails, you are not on the same link — different VLAN, isolation that also drops IPv6, or stale mDNS. Stop. Check the AP.
5. **Prove IPv4 only if you need it.** `ping <lease>` / `arp -n <lease>`. Incomplete ARP after a working LL ping is isolation or an IPv4 filter. You can SSH over IPv6 anyway.
6. **Prove sshd.** `nc -z -G 2 <addr> 22` or `nmap -Pn -p 22 <addr>`.
7. **Authenticate once.** One user, one key, `BatchMode`, `IdentitiesOnly`.
8. **Write down the new cache.** Update `HostName` to `<hostname>.local`, not to today’s lease. Optionally add `HostKeyAlias`.

If step 2 is empty after a minute: Avahi is down, multicast is filtered, or the Pi is not associated. Then use the DHCP UI or a cable.

Ethernet Mac ↔ Pi (or Pi ↔ LAN switch) bypasses every wireless isolation story. Link-local IPv6 still applies; IPv4 will be whatever `networkd` / NM configured (`169.254.0.0/16` if nobody ran DHCP — RFC 3927).

---

## 8. Things that look like bugs and are not

**The laptop reports “not associated” and still has `192.168.0.163` on `en0`.** The association UI and the IPv4 stack are different daemons. Believe `ifconfig` / `ip addr` and a default route, not the menu extra.

**`nmap -sn` sees one host: you.** On an isolated BSS that is the expected result. Use mDNS or the DHCP table.

**`SPAGUETI.local` ≠ `spagueti.local` in your head, equal on the wire.** mDNS names are case-insensitive. The hostname on the Pi can still be `SPAGUETI`.

**Ping fails, SSH works** (or the reverse). ICMP and TCP 22 are independent. Never use ping as a proxy for “SSH is down.”

**Two leases, one Pi.** Dual-stack, or NM still holding an old profile, or Ethernet + Wi‑Fi. `ip -br addr` on the Pi is source of truth; mDNS may publish both.

**You can see `_http._tcp` printers and not the Pi.** Those are other devices. DNS-SD is a shared bus. Filter by instance name / MAC OUI.

---

## 9. What this setup is *for*

A portable Pi will change prefix every time you change building. The design in this repo (fallback AP, no inbound from the internet, later a mesh overlay) exists because **there is no stable IPv4**.

The durable reachability story is:

- **Same LAN, this document** — mDNS + SSH + a key that travels with you.
- **No LAN, first_boot Wi‑Fi fallback** — you become the AP’s client at `10.42.0.1`.
- **Anywhere, later** — an overlay (Tailscale, WireGuard, …) so you stop caring about the venue prefix.

Until the overlay exists, treat every IPv4 as disposable and every host key as sacred.
