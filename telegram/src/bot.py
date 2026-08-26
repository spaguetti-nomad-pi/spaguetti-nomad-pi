#!/usr/bin/env python3
"""Owner-only Telegram bot. Commands are scripts under scripts/<category>/."""

from __future__ import annotations

import json
import logging
import os
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

log = logging.getLogger("telegram")
API = "https://api.telegram.org/bot{token}/{method}"
ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
LIMIT = 3500
TIMEOUT = 10
STOP = False


def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip() or default


def load_env_file(path: Path) -> None:
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def api(token: str, method: str, payload: dict, timeout: int = 60) -> object:
    url = API.format(token=token, method=method)
    data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = json.loads(resp.read().decode())
    if not body.get("ok"):
        raise RuntimeError(body.get("description", body))
    return body["result"]


def send(token: str, chat_id: int, text: str) -> None:
    api(token, "sendMessage", {"chat_id": chat_id, "text": text}, timeout=30)


def one_liner(path: Path) -> str:
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        s = line.strip()
        if s.startswith("#") and not s.startswith("#!"):
            return s.lstrip("# ").strip()
    return ""


def discover(root: Path) -> dict[str, Path]:
    found: dict[str, Path] = {}
    if not root.is_dir():
        return found
    for sh in sorted(root.glob("*/*.sh")):
        name = "/" + sh.stem
        if name in found:
            log.warning("skip duplicate %s (%s)", name, sh)
            continue
        found[name] = sh
    return found


def help_text(cmds: dict[str, Path]) -> str:
    cats: dict[str, list[Path]] = {}
    for path in cmds.values():
        cats.setdefault(path.parent.name, []).append(path)
    lines: list[str] = []
    for cat in sorted(cats):
        lines.append(f"{cat}:")
        for path in sorted(cats[cat], key=lambda p: p.stem):
            hint = one_liner(path)
            entry = f"  /{path.stem}"
            lines.append(f"{entry}  {hint}" if hint else entry)
        lines.append("")
    return "\n".join(lines).strip() or "No commands."


def run_script(path: Path) -> str:
    root = SCRIPTS.resolve()
    try:
        real = path.resolve()
        real.relative_to(root)
    except ValueError:
        return "forbidden"
    if not real.is_file() or real.suffix != ".sh":
        return "forbidden"
    try:
        proc = subprocess.run(
            [str(real)],
            capture_output=True,
            text=True,
            timeout=TIMEOUT,
            check=False,
        )
    except PermissionError:
        return "not executable"
    except subprocess.TimeoutExpired:
        return "timeout"
    out = ((proc.stdout or "") + (proc.stderr or "")).strip() or "(empty)"
    if len(out) > LIMIT:
        out = out[:LIMIT] + "\n…"
    return out


def command_name(text: str) -> str:
    raw = text.split(None, 1)[0]
    return raw.split("@", 1)[0].lower()


def handle(token: str, owner: str, cmds: dict[str, Path], msg: dict) -> None:
    chat = msg.get("chat") or {}
    chat_id = chat.get("id")
    if chat_id is None:
        return
    if not owner:
        log.info("set TELEGRAM_CHAT_ID=%s then restart", chat_id)
        return
    if str(chat_id) != owner:
        log.info("ignored chat_id=%s", chat_id)
        return
    text = (msg.get("text") or "").strip()
    if not text:
        return
    cmd = command_name(text)
    if cmd in {"/start", "/help"}:
        send(token, chat_id, help_text(cmds))
        return
    path = cmds.get(cmd)
    if path is None:
        send(token, chat_id, help_text(cmds))
        return
    send(token, chat_id, run_script(path))


def loop(token: str, owner: str, cmds: dict[str, Path]) -> None:
    offset = 0
    while not STOP:
        try:
            updates = api(token, "getUpdates", {"offset": offset, "timeout": 50}, timeout=60)
        except (urllib.error.URLError, TimeoutError, RuntimeError) as exc:
            log.warning("poll: %s", exc)
            time.sleep(3)
            continue
        if not isinstance(updates, list):
            continue
        for upd in updates:
            if not isinstance(upd, dict):
                continue
            offset = int(upd.get("update_id", offset)) + 1
            msg = upd.get("message") or upd.get("edited_message")
            if isinstance(msg, dict):
                handle(token, owner, cmds, msg)


def main() -> None:
    global STOP
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S")
    load_env_file(Path("/etc/telegram/telegram.env"))
    load_env_file(ROOT / "telegram.env")
    token = env("TELEGRAM_BOT_TOKEN")
    if not token:
        log.error("TELEGRAM_BOT_TOKEN is empty")
        sys.exit(1)
    cmds = discover(SCRIPTS)
    log.info("%d commands from %s", len(cmds), SCRIPTS)

    def stop(_signum: int, _frame: object) -> None:
        global STOP
        STOP = True

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    log.info("polling as %s", socket.gethostname().split(".")[0])
    loop(token, env("TELEGRAM_CHAT_ID"), cmds)


if __name__ == "__main__":
    main()
