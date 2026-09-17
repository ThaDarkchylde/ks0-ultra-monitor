with open("index.html", "r") as f:
    content = f.read()

# 1. CSS fuer Scan-Panel vor dem ZWEITEN </style> einfuegen (modern-miner-ui Block)
scan_css = """
.scan-panel {
    max-width: 900px;
    margin: 0 auto 20px;
    padding: 15px;
    border: 1px solid #00ff66;
    border-radius: 4px;
}
#scanButton {
    background: transparent;
    border: 1px solid #00ff66;
    color: #00ff66;
    font-family: "Courier New", monospace;
    padding: 8px 16px;
    cursor: pointer;
    text-shadow: 0 0 6px #00ff66;
    font-size: 13px;
}
#scanButton:hover {
    background: rgba(0,255,102,0.1);
}
#scanButton:disabled {
    opacity: .5;
    cursor: default;
}
.scan-item {
    display: flex;
    gap: 10px;
    align-items: center;
    padding: 6px 0;
    border-bottom: 1px dashed rgba(0,255,102,0.2);
    flex-wrap: wrap;
    margin-top: 10px;
}
.scan-ip {
    font-weight: bold;
}
.scan-type {
    opacity: .7;
}
.scan-item input {
    background: #001a0d;
    border: 1px solid #00ff66;
    color: #00ff66;
    font-family: "Courier New", monospace;
    padding: 4px 6px;
}
.scan-item button {
    background: transparent;
    border: 1px solid #00ff66;
    color: #00ff66;
    cursor: pointer;
    font-family: "Courier New", monospace;
    padding: 4px 10px;
}
.scan-empty {
    opacity: .6;
    padding: 6px 0;
    margin-top: 10px;
}
"""

last_style_pos = content.rfind("</style>")
if last_style_pos == -1:
    raise SystemExit("Kein </style> gefunden!")

content = content[:last_style_pos] + scan_css + content[last_style_pos:]

# 2. Scan-Panel-HTML direkt vor "TOTAL POWER CONSUMPTION"-Block einfuegen
scan_html = """
<div class="scan-panel">
    <button id="scanButton" onclick="scanNetwork()">SCAN NETWORK // NEUE MINER SUCHEN</button>
    <div id="scanResults"></div>
</div>

"""

marker = '<div class="total">'
if marker not in content:
    raise SystemExit("Marker fuer total-Block nicht gefunden!")

content = content.replace(marker, scan_html + marker, 1)

# 3. renderBitmain-Funktion + renderMiner-Dispatch erweitern
old_dispatch = '''function renderMiner(miner) {

    if (miner.type === "nerdqaxe") {
        return renderNerdQaxe(miner);
    }

    return renderKs0(miner);
}'''

if old_dispatch not in content:
    raise SystemExit("renderMiner-Block nicht gefunden!")

render_bitmain = '''function renderBitmain(miner) {

    const online = !!miner.online;

    return `
    <div class="miner-card ${online ? "" : "offline-card"}">

        <div class="miner-header">
            <div>
                <div class="miner-name">${text(miner.name)}</div>
                <div class="miner-model">${text(miner.model, "BITMAIN / CGMINER")}</div>
            </div>

            <div class="miner-status ${online ? "online" : "offline"}">
                ${online ? "\\u25cf ONLINE" : "\\u25cf OFFLINE"}
            </div>
        </div>

        <div class="hero">
            <div class="hero-label">HASHRATE</div>
            <div class="hero-value">${number(miner.hashrate, 1)} GH/s</div>
        </div>

        <div class="stats">

            <div class="stat important">
                <div class="stat-label">AVERAGE</div>
                <div class="stat-value">${number(miner.average_hashrate, 1)} GH/s</div>
            </div>

            <div class="stat">
                <div class="stat-label">TEMPERATURE</div>
                <div class="stat-value">${formatTemp(miner.temperature)}</div>
            </div>

            <div class="stat">
                <div class="stat-label">FAN</div>
                <div class="stat-value">${number(miner.fan)} RPM</div>
            </div>

            <div class="stat">
                <div class="stat-label">FREQUENCY</div>
                <div class="stat-value">${number(miner.frequency)} MHz</div>
            </div>

            <div class="stat">
                <div class="stat-label">UPTIME</div>
                <div class="stat-value">${text(miner.uptime)} s</div>
            </div>

        </div>

        <div class="share-section">

            <div class="section-title">SHARES</div>

            <div class="share-grid">

                <div class="share">
                    <div class="share-label">ACCEPTED</div>
                    <div class="share-value">${formatDiff(miner.accepted)}</div>
                </div>

                <div class="share">
                    <div class="share-label">REJECTED</div>
                    <div class="share-value">${formatDiff(miner.rejected)}</div>
                </div>

                <div class="share">
                    <div class="share-label">HW ERRORS</div>
                    <div class="share-value">${formatDiff(miner.hardware_errors)}</div>
                </div>

            </div>

        </div>

        <div class="footer-info">

            <div class="info">
                <span>POOL</span>
                <strong>${text(miner.pool)}</strong>
            </div>

            <div class="info">
                <span>STATUS</span>
                <strong>${text(miner.pool_status)}</strong>
            </div>

            <div class="info">
                <span>FIRMWARE</span>
                <strong>${text(miner.firmware)}</strong>
            </div>

            <div class="info">
                <span>IP</span>
                <strong>${text(miner.ip)}</strong>
            </div>

        </div>

    </div>`;
}

function renderMiner(miner) {

    if (miner.type === "nerdqaxe") {
        return renderNerdQaxe(miner);
    }

    if (miner.type === "bitmain") {
        return renderBitmain(miner);
    }

    return renderKs0(miner);
}'''

content = content.replace(old_dispatch, render_bitmain)

# 4. Stale-Cache-Fix (iOS) auch fuer Bitmain aktivieren
old_cache_check = 'if (miner.type === "nerdqaxe") {\n\n                const key = miner.ip || miner.name;'
new_cache_check = 'if (miner.type === "nerdqaxe" || miner.type === "bitmain") {\n\n                const key = miner.ip || miner.name;'

if old_cache_check not in content:
    raise SystemExit("Cache-Check-Block nicht gefunden!")

content = content.replace(old_cache_check, new_cache_check)

# 5. Scan-JS-Funktionen vor "update();\nsetInterval(update, 5000);" einfuegen
scan_js = """
async function scanNetwork() {
    const btn = document.getElementById("scanButton");
    const resultsEl = document.getElementById("scanResults");
    btn.disabled = true;
    btn.textContent = "SCANNE...";
    resultsEl.innerHTML = "";

    try {
        const response = await fetch("/api/scan");
        const found = await response.json();

        if (found.length === 0) {
            resultsEl.innerHTML = '<div class="scan-empty">Keine neuen Geraete gefunden.</div>';
        } else {
            resultsEl.innerHTML = found.map((device, i) => `
                <div class="scan-item">
                    <span class="scan-ip">${device.ip}</span>
                    <span class="scan-type">${device.label}</span>
                    <input type="text" id="scan-name-${i}" placeholder="Name" value="Miner-${device.ip.split('.').pop()}">
                    <button onclick='addMiner("${device.ip}", "${device.type}", ${i})'>+ HINZUFUEGEN</button>
                </div>
            `).join("");
        }
    } catch (error) {
        resultsEl.innerHTML = '<div class="scan-empty error">Scan fehlgeschlagen.</div>';
    }

    btn.disabled = false;
    btn.textContent = "SCAN NETWORK // NEUE MINER SUCHEN";
}

async function addMiner(ip, type, index) {
    const nameInput = document.getElementById(`scan-name-${index}`);
    const name = nameInput.value.trim() || `Miner-${ip.split('.').pop()}`;

    try {
        const response = await fetch("/api/miners", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ name: name, ip: ip, type: type })
        });

        if (response.ok) {
            nameInput.closest(".scan-item").remove();
            update();
        } else {
            alert("Konnte Miner nicht hinzufuegen.");
        }
    } catch (error) {
        alert("Fehler beim Hinzufuegen.");
    }
}

"""

anchor = "update();\nsetInterval(update, 5000);"
if anchor not in content:
    raise SystemExit("update()/setInterval-Anker nicht gefunden!")

content = content.replace(anchor, scan_js + anchor, 1)

with open("index.html", "w") as f:
    f.write(content)

print("Frontend-Patch erfolgreich angewendet.")
