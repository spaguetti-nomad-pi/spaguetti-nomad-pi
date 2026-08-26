#!/usr/bin/env python3
"""Owner-only Telegram bot. Long-polls Telegram; no public URL needed."""

from __future__ import annotations

import json
import logging
import os
import signal
import socket
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

log = logging.getLogger("telegram")
API = "https://api.telegram.org/bot{token}/{method}"
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


def status_text() -> str:
    host = socket.gethostname().split(".")[0]
    try:
        secs = float(Path("/proc/uptime").read_text().split()[0])
        mins = int(secs // 60)
        return f"{host}\nup {mins} min"
    except OSError:
        return host


def handle(token: str, owner: str, msg: dict) -> None:
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
    if text.startswith("/status"):
        send(token, chat_id, status_text())
    elif text.startswith("/start") or text.startswith("/help"):
        send(token, chat_id, "Commands: /status")
    elif text:
        send(token, chat_id, "Commands: /status")


def loop(token: str, owner: str) -> None:
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
                handle(token, owner, msg)


def main() -> None:
    global STOP
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S")
    load_env_file(Path("/etc/telegram/telegram.env"))
    load_env_file(Path(__file__).resolve().parent.parent / "telegram.env")
    token = env("TELEGRAM_BOT_TOKEN")
    if not token:
        log.error("TELEGRAM_BOT_TOKEN is empty")
        sys.exit(1)

    def stop(_signum: int, _frame: object) -> None:
        global STOP
        STOP = True

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    log.info("polling as %s", socket.gethostname().split(".")[0])
    loop(token, env("TELEGRAM_CHAT_ID"))


if __name__ == "__main__":
    main()
