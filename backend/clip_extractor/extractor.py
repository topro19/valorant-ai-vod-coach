import subprocess
import os
from pathlib import Path
from typing import List, Dict, Any, Optional
from backend.timestamp_finder.grouper import EncounterWindow

class ClipExtractor:
    @staticmethod
    def extract_encounter_clip(
        video_path: str,
        encounter: EncounterWindow,
        output_dir: str,
        job_id: str
    ) -> Dict[str, str]:
        os.makedirs(output_dir, exist_ok=True)
        clip_filename = f"encounter_{encounter.encounter_index:03d}.mp4"
        thumb_filename = f"encounter_{encounter.encounter_index:03d}.jpg"
        
        clip_path = os.path.join(output_dir, clip_filename)
        thumb_path = os.path.join(output_dir, thumb_filename)

        duration = max(1.0, encounter.end_sec - encounter.start_sec)

        # Fast re-encode or stream copy for exact seek precision
        cmd = [
            "ffmpeg", "-y",
            "-ss", f"{encounter.start_sec:.2f}",
            "-i", video_path,
            "-t", f"{duration:.2f}",
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-crf", "23",
            "-c:a", "aac",
            "-movflags", "+faststart",
            clip_path
        ]
        res = subprocess.run(cmd, capture_output=True)
        if res.returncode != 0:
            # Fallback with slower exact seek if fast seek fails
            cmd_fallback = [
                "ffmpeg", "-y",
                "-i", video_path,
                "-ss", f"{encounter.start_sec:.2f}",
                "-t", f"{duration:.2f}",
                "-c:v", "libx264",
                "-preset", "ultrafast",
                "-c:a", "copy",
                "-movflags", "+faststart",
                clip_path
            ]
            subprocess.run(cmd_fallback, capture_output=True, check=True)

        # Extract thumbnail at event_sec
        relative_thumb_time = max(0.0, min(duration, encounter.event_sec - encounter.start_sec))
        cmd_thumb = [
            "ffmpeg", "-y",
            "-ss", f"{relative_thumb_time:.2f}",
            "-i", clip_path,
            "-vframes", "1",
            "-vf", "scale=640:360",
            "-q:v", "4",
            thumb_path
        ]
        subprocess.run(cmd_thumb, capture_output=True)

        return {
            "clip_path": clip_path,
            "clip_filename": clip_filename,
            "thumb_path": thumb_path,
            "thumb_filename": thumb_filename
        }
