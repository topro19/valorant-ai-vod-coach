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
            "thumb_filename": thumb_filename,
            "duration": duration
        }

    @staticmethod
    def _format_seconds(sec: float) -> str:
        m, s = divmod(int(sec), 60)
        h, m = divmod(m, 60)
        if h > 0:
            return f"{h:02d}:{m:02d}:{s:02d}"
        return f"{m:02d}:{s:02d}"

    @classmethod
    def create_combat_montages(
        cls,
        encounters: List[Dict[str, Any]],
        output_dir: str,
        job_id: str,
        max_duration_sec: float = 3600.0
    ) -> List[Dict[str, Any]]:
        """
        Concatenates individual duel clips into continuous combat montages (up to 1 hour each).
        Uses fast stream copy (-c copy) so concatenation takes under 1 second without re-encoding.
        Returns a list of montage objects with timeline offsets for each duel.
        """
        os.makedirs(output_dir, exist_ok=True)
        if not encounters:
            return []

        # Split encounters into chunks of max_duration_sec
        montage_chunks: List[List[Dict[str, Any]]] = []
        current_chunk: List[Dict[str, Any]] = []
        current_chunk_duration = 0.0

        for enc in encounters:
            dur = enc.get("duration")
            if dur is None:
                dur = max(1.0, float(enc.get("end_sec", 0.0)) - float(enc.get("start_sec", 0.0)))
            
            if current_chunk and (current_chunk_duration + dur > max_duration_sec):
                montage_chunks.append(current_chunk)
                current_chunk = [enc]
                current_chunk_duration = dur
            else:
                current_chunk.append(enc)
                current_chunk_duration += dur

        if current_chunk:
            montage_chunks.append(current_chunk)

        montage_results = []
        for m_idx, chunk in enumerate(montage_chunks, start=1):
            montage_filename = f"combat_montage_{m_idx:02d}.mp4"
            montage_path = os.path.join(output_dir, montage_filename)
            concat_list_file = os.path.join(output_dir, f"concat_list_{m_idx:02d}.txt")

            # Write concat demuxer file
            # In ffmpeg concat demuxer on Windows, paths must use forward slashes or escape backslashes
            with open(concat_list_file, "w", encoding="utf-8") as f:
                for item in chunk:
                    clean_path = str(Path(item["clip_path"]).resolve()).replace("\\", "/")
                    f.write(f"file '{clean_path}'\n")

            # Execute ffmpeg concat
            cmd_copy = [
                "ffmpeg", "-y",
                "-f", "concat",
                "-safe", "0",
                "-i", concat_list_file,
                "-c", "copy",
                "-movflags", "+faststart",
                montage_path
            ]
            res = subprocess.run(cmd_copy, capture_output=True)
            if res.returncode != 0 or not os.path.exists(montage_path) or os.path.getsize(montage_path) == 0:
                # Fallback to fast re-encode if stream copy fails
                cmd_reencode = [
                    "ffmpeg", "-y",
                    "-f", "concat",
                    "-safe", "0",
                    "-i", concat_list_file,
                    "-c:v", "libx264",
                    "-preset", "ultrafast",
                    "-c:a", "aac",
                    "-movflags", "+faststart",
                    montage_path
                ]
                subprocess.run(cmd_reencode, capture_output=True, check=True)

            # Compute timeline offsets within this montage
            items_with_offsets = []
            cumulative_sec = 0.0
            for item in chunk:
                dur = item.get("duration")
                if dur is None:
                    dur = max(1.0, float(item.get("end_sec", 0.0)) - float(item.get("start_sec", 0.0)))
                
                m_start = cumulative_sec
                m_end = cumulative_sec + dur
                cumulative_sec += dur

                item_copy = dict(item)
                item_copy["montage_start_sec"] = m_start
                item_copy["montage_end_sec"] = m_end
                item_copy["montage_start_str"] = cls._format_seconds(m_start)
                item_copy["montage_end_str"] = cls._format_seconds(m_end)
                items_with_offsets.append(item_copy)

            montage_results.append({
                "montage_index": m_idx,
                "montage_filename": montage_filename,
                "montage_path": montage_path,
                "total_duration": cumulative_sec,
                "items": items_with_offsets
            })

            # Clean up temporary concat list file
            try:
                os.remove(concat_list_file)
            except Exception:
                pass

        return montage_results
