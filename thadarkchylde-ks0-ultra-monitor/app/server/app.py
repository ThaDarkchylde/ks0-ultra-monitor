from flask import Flask, jsonify, render_template, request

from miner import get_miner_data, get_nerdqaxe_data, get_bitmain_data
from miners_store import load_miners, add_miner
from scanner import scan_network

app = Flask(
    __name__,
    template_folder="../web"
)


@app.route("/")
def index():
    return render_template("index.html")


def _build_iceriver_result(miner):
    data = get_miner_data(miner["ip"])

    overview = data.get("overview", {})
    overview_data = overview.get("data", {})

    clock = data.get("clock", {})
    voltage = data.get("voltage", {})

    boards = overview_data.get("boards", [])

    temperature = None
    fan = None

    if boards:
        temperature = boards[0].get("chiptmp")
        fans = overview_data.get("fans", [])
        if fans:
            fan = max(fans)

    return {
        "name": miner["name"],
        "ip": miner["ip"],
        "type": "iceriver",

        "online": overview_data.get("online", False),

        "hashrate": overview_data.get("rtpow"),
        "average_hashrate": overview_data.get("avgpow"),

        "temperature": temperature,
        "fan": fan,

        "clock": clock,
        "voltage": voltage,

        "power": data.get("power_estimate"),
        "power_source": "estimated",

        "firmware": overview_data.get("softver1"),
        "model": overview_data.get("model"),

        "pool": data.get("pool", {}),
        "shares": data.get("kryptex", {})
    }


def _build_nerdqaxe_result(miner):
    data = get_nerdqaxe_data(miner["ip"])
    return {
        "name": miner["name"],
        "ip": miner["ip"],
        "type": "nerdqaxe",
        **data
    }


def _build_bitmain_result(miner):
    data = get_bitmain_data(miner["ip"])
    return {
        "name": miner["name"],
        "ip": miner["ip"],
        "type": "bitmain",
        **data
    }


BUILDERS = {
    "iceriver": _build_iceriver_result,
    "nerdqaxe": _build_nerdqaxe_result,
    "bitmain": _build_bitmain_result,
}


@app.route("/api/miners", methods=["GET"])
def miners():
    result = []
    for miner in load_miners():
        builder = BUILDERS.get(miner.get("type", "iceriver"), _build_iceriver_result)
        result.append(builder(miner))
    return jsonify(result)


@app.route("/api/miners", methods=["POST"])
def add_miner_route():
    payload = request.get_json(force=True, silent=True) or {}
    name = payload.get("name")
    ip = payload.get("ip")
    miner_type = payload.get("type")

    if not name or not ip or not miner_type:
        return jsonify({"error": "name, ip und type sind erforderlich"}), 400

    updated, added = add_miner(name, ip, miner_type)
    if not added:
        return jsonify({"error": "IP bereits vorhanden", "miners": updated}), 409

    return jsonify({"miners": updated}), 201


@app.route("/api/scan", methods=["GET"])
def scan():
    return jsonify(scan_network())


@app.route("/health")
def health():
    return jsonify({
        "status": "ok"
    })


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=3000,
        debug=False
    )
