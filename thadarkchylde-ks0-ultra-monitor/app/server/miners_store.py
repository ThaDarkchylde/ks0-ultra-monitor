import json
import os
import threading

from config import MINERS as CONFIG_MINERS

MINERS_FILE = os.getenv("MINERS_FILE", "/app/data/miners.json")

_lock = threading.Lock()

DEFAULT_MINERS = [
    {**m, "type": m.get("type", "iceriver")} for m in CONFIG_MINERS
]


def _ensure_file():
    os.makedirs(os.path.dirname(MINERS_FILE), exist_ok=True)
    if not os.path.exists(MINERS_FILE):
        with open(MINERS_FILE, "w") as f:
            json.dump(DEFAULT_MINERS, f, indent=2)


def load_miners():
    with _lock:
        _ensure_file()
        try:
            with open(MINERS_FILE, "r") as f:
                miners = json.load(f)
            for m in miners:
                m.setdefault("type", "iceriver")
            return miners
        except Exception:
            return list(DEFAULT_MINERS)


def save_miners(miners):
    with _lock:
        os.makedirs(os.path.dirname(MINERS_FILE), exist_ok=True)
        with open(MINERS_FILE, "w") as f:
            json.dump(miners, f, indent=2)


def add_miner(name, ip, miner_type):
    miners = load_miners()
    for m in miners:
        if m["ip"] == ip:
            return miners, False
    miners.append({"name": name, "ip": ip, "type": miner_type})
    save_miners(miners)
    return miners, True


def known_ips():
    return {m["ip"] for m in load_miners()}
