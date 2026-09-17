import uvicorn
import sys
import os
import shutil
from pathlib import Path

# Ensure project root is in sys.path
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from backend.config import settings

def main():
    print("=" * 65)
    print("           VALORANT AI VOD COACH - WINDOWS APPLICATION")
    print("=" * 65)
    print(f"Data Directory : {settings.data_dir}")
    print(f"Host / Port    : http://{settings.host}:{settings.port}")
    print(f"Gemini Model   : {settings.gemini_model}")
    print(f"Gemini API Key : {'Configured' if settings.gemini_api_key else 'Not set (Offline / Mock Mode available)'}")
    
    # Check FFmpeg
    ffmpeg_ok = shutil.which("ffmpeg") is not None
    ffprobe_ok = shutil.which("ffprobe") is not None
    print(f"FFmpeg Status  : {'Available [OK]' if ffmpeg_ok else 'Missing [WARNING]'}")
    print(f"FFprobe Status : {'Available [OK]' if ffprobe_ok else 'Missing [WARNING]'}")
    print("=" * 65)
    print(f"Opening Web UI at: http://{settings.host}:{settings.port}")
    print("Press Ctrl+C to stop the server.\n")

    uvicorn.run(
        "backend.main:app",
        host=settings.host,
        port=settings.port,
        reload=False
    )

if __name__ == "__main__":
    main()
