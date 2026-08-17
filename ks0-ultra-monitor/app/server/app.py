from flask import Flask, jsonify, render_template
from config import MINERS
from miner import get_miner_data

app = Flask(
    __name__,
    template_folder="../web"
)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/miners")
def miners():
    result = []

    for miner in MINERS:
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

        result.append({
            "name": miner["name"],
            "ip": miner["ip"],

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
            "model": overview_data.get("model")
        })

    return jsonify(result)


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
