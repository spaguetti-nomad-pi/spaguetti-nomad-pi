#!/usr/bin/env python3
"""WiFi fallback: raise a setup AP and captive portal when the Pi is offline."""

from __future__ import annotations

import json
import logging
import os
import signal
import socket
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent.parent
PORTAL_DIR = ROOT / "portal"
CAPTIVE_PATHS = {
    "/generate_204",
    "/gen_204",
    "/hotspot-detect.html",
    "/library/test/success.html",
    "/ncsi.txt",
    "/connecttest.txt",
    "/canonical.html",
    "/success.txt",
    "/redirect",
}

log = logging.getLogger("wifi-fallback")


def env(name: str, default: str) -> str:
    value = os.environ.get(name, default).strip()
    return value or default


def default_ssid() -> str:
    return f"{socket.gethostname().split('.')[0]}-setup"


class Config:
    ssid = env("AP_SSID", default_ssid())
    password = env("AP_PASSWORD", "raspi-setup")
    connection = env("AP_CONNECTION", ssid)
    iface = env("AP_IFACE", "wlan0")
    address = env("AP_ADDRESS", "10.42.0.1")
    prefix = env("AP_PREFIX", "24")
    check_interval = int(env("CHECK_INTERVAL", "15"))
    offline_grace = int(env("OFFLINE_GRACE", "45"))
    boot_grace = int(env("BOOT_GRACE", "120"))
    connect_timeout = int(env("CONNECT_TIMEOUT", "30"))

    @classmethod
    def cidr(cls) -> str:
        return f"{cls.address}/{cls.prefix}"


def run(args: list[str], timeout: int = 30) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def nmcli(*args: str, timeout: int = 30) -> subprocess.CompletedProcess[str]:
    return run(["nmcli", *args], timeout=timeout)


def parse_nmcli_line(line: str, nfields: int) -> list[str]:
    parts: list[str] = []
    buf: list[str] = []
    esc = False
    for ch in line:
        if esc:
            buf.append(ch)
            esc = False
        elif ch == "\\":
            esc = True
        elif ch == ":" and len(parts) < nfields - 1:
            parts.append("".join(buf))
            buf = []
        else:
            buf.append(ch)
    parts.append("".join(buf))
    while len(parts) < nfields:
        parts.append("")
    return parts[:nfields]


def load_env_file(path: Path) -> None:
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


class State:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.mode = "offline"  # offline | ap | connecting | online
        self.error = ""
        self.networks: list[dict[str, Any]] = []
        self.connect_req: dict[str, str] | None = None
        self.rescan_req = False
        self.stop = threading.Event()

    def snapshot(self) -> dict[str, Any]:
        with self.lock:
            return {
                "state": self.mode,
                "error": self.error,
                "ssid": Config.ssid,
                "ip": Config.address,
                "networks": list(self.networks),
            }

    def set_mode(self, mode: str, error: str = "") -> None:
        with self.lock:
            self.mode = mode
            if error or mode != "connecting":
                self.error = error
            log.info("mode=%s%s", mode, f" error={error}" if error else "")

    def take_connect(self) -> dict[str, str] | None:
        with self.lock:
            req = self.connect_req
            self.connect_req = None
            return req

    def take_rescan(self) -> bool:
        with self.lock:
            req = self.rescan_req
            self.rescan_req = False
            return req


STATE = State()


class NM:
    @staticmethod
    def ready() -> bool:
        result = nmcli("general", "status")
        return result.returncode == 0

    @staticmethod
    def wait_ready(seconds: int = 60) -> None:
        deadline = time.time() + seconds
        while time.time() < deadline:
            if NM.ready():
                return
            time.sleep(1)
        raise RuntimeError("NetworkManager did not become ready")

    @staticmethod
    def connection_exists(name: str) -> bool:
        names = [line.strip() for line in nmcli("-g", "NAME", "connection", "show").stdout.splitlines()]
        return name in names

    @staticmethod
    def active_connections() -> list[tuple[str, str, str]]:
        result = nmcli("-t", "-f", "NAME,TYPE,DEVICE", "connection", "show", "--active")
        rows = []
        for line in result.stdout.splitlines():
            if not line.strip():
                continue
            name, ctype, device = parse_nmcli_line(line, 3)
            rows.append((name, ctype, device))
        return rows

    @staticmethod
    def device_state(device: str) -> str:
        result = nmcli("-t", "-f", "DEVICE,TYPE,STATE", "device", "status")
        for line in result.stdout.splitlines():
            name, _ctype, state = parse_nmcli_line(line, 3)
            if name == device:
                return state
        return ""

    @staticmethod
    def ethernet_up() -> bool:
        result = nmcli("-t", "-f", "DEVICE,TYPE,STATE", "device", "status")
        for line in result.stdout.splitlines():
            _name, ctype, state = parse_nmcli_line(line, 3)
            if ctype == "ethernet" and state.startswith("connected"):
                return True
        return False

    @staticmethod
    def ap_active() -> bool:
        for name, _ctype, device in NM.active_connections():
            if name == Config.connection and device == Config.iface:
                return True
        return False

    @staticmethod
    def wifi_client_active() -> bool:
        for name, ctype, device in NM.active_connections():
            if ctype == "802-11-wireless" and device == Config.iface and name != Config.connection:
                return True
        return False

    @staticmethod
    def ping() -> bool:
        result = run(["ping", "-c", "1", "-W", "2", "1.1.1.1"], timeout=5)
        return result.returncode == 0

    @staticmethod
    def has_upstream() -> bool:
        if NM.ethernet_up():
            return True
        if NM.wifi_client_active() and NM.ping():
            return True
        return False

    @staticmethod
    def wifi_client_profiles() -> list[str]:
        result = nmcli("-t", "-f", "NAME,TYPE,AUTOCONNECT", "connection", "show")
        names: list[str] = []
        for line in result.stdout.splitlines():
            name, ctype, auto = parse_nmcli_line(line, 3)
            if ctype == "802-11-wireless" and name != Config.connection and auto == "yes":
                names.append(name)
        return names

    @staticmethod
    def activate_saved_wifi() -> None:
        for name in NM.wifi_client_profiles():
            log.info("trying saved WiFi %s", name)
            nmcli("--wait", "25", "connection", "up", name, timeout=35)
            if NM.has_upstream() or NM.wifi_client_active():
                return

    @staticmethod
    def scan(rescan: bool = True) -> list[dict[str, Any]]:
        args = ["-t", "-f", "SSID,SIGNAL,SECURITY", "device", "wifi", "list"]
        if rescan:
            args.append("--rescan")
            args.append("yes")
        result = nmcli(*args, timeout=25)
        if result.returncode != 0:
            log.warning("wifi scan: %s", result.stderr.strip() or result.stdout.strip())
        seen: set[str] = set()
        networks: list[dict[str, Any]] = []
        for line in result.stdout.splitlines():
            ssid, signal, security = parse_nmcli_line(line, 3)
            ssid = ssid.strip()
            if not ssid or ssid in seen or ssid == Config.ssid:
                continue
            seen.add(ssid)
            try:
                strength = int(signal)
            except ValueError:
                strength = 0
            open_net = not security or security in {"--", ""}
            networks.append(
                {
                    "ssid": ssid,
                    "signal": strength,
                    "security": "open" if open_net else security,
                    "open": open_net,
                }
            )
        networks.sort(key=lambda item: item["signal"], reverse=True)
        return networks

    @staticmethod
    def ensure_ap_connection() -> None:
        if not NM.connection_exists(Config.connection):
            nmcli(
                "connection",
                "add",
                "type",
                "wifi",
                "ifname",
                Config.iface,
                "con-name",
                Config.connection,
                "autoconnect",
                "no",
                "ssid",
                Config.ssid,
            )
        nmcli(
            "connection",
            "modify",
            Config.connection,
            "802-11-wireless.mode",
            "ap",
            "802-11-wireless.band",
            "bg",
            "ipv4.method",
            "shared",
            "ipv4.addresses",
            Config.cidr(),
            "ipv4.never-default",
            "yes",
            "wifi-sec.key-mgmt",
            "wpa-psk",
            "wifi-sec.psk",
            Config.password,
            "802-11-wireless-security.proto",
            "rsn",
            "802-11-wireless-security.pairwise",
            "ccmp",
            "connection.autoconnect",
            "no",
        )

    @staticmethod
    def start_ap() -> None:
        NM.ensure_ap_connection()
        result = nmcli("connection", "up", Config.connection, timeout=40)
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or "failed to start AP")

    @staticmethod
    def stop_ap() -> None:
        if NM.ap_active():
            nmcli("connection", "down", Config.connection)

    @staticmethod
    def wait_ap_ip(seconds: int = 20) -> bool:
        deadline = time.time() + seconds
        while time.time() < deadline:
            result = run(["ip", "-4", "-o", "addr", "show", "dev", Config.iface])
            if Config.address in result.stdout:
                return True
            time.sleep(0.4)
        return False

    @staticmethod
    def wifi_con_name(ssid: str) -> str:
        return f"wifi-{ssid}"[:44]

    @staticmethod
    def save_wifi(ssid: str, password: str) -> str:
        name = NM.wifi_con_name(ssid)
        if NM.connection_exists(name):
            nmcli("connection", "delete", name)
        result = nmcli(
            "connection",
            "add",
            "type",
            "wifi",
            "ifname",
            Config.iface,
            "con-name",
            name,
            "ssid",
            ssid,
            "autoconnect",
            "yes",
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or "failed to add WiFi connection")
        if password:
            result = nmcli(
                "connection",
                "modify",
                name,
                "wifi-sec.key-mgmt",
                "wpa-psk",
                "wifi-sec.psk",
                password,
            )
        else:
            result = nmcli("connection", "modify", name, "wifi-sec.key-mgmt", "none")
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or "failed to set WiFi security")
        return name

    @staticmethod
    def connect_wifi(name: str) -> None:
        result = nmcli("--wait", str(Config.connect_timeout), "connection", "up", name, timeout=Config.connect_timeout + 10)
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or "failed to connect")


class Firewall:
    table = "wifi_fallback"

    @classmethod
    def apply(cls) -> None:
        cls.clear()
        rules = f"""
table ip {cls.table} {{
  chain prerouting {{
    type nat hook prerouting priority dstnat; policy accept;
    iifname "{Config.iface}" tcp dport 80 dnat to {Config.address}:80
  }}
}}
"""
        proc = subprocess.run(
            ["nft", "-f", "-"],
            input=rules,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        if proc.returncode != 0:
            log.warning("nftables: %s", proc.stderr.strip())
        run(["sysctl", "-w", "net.ipv4.ip_forward=1"])

    @classmethod
    def clear(cls) -> None:
        run(["nft", "delete", "table", "ip", cls.table])


MIME = {
    ".html": "text/html; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".ico": "image/x-icon",
}


class PortalHandler(BaseHTTPRequestHandler):
    server_version = "wifi-fallback/1.0"

    def log_message(self, fmt: str, *args: Any) -> None:
        log.debug("http " + fmt, *args)

    def _send(self, code: int, body: bytes, content_type: str, extra: dict[str, str] | None = None) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        if extra:
            for key, value in extra.items():
                self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)

    def _json(self, code: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload).encode("utf-8")
        self._send(code, body, "application/json; charset=utf-8")

    def _redirect_portal(self) -> None:
        location = f"http://{Config.address}/"
        self._send(302, b"", "text/plain", {"Location": location})

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        if path in CAPTIVE_PATHS or path == "/":
            self._static("/index.html")
            return
        if path == "/api/status":
            self._json(200, STATE.snapshot())
            return
        if path == "/api/networks":
            if parse_qs(parsed.query).get("rescan", [""])[0] in {"1", "true"}:
                with STATE.lock:
                    STATE.rescan_req = True
            snap = STATE.snapshot()
            self._json(200, {"networks": snap["networks"]})
            return
        self._static(path)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path != "/api/connect":
            self._json(404, {"error": "not found"})
            return
        length = int(self.headers.get("Content-Length", "0") or 0)
        raw = self.rfile.read(min(length, 8192)).decode("utf-8", errors="replace")
        ctype = self.headers.get("Content-Type", "")
        ssid = ""
        password = ""
        if "application/json" in ctype:
            try:
                data = json.loads(raw or "{}")
            except json.JSONDecodeError:
                self._json(400, {"error": "JSON inválido"})
                return
            ssid = str(data.get("ssid", "")).strip()
            password = str(data.get("password", ""))
        else:
            fields = parse_qs(raw, keep_blank_values=True)
            ssid = (fields.get("ssid") or [""])[0].strip()
            password = (fields.get("password") or [""])[0]
        if not ssid:
            self._json(400, {"error": "Falta el SSID"})
            return
        with STATE.lock:
            if STATE.mode == "connecting":
                self._json(409, {"error": "Ya hay una conexión en curso"})
                return
            STATE.connect_req = {"ssid": ssid, "password": password}
            STATE.mode = "connecting"
            STATE.error = ""
        self._json(202, {"ok": True, "state": "connecting"})

    def _static(self, path: str) -> None:
        rel = path.lstrip("/")
        if ".." in rel or path.startswith("/api/"):
            self._json(404, {"error": "not found"})
            return
        file_path = (PORTAL_DIR / rel).resolve()
        if PORTAL_DIR.resolve() not in file_path.parents and file_path != PORTAL_DIR.resolve():
            self._json(403, {"error": "forbidden"})
            return
        if not file_path.is_file():
            self._redirect_portal()
            return
        body = file_path.read_bytes()
        if file_path.name == "index.html":
            host = socket.gethostname().split(".")[0].encode("utf-8")
            body = body.replace(b"__HOSTNAME__", host)
        content_type = MIME.get(file_path.suffix, "application/octet-stream")
        self._send(200, body, content_type)


class ReuseHTTPServer(ThreadingHTTPServer):
    allow_reuse_address = True


class Portal:
    def __init__(self) -> None:
        self.httpd: ThreadingHTTPServer | None = None
        self.thread: threading.Thread | None = None

    def start(self) -> None:
        self.stop()
        httpd = None
        last_err: OSError | None = None
        for _ in range(15):
            try:
                httpd = ReuseHTTPServer((Config.address, 80), PortalHandler)
                break
            except OSError as exc:
                last_err = exc
                time.sleep(0.4)
        if httpd is None:
            raise RuntimeError(f"could not bind portal on {Config.address}:80 ({last_err})")
        self.httpd = httpd
        self.thread = threading.Thread(target=httpd.serve_forever, daemon=True, name="portal")
        self.thread.start()
        log.info("portal listening on http://%s/", Config.address)

    def stop(self) -> None:
        if self.httpd is None:
            return
        try:
            self.httpd.shutdown()
            self.httpd.server_close()
        except OSError:
            pass
        self.httpd = None
        self.thread = None


def refresh_scan(rescan: bool) -> None:
    try:
        networks = NM.scan(rescan=rescan)
    except (subprocess.TimeoutExpired, OSError) as exc:
        log.warning("scan failed: %s", exc)
        return
    with STATE.lock:
        STATE.networks = networks
    log.info("scan found %d networks", len(networks))


def raise_ap(portal: Portal) -> None:
    log.info("starting AP %s", Config.ssid)
    NM.start_ap()
    if not NM.wait_ap_ip():
        raise RuntimeError(f"{Config.address} did not appear on {Config.iface}")
    Firewall.apply()
    portal.start()
    STATE.set_mode("ap")


def lower_ap(portal: Portal) -> None:
    portal.stop()
    Firewall.clear()
    NM.stop_ap()


def idle(seconds: float) -> None:
    """Sleep, but wake early if the portal queued a connect or rescan."""
    deadline = time.time() + seconds
    while time.time() < deadline and not STATE.stop.is_set():
        with STATE.lock:
            if STATE.connect_req or STATE.rescan_req:
                return
        STATE.stop.wait(0.5)


def try_user_connect(portal: Portal, ssid: str, password: str) -> None:
    STATE.set_mode("connecting")
    log.info("connecting to %s", ssid)
    lowered = False
    try:
        name = NM.save_wifi(ssid, password)
        lower_ap(portal)
        lowered = True
        NM.connect_wifi(name)
        deadline = time.time() + Config.connect_timeout
        while time.time() < deadline:
            if NM.has_upstream():
                STATE.set_mode("online")
                return
            time.sleep(1)
        raise RuntimeError("sin internet tras asociar")
    except Exception as exc:
        log.warning("connect to %s failed: %s", ssid, exc)
        STATE.set_mode("offline", str(exc))
        if lowered or not NM.ap_active():
            try:
                refresh_scan(rescan=True)
                raise_ap(portal)
            except Exception as ap_exc:
                log.error("failed to restore AP: %s", ap_exc)
                STATE.set_mode("offline", str(ap_exc))
        else:
            STATE.set_mode("ap", str(exc))


def loop() -> None:
    run(["rfkill", "unblock", "wifi"])
    NM.wait_ready()
    portal = Portal()
    offline_since: float | None = None
    started = time.time()
    saved = NM.wifi_client_profiles()
    if saved:
        log.info("saved WiFi: %s", ", ".join(saved))
        NM.activate_saved_wifi()
    else:
        try:
            refresh_scan(rescan=True)
        except Exception as exc:
            log.warning("initial scan failed: %s", exc)

    log.info("watching connectivity (grace %ss, boot %ss)", Config.offline_grace, Config.boot_grace)

    while not STATE.stop.is_set():
        req = STATE.take_connect()
        if req:
            try_user_connect(portal, req["ssid"], req["password"])
            offline_since = None
            saved = NM.wifi_client_profiles()
            continue

        if STATE.take_rescan() and STATE.snapshot()["state"] == "ap":
            try:
                refresh_scan(rescan=False)
                if not STATE.snapshot()["networks"]:
                    lower_ap(portal)
                    refresh_scan(rescan=True)
                    raise_ap(portal)
            except Exception as exc:
                log.warning("rescan failed: %s", exc)
                try:
                    raise_ap(portal)
                except Exception:
                    pass

        if NM.has_upstream():
            offline_since = None
            if NM.ap_active() or portal.httpd:
                log.info("upstream is up, tearing down AP")
                lower_ap(portal)
            STATE.set_mode("online")
            idle(Config.check_interval)
            continue

        booting = saved and (time.time() - started) < Config.boot_grace
        if booting and NM.wifi_client_active():
            STATE.set_mode("offline")
            idle(Config.check_interval)
            continue

        if offline_since is None:
            offline_since = time.time()
        grace = Config.boot_grace if booting else Config.offline_grace
        waited = time.time() - offline_since
        if waited < grace:
            STATE.set_mode("offline")
            idle(min(Config.check_interval, grace - waited))
            continue

        if not NM.ap_active():
            try:
                if saved:
                    NM.activate_saved_wifi()
                    if NM.has_upstream() or NM.wifi_client_active():
                        offline_since = None
                        continue
                if not STATE.snapshot()["networks"]:
                    refresh_scan(rescan=True)
                raise_ap(portal)
            except Exception as exc:
                log.error("could not start AP: %s", exc)
                STATE.set_mode("offline", str(exc))
        elif STATE.snapshot()["state"] != "connecting":
            STATE.set_mode("ap")

        idle(Config.check_interval)

    lower_ap(portal)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
    )
    load_env_file(Path("/etc/wifi-fallback/wifi-fallback.env"))
    load_env_file(ROOT / "wifi-fallback.env")
    Config.ssid = env("AP_SSID", default_ssid())
    Config.password = env("AP_PASSWORD", "raspi-setup")
    Config.connection = env("AP_CONNECTION", Config.ssid)
    Config.iface = env("AP_IFACE", Config.iface)
    Config.address = env("AP_ADDRESS", Config.address)
    Config.prefix = env("AP_PREFIX", Config.prefix)
    Config.check_interval = int(env("CHECK_INTERVAL", str(Config.check_interval)))
    Config.offline_grace = int(env("OFFLINE_GRACE", str(Config.offline_grace)))
    Config.boot_grace = int(env("BOOT_GRACE", str(Config.boot_grace)))
    Config.connect_timeout = int(env("CONNECT_TIMEOUT", str(Config.connect_timeout)))

    def handle_stop(_signum: int, _frame: Any) -> None:
        STATE.stop.set()

    signal.signal(signal.SIGTERM, handle_stop)
    signal.signal(signal.SIGINT, handle_stop)
    loop()


if __name__ == "__main__":
    main()
