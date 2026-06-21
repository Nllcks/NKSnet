import json
import os
import time
from pathlib import Path

import requests


DATA_DIR = Path(os.path.expanduser("~")) / ".speedtest_app"
DATA_DIR.mkdir(exist_ok=True)
HISTORY_FILE = DATA_DIR / "history.json"
SETTINGS_FILE = DATA_DIR / "settings.json"
LAST_RESULT_FILE = DATA_DIR / "last_result.json"


def detect_isp():
    """Detect ISP, location, and public IP via ip-api.com."""
    try:
        resp = requests.get("http://ip-api.com/json/?fields=query,isp,org,country,city,region", timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            return {
                "ip": data.get("query", "N/A"),
                "isp": data.get("isp", "N/A"),
                "org": data.get("org", "N/A"),
                "city": data.get("city", "N/A"),
                "region": data.get("region", "N/A"),
                "country": data.get("country", "N/A"),
            }
    except Exception:
        pass
    return {"ip": "N/A", "isp": "Nao disponivel", "org": "", "city": "", "region": "", "country": ""}


def load_history():
    if HISTORY_FILE.exists():
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return []


def save_result(ping, jitter, download, upload, server):
    history = load_history()
    entry = {
        "timestamp": time.time(),
        "ping": round(ping, 1),
        "jitter": round(jitter, 2),
        "download": round(download, 2),
        "upload": round(upload, 2),
        "server": server.get("name", ""),
        "isp": server.get("sponsor", ""),
    }
    history.append(entry)
    if len(history) > 50:
        history = history[-50:]
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)
    with open(LAST_RESULT_FILE, "w", encoding="utf-8") as f:
        json.dump(entry, f, ensure_ascii=False, indent=2)


def load_last_result():
    if LAST_RESULT_FILE.exists():
        try:
            with open(LAST_RESULT_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return None


def load_settings():
    if SETTINGS_FILE.exists():
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"auto_start": False}


def save_settings(settings):
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(settings, f, ensure_ascii=False, indent=2)
