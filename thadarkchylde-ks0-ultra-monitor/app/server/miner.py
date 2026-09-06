import os
import json
import time
from pathlib import Path
import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

KS_USER = os.getenv("KS_USER", "admin")
KS_PASSWORD = os.getenv("KS_PASSWORD", "")

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



# ============================================================
# KRYPTEX POOL
# ============================================================

KRYPTEX_BASE = "https://pool.kryptex.com"
KRYPTEX_COIN = "kas"
KRYPTEX_WALLET = (
    "kaspa:qz87l97qrt09867uz7qlcws2w6zsgktwj8244nptgrhrxp0gtdjrkflr60k24"
)

# Persistent state.
#
# Kryptex only returns a limited number of recent blocks.
# We therefore keep the known block hashes locally so that
# BLOCKS FOUND does not fall back to the API result count.
#
# The state is stored inside /app/data in the container.
STATE_FILE = Path(
    os.getenv(
        "KS_MONITOR_STATE",
        "/app/data/kryptex_state.json"
    )
)


def load_state():
    try:
        if STATE_FILE.exists():
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                state = json.load(f)

            if isinstance(state, dict):
                state.setdefault("known_blocks", {})
                state.setdefault("workers", {})
                return state

    except Exception:
        pass

    return {
        "known_blocks": {},
        "workers": {}
    }


def save_state(state):
    try:
        STATE_FILE.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        tmp = STATE_FILE.with_suffix(".tmp")

        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(
                state,
                f,
                indent=2,
                ensure_ascii=False
            )

        tmp.replace(STATE_FILE)

    except Exception:
        pass


KRYPTEX_STATE = load_state()


def get_kryptex_json(endpoint):
    try:
        response = requests.get(
            KRYPTEX_BASE + endpoint,
            timeout=10
        )

        response.raise_for_status()
        return response.json()

    except Exception:
        return {}


def get_kryptex_workers():
    endpoint = (
        f"/{KRYPTEX_COIN}/api/v3/miner/workers/"
        f"{KRYPTEX_WALLET}"
    )

    data = get_kryptex_json(endpoint)

    workers = {}

    for item in data.get("results", []):
        worker = item.get("worker")

        if not worker:
            continue

        hashrate_30m = float(
            item.get("avg_hashrate_30m", 0) or 0
        )

        workers[worker] = {
            "worker": worker,
            "status": item.get("status", "offline"),
            "scheme": item.get("scheme", ""),
            "valid": int(item.get("valid", 0) or 0),
            "stale": int(item.get("stale", 0) or 0),
            "invalid": int(item.get("invalid", 0) or 0),

            "hashrate_30m": hashrate_30m,

            "hashrate_3h": float(
                item.get("avg_hashrate_3h", 0) or 0
            ),

            "hashrate_24h": float(
                item.get("avg_hashrate_24h", 0) or 0
            ),

            "estimated_difficulty": (
                (hashrate_30m * 60) / 4294967296
                if hashrate_30m > 0
                else None
            ),

            "agent": item.get("agent"),
            "country": item.get("country"),

            "last_share": item.get("last_share"),
            "last_active": item.get("last_active")
        }

    return workers


def get_kryptex_network():
    data = get_kryptex_json(
        f"/api/v1/net/stats/{KRYPTEX_COIN}"
    )

    if not isinstance(data, dict):
        return {}

    results = data.get("day", [])

    if not isinstance(results, list) or not results:
        return {}

    latest = results[-1]

    if not isinstance(latest, dict):
        return {}

    return {
        "difficulty": latest.get("net_difficulty"),
        "hashrate": latest.get("net_hashrate"),
        "timestamp": latest.get("timestamp")
    }


def get_kryptex_blocks():
    data = get_kryptex_json(
        f"/{KRYPTEX_COIN}/api/v1/miner/blocks/{KRYPTEX_WALLET}"
    )

    if isinstance(data, dict):
        return data.get(
            "results",
            data.get("blocks", [])
        )

    if isinstance(data, list):
        return data

    return []


def update_block_state(blocks):
    """
    Add newly discovered blocks to the persistent block database.

    Kryptex currently exposes only the latest 15 blocks.
    Block hashes are therefore used as permanent identifiers.
    """

    known = KRYPTEX_STATE.setdefault(
        "known_blocks",
        {}
    )

    new_blocks = 0

    for block in blocks:

        if not isinstance(block, dict):
            continue

        block_hash = str(
            block.get("hash", "")
        ).strip()

        if not block_hash:
            continue

        if block_hash not in known:
            known[block_hash] = {
                "date": block.get("date"),
                "height": block.get("height"),
                "worker": block.get("worker"),
                "effort": block.get("miner_effort"),
                "reward": block.get("reward"),
                "confirmed": block.get("confirmed"),
                "scheme": block.get("scheme"),
                "kind": block.get("kind")
            }

            new_blocks += 1

    # Save immediately whenever the API reports a new block.
    if new_blocks:
        save_state(KRYPTEX_STATE)

    return new_blocks


def get_current_effort(
    worker_name,
    worker,
    network_difficulty,
    pool_difficulty
):
    if not worker_name:
        return None

    try:
        network_difficulty = float(network_difficulty)
        pool_difficulty = float(pool_difficulty)

        if network_difficulty <= 0:
            return None

        current_raw_valid = int(worker.get("valid", 0) or 0)

    except Exception:
        return None

    workers_state = KRYPTEX_STATE.setdefault("workers", {})
    worker_state = workers_state.get(worker_name)

    if not isinstance(worker_state, dict):
        worker_state = {
            "baseline_shares": 0,
            "accumulated_shares": 0,
            "last_raw_valid": current_raw_valid,
            "last_block_hash": (
                max(
                    KRYPTEX_STATE.get("known_blocks", {}).items(),
                    key=lambda item: int(item[1].get("date", 0) or 0)
                )[0]
                if KRYPTEX_STATE.get("known_blocks")
                else None
            ),
            "updated": int(time.time())
        }
        workers_state[worker_name] = worker_state
        save_state(KRYPTEX_STATE)

    if "accumulated_shares" not in worker_state:
        worker_state["accumulated_shares"] = int(
            worker_state.get("baseline_shares", 0)
        )
        worker_state["last_raw_valid"] = current_raw_valid
        save_state(KRYPTEX_STATE)

    last_raw_valid = worker_state.get("last_raw_valid")

    if last_raw_valid is None:
        delta = 0
    elif current_raw_valid >= last_raw_valid:
        delta = current_raw_valid - last_raw_valid
    else:
        delta = 0

    accumulated_shares = int(
        worker_state.get("accumulated_shares", 0)
    ) + delta

    worker_state["accumulated_shares"] = accumulated_shares
    worker_state["last_raw_valid"] = current_raw_valid
    worker_state["updated"] = int(time.time())
    save_state(KRYPTEX_STATE)

    baseline = int(
        worker_state.get("baseline_shares", accumulated_shares)
    )

    shares_since_block = max(0, accumulated_shares - baseline)

    SHARE_DIFFICULTY_HASH_FACTOR = 4294967296  # 2**32

    effort = (
        shares_since_block
        * pool_difficulty
        * SHARE_DIFFICULTY_HASH_FACTOR
        / network_difficulty
        * 100
    )

    return round(effort, 3)


def reset_worker_search_after_new_block(
    worker_name,
    current_shares,
    latest_block_hash
):
    workers_state = KRYPTEX_STATE.setdefault("workers", {})

    existing = workers_state.get(worker_name, {})

    accumulated_shares = int(
        existing.get("accumulated_shares", 0)
    )

    workers_state[worker_name] = {
        "baseline_shares": accumulated_shares,
        "accumulated_shares": accumulated_shares,
        "last_raw_valid": existing.get(
            "last_raw_valid",
            int(current_shares or 0)
        ),
        "last_block_hash": latest_block_hash,
        "updated": int(time.time())
    }

    save_state(KRYPTEX_STATE)


def get_kryptex_data(worker_name):

    workers = get_kryptex_workers()

    worker = workers.get(
        worker_name,
        {}
    )

    network = get_kryptex_network()

    blocks = get_kryptex_blocks()

    # --------------------------------------------------------
    # Persistent block tracking
    # --------------------------------------------------------

    update_block_state(blocks)

    known_blocks = KRYPTEX_STATE.get(
        "known_blocks",
        {}
    )

    worker_known_blocks = {
        block_hash: block
        for block_hash, block in known_blocks.items()
        if isinstance(block, dict)
        and block.get("worker") == worker_name
    }

    block_count = len(
        worker_known_blocks
    )

    # --------------------------------------------------------
    # Network values
    # --------------------------------------------------------

    network_difficulty = (
        network.get("difficulty")
        if isinstance(network, dict)
        else None
    )

    network_hashrate = (
        network.get("hashrate")
        if isinstance(network, dict)
        else None
    )

    # --------------------------------------------------------
    # Pool difficulty
    # --------------------------------------------------------

    pool_difficulty = None

    try:

        # Kryptex worker API may expose the current share
        # difficulty under several possible names.
        raw = worker.get(
            "difficulty",
            worker.get(
                "diff",
                worker.get(
                    "pool_difficulty"
                )
            )
        )

        if raw is not None:
            pool_difficulty = float(raw)

    except Exception:
        pool_difficulty = None

    # --------------------------------------------------------
    # If the worker endpoint does not expose difficulty,
    # use the miner's configured pool difficulty when possible.
    #
    # This is filled by get_miner_data() later if available.
    # --------------------------------------------------------

    if pool_difficulty is None:
        estimated = worker.get("estimated_difficulty")

        if estimated is not None:
            pool_difficulty = float(estimated)

    if pool_difficulty is None:
        pool_difficulty = 0.0

    # --------------------------------------------------------
    # Current block search effort
    # --------------------------------------------------------

    current_effort = None

    if (
        network_difficulty is not None
        and pool_difficulty > 0
    ):
        current_effort = get_current_effort(
            worker_name,
            worker,
            network_difficulty,
            pool_difficulty
        )

    # --------------------------------------------------------
    # Latest known block
    # --------------------------------------------------------

    latest_block_hash = None

    if known_blocks:

        try:
            latest_block_hash = max(
                known_blocks.items(),
                key=lambda item: int(
                    item[1].get(
                        "date",
                        0
                    ) or 0
                )
            )[0]

        except Exception:
            latest_block_hash = None

    # --------------------------------------------------------
    # Detect whether the latest API block is newer than
    # the worker's stored search baseline.
    # --------------------------------------------------------

    if worker_name and blocks:

        try:

            worker_blocks = [
                b for b in blocks
                if isinstance(b, dict)
                and b.get("hash")
                and b.get("worker") == worker_name
            ]

            if worker_blocks:

                latest_api_block = max(
                    worker_blocks,
                    key=lambda b: int(
                        b.get("date", 0) or 0
                    )
                )

                latest_api_hash = str(
                    latest_api_block.get("hash")
                )

                workers_state = KRYPTEX_STATE.setdefault(
                    "workers",
                    {}
                )

                worker_state = workers_state.get(
                    worker_name,
                    {}
                )

                stored_hash = worker_state.get(
                    "last_block_hash"
                )

                if (
                    latest_api_hash
                    and stored_hash
                    and latest_api_hash != stored_hash
                ):
                    reset_worker_search_after_new_block(
                        worker_name,
                        worker.get("valid", 0),
                        latest_api_hash
                    )

                    current_effort = 0.0

        except Exception:
            pass

    # --------------------------------------------------------
    # Return data
    # --------------------------------------------------------

    return {

        "status": worker.get(
            "status",
            "offline"
        ),

        "scheme": worker.get(
            "scheme",
            "solo"
        ),

        "accepted": worker.get(
            "valid",
            0
        ),

        "rejected": (
            worker.get("stale", 0)
            +
            worker.get("invalid", 0)
        ),

        "invalid": worker.get(
            "invalid",
            0
        ),

        "stale": worker.get(
            "stale",
            0
        ),

        "duplicate": 0,

        "weak": 0,

        "shares": worker.get(
            "valid",
            0
        ),

        "blocks": block_count,

        "effort": current_effort,

        "hashrate_30m": worker.get(
            "hashrate_30m",
            0
        ),

        "hashrate_3h": worker.get(
            "hashrate_3h",
            0
        ),

        "hashrate_24h": worker.get(
            "hashrate_24h",
            0
        ),

        "agent": worker.get(
            "agent"
        ),

        "country": worker.get(
            "country"
        ),

        "last_share": worker.get(
            "last_share"
        ),

        "last_active": worker.get(
            "last_active"
        ),

        "network_difficulty": network_difficulty,

        "network_hashrate": network_hashrate,

        "pool_difficulty": pool_difficulty,

        "pool": "Kryptex",

        "coin": "KAS"
    }


def get_nerdqaxe_data(ip):
    try:
        response = requests.get(
            f"http://{ip}/api/system/info",
            timeout=5
        )

        response.raise_for_status()
        data = response.json()

        return {
            "online": True,
            "model": data.get("deviceModel", "NerdQAxe++"),
            "hostname": data.get("hostname"),

            "hashrate": data.get("hashRate"),
            "hashrate_1m": data.get("hashRate_1m"),
            "hashrate_10m": data.get("hashRate_10m"),
            "hashrate_1h": data.get("hashRate_1h"),
            "hashrate_1d": data.get("hashRate_1d"),

            "temperature": data.get("temp"),
            "vr_temperature": data.get("vrTemp"),

            "power": data.get("power"),
            "voltage": data.get("voltage"),
            "current": data.get("current"),

            "fan": data.get("fanspeed"),
            "fan_manual": data.get("manualFanSpeed"),
            "fan_rpm": data.get("fanrpm"),

            "frequency": data.get("frequency"),
            "core_voltage": data.get("coreVoltage"),
            "core_voltage_actual": data.get("coreVoltageActual"),

            "accepted": data.get("sharesAccepted", 0),
            "rejected": data.get("sharesRejected", 0),

            "best_diff": data.get("bestDiff"),
            "best_session_diff": data.get("bestSessionDiff"),

            "found_blocks": data.get("foundBlocks", 0),
            "total_found_blocks": data.get("totalFoundBlocks", 0),

            "pool_difficulty": data.get("poolDifficulty"),
            "pool": data.get("stratumURL"),
            "pool_port": data.get("stratumPort"),
            "pool_connected": (
                data.get("stratum", {})
                    .get("pools", [{}])[0]
                    .get("connected", False)
            ),

            "wifi_rssi": data.get("wifiRSSI"),
            "ping": data.get("lastpingrtt"),
            "ping_loss": data.get("recentpingloss"),

            "firmware": data.get("version"),
            "asic": data.get("ASICModel"),
            "uptime": data.get("uptimeSeconds"),

            "wifi_status": data.get("wifiStatus"),
            "stratum_user": data.get("stratumUser"),

            "error": None
        }

    except Exception as e:
        return {
            "online": False,
            "error": str(e)
        }


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
            "kryptex": {}
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

    worker = overview_data.get(
        "host"
    )

    kryptex = get_kryptex_data(
        worker
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

        "kryptex": kryptex
    }

