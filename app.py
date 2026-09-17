import sys
import os
import time
import urllib.request
import threading
from pathlib import Path

# Ensure project root is in sys.path
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

import uvicorn
import webview
from backend.config import settings

def is_server_ready(url: str) -> bool:
    try:
        req = urllib.request.Request(f"{url}/api/health", headers={"User-Agent": "VodCoachDesktop/1.0"})
        with urllib.request.urlopen(req, timeout=1.0) as resp:
            return resp.status == 200
    except Exception:
        return False

def run_backend_server():
    uvicorn.run(
        "backend.main:app",
        host=settings.host,
        port=settings.port,
        log_level="warning",
        reload=False
    )

def main():
    target_url = f"http://{settings.host}:{settings.port}"
    print("=" * 60)
    print("         VALORANT AI VOD COACH - DESKTOP APPLICATION")
    print("=" * 60)
    print(f"Connecting to internal backend at: {target_url}")

    # Check if backend is already listening
    if not is_server_ready(target_url):
        print("Starting background FastAPI analysis engine...")
        server_thread = threading.Thread(target=run_backend_server, daemon=True)
        server_thread.start()

        # Wait for server to become responsive
        max_wait_seconds = 15
        start_time = time.time()
        while time.time() - start_time < max_wait_seconds:
            if is_server_ready(target_url):
                print("Analysis engine initialized and ready!")
                break
            time.sleep(0.2)
        else:
            print("[Warning] Server startup wait exceeded, attempting to launch window...")

    # Launch Native PyWebView Window
    print("Launching native desktop window...")
    window = webview.create_window(
        title="VALORANT AI VOD COACH",
        url=target_url,
        width=1440,
        height=900,
        min_size=(1100, 700),
        text_select=True,
        confirm_close=False
    )

    webview.start()
    print("Application closed.")

if __name__ == "__main__":
    main()
