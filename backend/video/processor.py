import subprocess
import json
import os
import shutil
from pathlib import Path
from typing import Dict, Any, Optional, Tuple

class VideoProcessor:
    @staticmethod
    def check_ffmpeg() -> bool:
        return shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None

    @staticmethod
    def get_metadata(video_path: str) -> Dict[str, Any]:
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"Video file not found at: {video_path}")

        cmd = [
            "ffprobe",
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            video_path
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        data = json.loads(res.stdout)

        video_stream = next((s for s in data.get("streams", []) if s.get("codec_type") == "video"), None)
        if not video_stream:
            raise ValueError("No video stream found in the uploaded file.")

        duration = float(data.get("format", {}).get("duration", 0.0))
        if duration == 0.0 and "duration" in video_stream:
            duration = float(video_stream["duration"])

        fps = 60.0
        fps_str = video_stream.get("r_frame_rate", "60/1")
        if "/" in fps_str:
            num, den = fps_str.split("/")
            fps = float(num) / float(den) if float(den) > 0 else 60.0
        elif fps_str:
            fps = float(fps_str)

        width = int(video_stream.get("width", 1920))
        height = int(video_stream.get("height", 1080))
        codec = video_stream.get("codec_name", "unknown")
        file_size = int(data.get("format", {}).get("size", os.path.getsize(video_path)))

        return {
            "duration": duration,
            "width": width,
            "height": height,
            "fps": fps,
            "codec": codec,
            "file_size": file_size,
            "filename": os.path.basename(video_path),
            "filepath": str(video_path)
        }

    @staticmethod
    def extract_frame(video_path: str, timestamp_sec: float, output_path: str, width: int = 1280, height: int = 720) -> str:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        cmd = [
            "ffmpeg", "-y",
            "-ss", f"{timestamp_sec:.2f}",
            "-i", video_path,
            "-vframes", "1",
            "-vf", f"scale={width}:{height}",
            "-q:v", "3",
            output_path
        ]
        subprocess.run(cmd, capture_output=True, check=True)
        return output_path

    @staticmethod
    def extract_thumbnail(video_path: str, output_path: str) -> str:
        # Grab thumbnail at 2 seconds or 10%
        return VideoProcessor.extract_frame(video_path, 2.0, output_path)
