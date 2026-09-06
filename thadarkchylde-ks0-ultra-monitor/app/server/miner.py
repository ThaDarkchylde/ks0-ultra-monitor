import os
import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

KS_USER = os.getenv("KS_USER", "admin")
KS_PASSWORD = os.getenv("KS_PASSWORD", "")
BRIDGE_METRICS_URL = os.getenv("BRIDGE_METRICS_URL", "http://bridge:2114/metrics")


def get_session(ip):
    session = requests.Session()

    try:
        response = session.post(
            f"https://{ip}/user/login",
            data={
                "username": KS_USER,
                "password": KS_PASSWORD
            },
            verify=False,
            timeout=5
        )

        if response.json().get("error") == 0:
            return session

    except Exception:
        pass

    return None


def get_json(session, ip, endpoint):
    try:
        response = session.get(
            f"https://{ip}{endpoint}",
            verify=False,
            timeout=5
        )

        response.raise_for_status()
        return response.json()

    except Exception as e:
        return {
            "error": 1,
            "message": str(e)
        }


def get_bridge_metrics():
    try:
        response = requests.get(
            BRIDGE_METRICS_URL,
            timeout=5
        )

        response.raise_for_status()

        metrics = {}
        blocks = {}

        for line in response.text.splitlines():

            line = line.strip()

            if not line or line.startswith("#") or "{" not in line:
                continue

            metric_name, rest = line.split("{", 1)
            labels_text, value_text = rest.rsplit("}", 1)

            labels = {}

            for part in labels_text.split(","):

                if "=" not in part:
                    continue

                key, value = part.split("=", 1)

                labels[key.strip()] = value.strip().strip('"')

            try:
                value = float(value_text.strip())
            except ValueError:
                continue

            worker = labels.get("worker")

            if not worker:
                continue

            entry = metrics.setdefault(worker, {})

            if metric_name == "ks_valid_share_counter":
                entry["accepted"] = int(value)

            elif metric_name == "ks_invalid_share_counter":

                share_type = labels.get("type", "invalid")

                entry[share_type] = int(value)

            elif metric_name == "ks_mined_blocks_gauge":

                blocks[worker] = blocks.get(worker, 0) + 1

        result = {}

        for worker, data in metrics.items():

            accepted = data.get("accepted", 0)

            invalid = data.get("invalid", 0)
            stale = data.get("stale", 0)
            duplicate = data.get("duplicate", 0)
            weak = data.get("weak", 0)

            rejected = (
                invalid +
                stale +
                duplicate +
                weak
            )

            result[worker] = {
                "accepted": accepted,
                "rejected": rejected,
                "invalid": invalid,
                "stale": stale,
                "duplicate": duplicate,
                "weak": weak,
                "shares": accepted + rejected,
                "blocks": blocks.get(worker, 0)
            }

        return result

    except Exception:
        return {}


def estimate_power(clock, voltage):

    if not clock or not voltage:
        return None

    freq = (
        clock.get("base", 0) +
        clock.get("offset", 0)
    )

    volt = (
        voltage.get("base", 0) +
        voltage.get("offset", 0)
    )

    if freq <= 0 or volt <= 0:
        return None

    power = 100 * (
        (volt / 1312) ** 2
    ) * (
        freq / 355
    )

    return round(power, 1)


def get_miner_data(ip):

    session = get_session(ip)

    if not session:

        return {
            "online": False,
            "error": "Authentication failed",
            "bridge": {}
        }

    overview = get_json(
        session,
        ip,
        "/overview"
    )

    clock = get_json(
        session,
        ip,
        "/clock"
    )

    voltage = get_json(
        session,
        ip,
        "/voltage"
    )

    clock_data = clock.get(
        "clock",
        {}
    )

    voltage_data = voltage.get(
        "voltage",
        {}
    )

    overview_data = overview.get(
        "data",
        {}
    )

    pools = overview_data.get(
        "pools",
        []
    )

    pool = pools[0] if pools else {}

    bridge_metrics = get_bridge_metrics()

    worker = overview_data.get(
        "host"
    )

    return {

        "overview": overview,

        "clock": clock_data,

        "voltage": voltage_data,

        "power_estimate": estimate_power(
            clock_data,
            voltage_data
        ),

        "pool": {

            "address": pool.get(
                "addr"
            ),

            "connected": pool.get(
                "connect",
                False
            ),

            "priority": pool.get(
                "priority"
            ),

            "difficulty": pool.get(
                "diff"
            )
        },

        "bridge": bridge_metrics.get(
            worker,
            {}
        )
    }
