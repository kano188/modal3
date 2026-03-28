import os
import shutil
import subprocess
import threading
import requests
import json
import time
from flask import Flask

app = Flask(__name__)

# ===== 環境變數 =====
FILE_PATH = './tmp'
UUID = os.environ.get('UUID', 'd0c62998-a0d9-4504-b9c4-6ad0d511e8c7')

# Argo
ARGO_DOMAIN = os.environ.get('ARGO_DOMAIN', modal3.future13800.eu.org)
ARGO_AUTH = os.environ.get('ARGO_AUTH', 'eyJhIjoiNjc0MmMxNDI5ZDE4OTA3NjMzZjMyZjQ2MWM5MzUwOWMiLCJ0IjoiMGVhZWQzNjktNDE4MC00ZjMwLTkzZWUtZjQ1OTJjNzU1NTRjIiwicyI6IlpERXpZVFkwT0RFdE5tRmpaQzAwTTJNeUxUaGhOakV0WVRNd1pHTTRaVEUzWm1NdyJ9')
ARGO_PORT = int(os.environ.get('ARGO_PORT', 8001))  # Argo端口，固定隧道token请改回8080或在cf后台设置的端口与这里对应

# 哪吒
NEZHA_SERVER = os.environ.get('NEZHA_SERVER', 'nezha.babiq.eu.org')
NEZHA_PORT = os.environ.get('NEZHA_PORT', '443')
NEZHA_KEY = os.environ.get('NEZHA_KEY', 'QgaPOAwrqFaLcy0JQ6')

os.makedirs(FILE_PATH, exist_ok=True)

# ===== 下載 =====
def download(url, path):
    with requests.get(url, stream=True) as r:
        with open(path, 'wb') as f:
            shutil.copyfileobj(r.raw, f)

# ===== Xray 配置（已正確對接 ARGO_PORT + WS）=====
def generate_config():
    config = {
        "log": {"loglevel": "warning"},
        "inbounds": [{
            "port": ARGO_PORT,
            "protocol": "vless",
            "settings": {
                "clients": [{"id": UUID}],
                "decryption": "none"
            },
            "streamSettings": {
                "network": "ws",
                "wsSettings": {
                    "path": "/argo"
                }
            }
        }],
        "outbounds": [{"protocol": "freedom"}]
    }

    with open(f"{FILE_PATH}/config.json", "w") as f:
        json.dump(config, f, indent=2)

# ===== 下載核心 =====
def setup_core():
    print("[INFO] Downloading core...")

    # Xray
    download(
        "https://github.com/XTLS/Xray-core/releases/latest/download/Xray-linux-64.zip",
        f"{FILE_PATH}/xray.zip"
    )
    subprocess.run(["unzip", "-o", "xray.zip"], cwd=FILE_PATH)
    subprocess.run(["chmod", "+x", "xray"], cwd=FILE_PATH)

    # cloudflared
    download(
        "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64",
        f"{FILE_PATH}/cloudflared"
    )
    subprocess.run(["chmod", "+x", "cloudflared"], cwd=FILE_PATH)

    # 哪吒
    if NEZHA_SERVER and NEZHA_PORT and NEZHA_KEY:
        download(
            "https://github.com/naiba/nezha/releases/latest/download/nezha-agent_linux_amd64.zip",
            f"{FILE_PATH}/nezha.zip"
        )
        subprocess.run(["unzip", "-o", "nezha.zip"], cwd=FILE_PATH)
        subprocess.run(["chmod", "+x", "nezha-agent"], cwd=FILE_PATH)

# ===== 啟動 Xray =====
def run_xray():
    print(f"[INFO] Starting Xray on port {ARGO_PORT} ...")
    subprocess.Popen(["./xray", "-config", "config.json"], cwd=FILE_PATH)

# ===== 啟動 Argo =====
def run_argo():
    print(f"[INFO] Starting Argo -> localhost:{ARGO_PORT}")

    if ARGO_AUTH and ARGO_DOMAIN:
        subprocess.Popen([
            "./cloudflared", "tunnel",
            "--token", ARGO_AUTH
        ], cwd=FILE_PATH)
    else:
        subprocess.Popen([
            "./cloudflared", "tunnel",
            "--url", f"http://localhost:{ARGO_PORT}",
            "--no-autoupdate"
        ], cwd=FILE_PATH)

# ===== 啟動 哪吒 =====
def run_nezha():
    if NEZHA_SERVER and NEZHA_PORT and NEZHA_KEY:
        print("[INFO] Starting Nezha...")
        subprocess.Popen([
            "./nezha-agent",
            "-s", f"{NEZHA_SERVER}:{NEZHA_PORT}",
            "-p", NEZHA_KEY
        ], cwd=FILE_PATH)
    else:
        print("[INFO] Nezha not configured")

# ===== 保活 =====
def keep_alive():
    while True:
        print("[KEEPALIVE]", time.strftime('%Y-%m-%d %H:%M:%S'))
        time.sleep(60)

# ===== Web =====
@app.route("/")
def home():
    return f"✅ Running (Port: {ARGO_PORT})"

# ===== 主入口 =====
if __name__ == "__main__":
    print("🚀 Starting full stack...")

    try:
        setup_core()
        generate_config()
        run_xray()
        time.sleep(2)
        run_argo()
        run_nezha()
    except Exception as e:
        print("ERROR:", e)

    # 保活
    t = threading.Thread(target=keep_alive)
    t.daemon = True
    t.start()

    # 阻塞（關鍵）
    app.run(host="0.0.0.0", port=8000)
