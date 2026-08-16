import os
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

        data = response.json()

        if data.get("error") == 0:
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


def estimate_power(clock, voltage):
    if not clock or not voltage:
        return None

    freq = clock.get("base", 0) + clock.get("offset", 0)
    volt = voltage.get("base", 0) + voltage.get("offset", 0)

    if freq <= 0 or volt <= 0:
        return None

    # Approximation:
    # 355 MHz @ 1312 mV ≈ 100 W
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
            "error": "Authentication failed"
        }

    overview = get_json(session, ip, "/overview")
    clock = get_json(session, ip, "/clock")
    voltage = get_json(session, ip, "/voltage")

    clock_data = clock.get("clock", {})
    voltage_data = voltage.get("voltage", {})
    overview_data = overview.get("data", {})

    return {
        "overview": overview,
        "clock": clock_data,
        "voltage": voltage_data,
        "power_estimate": estimate_power(
            clock_data,
            voltage_data
        )
    }
