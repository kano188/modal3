import os
import subprocess
import threading
import requests
import json
import time
from flask import Flask

app = Flask(__name__)

# ===== 環境變數 =====
FILE_PATH = './tmp'
UUID = os.environ.get('UUID', '70cb60c0-ed32-4db1-a147-fb4714c75b17')

ARGO_DOMAIN = os.environ.get('ARGO_DOMAIN', 'modal3.future13800.eu.org')
ARGO_AUTH = os.environ.get('ARGO_AUTH', 'eyJhIjoiNjc0MmMxNDI5ZDE4OTA3NjMzZjMyZjQ2MWM5MzUwOWMiLCJ0IjoiMGVhZWQzNjktNDE4MC00ZjMwLTkzZWUtZjQ1OTJjNzU1NTRjIiwicyI6IlpERXpZVFkwT0RFdE5tRmpaQzAwTTJNeUxUaGhOakV0WVRNd1pHTTRaVEUzWm1NdyJ9')
ARGO_PORT = int(os.environ.get('ARGO_PORT', 8001))  # Argo端口

NEZHA_SERVER = os.environ.get('NEZHA_SERVER', 'nezha.babiq.eu.org')
NEZHA_PORT = os.environ.get('NEZHA_PORT', '443')
NEZHA_KEY = os.environ.get('NEZHA_KEY', 'QgaPOAwrqFaLcy0JQ6')

os.makedirs(FILE_PATH, exist_ok=True)

# ===== 下載（無 unzip 版本）=====
def download_file(url, path):
    r = requests.get(url)
    with open(path, 'wb') as f:
        f.write(r.content)

# ===== Xray 配置 =====
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

# ===== 安裝核心（不解壓版）=====
def setup_core():
    print("[INFO] Installing core...")

    # Xray（直接下載 binary）
    download_file(
        "https://github.com/XTLS/Xray-core/releases/latest/download/Xray-linux-64",
        f"{FILE_PATH}/xray"
    )
    os.chmod(f"{FILE_PATH}/xray", 0o755)

    # Argo
    download_file(
        "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64",
        f"{FILE_PATH}/cloudflared"
    )
    os.chmod(f"{FILE_PATH}/cloudflared", 0o755)

    # 哪吒
    if NEZHA_SERVER and NEZHA_PORT and NEZHA_KEY:
        download_file(
            "https://github.com/naiba/nezha/releases/latest/download/nezha-agent_linux_amd64",
            f"{FILE_PATH}/nezha-agent"
        )
        os.chmod(f"{FILE_PATH}/nezha-agent", 0o755)

# ===== 啟動 =====
def run_xray():
    print("[INFO] Starting Xray...")
    subprocess.Popen([f"{FILE_PATH}/xray", "-config", f"{FILE_PATH}/config.json"])

def run_argo():
    print("[INFO] Starting Argo...")
    if ARGO_AUTH:
        subprocess.Popen([f"{FILE_PATH}/cloudflared", "tunnel", "--token", ARGO_AUTH])
    else:
        subprocess.Popen([
            f"{FILE_PATH}/cloudflared",
            "tunnel",
            "--url", f"http://localhost:{ARGO_PORT}"
        ])

def run_nezha():
    if NEZHA_SERVER and NEZHA_PORT and NEZHA_KEY:
        print("[INFO] Starting Nezha...")
        subprocess.Popen([
            f"{FILE_PATH}/nezha-agent",
            "-s", f"{NEZHA_SERVER}:{NEZHA_PORT}",
            "-p", NEZHA_KEY
        ])

# ===== 保活 =====
def keep_alive():
    while True:
        print("[KEEPALIVE]", time.strftime('%H:%M:%S'))
        time.sleep(60)

# ===== Web（防退出關鍵）=====
@app.route("/")
def home():
    return "OK"

# ===== 主入口 =====
if __name__ == "__main__":
    print("🚀 Starting...")

    try:
        setup_core()
        generate_config()
        run_xray()
        time.sleep(2)
        run_argo()
        run_nezha()
    except Exception as e:
        print("ERROR:", e)

    threading.Thread(target=keep_alive, daemon=True).start()

    # ⚠️ 關鍵：前台阻塞
    app.run(host="0.0.0.0", port=8000)
