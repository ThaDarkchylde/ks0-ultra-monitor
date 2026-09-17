import ipaddress
import json
import os
import socket
import concurrent.futures

import requests
import urllib3

from miners_store import known_ips

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

SCAN_TIMEOUT = 0.3
MAX_HOSTS = 254


def _local_subnet():
    override = os.getenv("SCAN_SUBNET")
    if override:
        return ipaddress.ip_network(override, strict=False)

    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
    except Exception:
        local_ip = "192.168.0.1"
    finally:
        s.close()

    return ipaddress.ip_network(f"{local_ip}/24", strict=False)


def _port_open(ip, port, timeout=SCAN_TIMEOUT):
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(timeout)
            return s.connect_ex((ip, port)) == 0
    except Exception:
        return False


def _probe_bitmain(ip):
    try:
        with socket.create_connection((ip, 4028), timeout=1.5) as sock:
            sock.sendall(json.dumps({"command": "summary"}).encode())
            data = sock.recv(4096)
        text = data.decode(errors="ignore").strip("\x00").strip()
        parsed = json.loads(text)
        return "STATUS" in parsed
    except Exception:
        return False


def _probe_nerdqaxe(ip):
    try:
        response = requests.get(f"http://{ip}/api/system/info", timeout=1.5)
        if response.status_code != 200:
            return False
        data = response.json()
        return "ASICModel" in data or "hashRate" in data
    except Exception:
        return False


def _probe_iceriver(ip):
    try:
        response = requests.post(
            f"https://{ip}/user/login",
            data={"username": "probe", "password": "probe"},
            verify=False,
            timeout=1.5,
        )
        data = response.json()
        return "error" in data
    except Exception:
        return False


def _check_host(ip):
    ip_str = str(ip)

    if _port_open(ip_str, 4028) and _probe_bitmain(ip_str):
        return {"ip": ip_str, "type": "bitmain", "label": "Bitmain / CGMiner-kompatibel"}

    if _port_open(ip_str, 443) and _probe_iceriver(ip_str):
        return {"ip": ip_str, "type": "iceriver", "label": "IceRiver"}

    if _port_open(ip_str, 80):
        if _probe_nerdqaxe(ip_str):
            return {"ip": ip_str, "type": "nerdqaxe", "label": "NerdQAxe / AxeOS"}
        if _probe_iceriver(ip_str):
            return {"ip": ip_str, "type": "iceriver", "label": "IceRiver"}

    return None


def scan_network():
    network = _local_subnet()
    existing = known_ips()
    hosts = list(network.hosts())[:MAX_HOSTS]

    found = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=60) as executor:
        for result in executor.map(_check_host, hosts):
            if result and result["ip"] not in existing:
                found.append(result)

    return found
