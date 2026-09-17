import cv2
import numpy as np
import os
import subprocess
from typing import List, Dict, Any, Callable, Optional

class CandidateTimestamp:
    def __init__(self, timestamp_sec: float, score: float, trigger_type: str):
        self.timestamp_sec = round(timestamp_sec, 2)
        self.score = round(score, 2)
        self.trigger_type = trigger_type

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp_sec": self.timestamp_sec,
            "timestamp_formatted": self.format_time(self.timestamp_sec),
            "score": self.score,
            "trigger_type": self.trigger_type
        }

    @staticmethod
    def format_time(seconds: float) -> str:
        m = int(seconds // 60)
        s = int(seconds % 60)
        return f"{m:02d}:{s:02d}"

class ValorantTimestampFinder:
    """
    Ultrafast event detector with hardware-accelerated sequential pipe decoding
    and resolution-invariant HSV kill-banner + killfeed detection.
    """
    def __init__(self, sample_interval_sec: float = 2.5):
        self.sample_interval_sec = max(1.0, float(sample_interval_sec))
        # Yellow / Gold kill banner HSV thresholds
        self.lower_yellow = np.array([20, 100, 120])
        self.upper_yellow = np.array([35, 255, 255])
        
        # Red killfeed / damage HSV thresholds
        self.lower_red1 = np.array([0, 120, 100])
        self.upper_red1 = np.array([10, 255, 255])
        self.lower_red2 = np.array([170, 120, 100])
        self.upper_red2 = np.array([180, 255, 255])

        # Cyan / Teal ally HSV thresholds
        self.lower_cyan = np.array([75, 80, 100])
        self.upper_cyan = np.array([105, 255, 255])

    def detect_candidate_events(
        self,
        video_path: str,
        progress_callback: Optional[Callable[[float, str], None]] = None
    ) -> List[CandidateTimestamp]:
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"Video file not found: {video_path}")

        # Try ultrafast hardware-accelerated FFmpeg pipe first
        try:
            return self._detect_via_ffmpeg_pipe(video_path, progress_callback)
        except Exception as e:
            print(f"[TimestampFinder Warning] FFmpeg pipe scan failed ({e}). Falling back to OpenCV.")
            return self._detect_via_opencv(video_path, progress_callback)

    def _get_video_duration(self, video_path: str) -> float:
        try:
            cmd = [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                video_path
            ]
            out = subprocess.check_output(cmd, stderr=subprocess.DEVNULL).decode().strip()
            return float(out)
        except Exception:
            cap = cv2.VideoCapture(video_path)
            fps = cap.get(cv2.CAP_PROP_FPS) or 60.0
            frames = cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0
            cap.release()
            return frames / fps if frames > 0 else 0.0

    def _detect_via_ffmpeg_pipe(
        self,
        video_path: str,
        progress_callback: Optional[Callable[[float, str], None]] = None
    ) -> List[CandidateTimestamp]:
        duration = self._get_video_duration(video_path)
        scan_width, scan_height = 640, 360
        frame_bytes = scan_width * scan_height * 3

        # Spawn FFmpeg with auto hardware acceleration and low-res frame sampling
        cmd = [
            "ffmpeg", "-v", "error",
            "-hwaccel", "auto",
            "-i", video_path,
            "-vf", f"fps=1/{self.sample_interval_sec},scale={scan_width}:{scan_height}",
            "-f", "rawvideo",
            "-pix_fmt", "bgr24",
            "-"
        ]
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=frame_bytes * 10)

        # Pre-calculate normalized crops for 640x360
        kf_y1, kf_y2 = int(scan_height * 0.06), int(scan_height * 0.24)
        kf_x1, kf_x2 = int(scan_width * 0.72), int(scan_width * 0.99)

        banner_y1, banner_y2 = int(scan_height * 0.68), int(scan_height * 0.88)
        banner_x1, banner_x2 = int(scan_width * 0.42), int(scan_width * 0.58)

        candidates: List[CandidateTimestamp] = []
        frame_idx = 0
        last_detected_time = -10.0

        try:
            while True:
                raw = proc.stdout.read(frame_bytes)
                if not raw or len(raw) < frame_bytes:
                    break

                timestamp_sec = frame_idx * self.sample_interval_sec
                if progress_callback and duration > 0:
                    pct = min(99.0, (timestamp_sec / duration) * 100.0)
                    progress_callback(
                        pct,
                        f"Scanning video for duel events ({CandidateTimestamp.format_time(timestamp_sec)} / {CandidateTimestamp.format_time(duration)})"
                    )

                frame = np.frombuffer(raw, dtype=np.uint8).reshape((scan_height, scan_width, 3))

                # 1. Killfeed check
                kf_crop = frame[kf_y1:kf_y2, kf_x1:kf_x2]
                kf_hsv = cv2.cvtColor(kf_crop, cv2.COLOR_BGR2HSV)
                mask_red1 = cv2.inRange(kf_hsv, self.lower_red1, self.upper_red1)
                mask_red2 = cv2.inRange(kf_hsv, self.lower_red2, self.upper_red2)
                red_pixels = int(np.sum(mask_red1 > 0) + np.sum(mask_red2 > 0))

                mask_cyan = cv2.inRange(kf_hsv, self.lower_cyan, self.upper_cyan)
                cyan_pixels = int(np.sum(mask_cyan > 0))

                # 2. Kill banner check
                banner_crop = frame[banner_y1:banner_y2, banner_x1:banner_x2]
                banner_hsv = cv2.cvtColor(banner_crop, cv2.COLOR_BGR2HSV)
                mask_yellow = cv2.inRange(banner_hsv, self.lower_yellow, self.upper_yellow)
                yellow_pixels = int(np.sum(mask_yellow > 0))

                # Resolution-invariant thresholds
                banner_total = banner_crop.shape[0] * banner_crop.shape[1]
                kf_total = kf_crop.shape[0] * kf_crop.shape[1]

                is_kill_banner = yellow_pixels > (banner_total * 0.015)
                is_killfeed_active = (red_pixels > (kf_total * 0.005) and cyan_pixels > (kf_total * 0.004)) or (red_pixels > (kf_total * 0.012))

                if (is_kill_banner or is_killfeed_active) and (timestamp_sec - last_detected_time >= 2.0):
                    score = 0.9 if is_kill_banner else 0.75
                    trigger = "KILL_BANNER" if is_kill_banner else "KILLFEED_COMBAT"
                    candidates.append(CandidateTimestamp(timestamp_sec, score, trigger))
                    last_detected_time = timestamp_sec

                frame_idx += 1
        finally:
            proc.kill()

        return candidates

    def _detect_via_opencv(
        self,
        video_path: str,
        progress_callback: Optional[Callable[[float, str], None]] = None
    ) -> List[CandidateTimestamp]:
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise ValueError(f"Could not open video with OpenCV: {video_path}")

        fps = cap.get(cv2.CAP_PROP_FPS) or 60.0
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = total_frames / fps if total_frames > 0 else 0.0

        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)) or 1920
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) or 1080

        kf_y1, kf_y2 = int(height * 0.06), int(height * 0.24)
        kf_x1, kf_x2 = int(width * 0.72), int(width * 0.99)

        banner_y1, banner_y2 = int(height * 0.68), int(height * 0.88)
        banner_x1, banner_x2 = int(width * 0.42), int(width * 0.58)

        frame_step = max(1, int(fps * self.sample_interval_sec))
        candidates: List[CandidateTimestamp] = []

        current_frame = 0
        last_detected_time = -10.0

        while current_frame < total_frames:
            cap.set(cv2.CAP_PROP_POS_FRAMES, current_frame)
            ret, frame = cap.read()
            if not ret or frame is None:
                break

            timestamp_sec = current_frame / fps
            if progress_callback and total_frames > 0:
                pct = (current_frame / total_frames) * 100.0
                progress_callback(pct, f"Scanning video for duel events ({CandidateTimestamp.format_time(timestamp_sec)} / {CandidateTimestamp.format_time(duration)})")

            kf_crop = frame[kf_y1:kf_y2, kf_x1:kf_x2]
            kf_hsv = cv2.cvtColor(kf_crop, cv2.COLOR_BGR2HSV)
            mask_red1 = cv2.inRange(kf_hsv, self.lower_red1, self.upper_red1)
            mask_red2 = cv2.inRange(kf_hsv, self.lower_red2, self.upper_red2)
            red_pixels = int(np.sum(mask_red1 > 0) + np.sum(mask_red2 > 0))

            mask_cyan = cv2.inRange(kf_hsv, self.lower_cyan, self.upper_cyan)
            cyan_pixels = int(np.sum(mask_cyan > 0))

            banner_crop = frame[banner_y1:banner_y2, banner_x1:banner_x2]
            banner_hsv = cv2.cvtColor(banner_crop, cv2.COLOR_BGR2HSV)
            mask_yellow = cv2.inRange(banner_hsv, self.lower_yellow, self.upper_yellow)
            yellow_pixels = int(np.sum(mask_yellow > 0))

            banner_total = banner_crop.shape[0] * banner_crop.shape[1]
            kf_total = kf_crop.shape[0] * kf_crop.shape[1]

            is_kill_banner = yellow_pixels > (banner_total * 0.015)
            is_killfeed_active = (red_pixels > (kf_total * 0.005) and cyan_pixels > (kf_total * 0.004)) or (red_pixels > (kf_total * 0.012))

            if (is_kill_banner or is_killfeed_active) and (timestamp_sec - last_detected_time >= 2.0):
                score = 0.9 if is_kill_banner else 0.75
                trigger = "KILL_BANNER" if is_kill_banner else "KILLFEED_COMBAT"
                candidates.append(CandidateTimestamp(timestamp_sec, score, trigger))
                last_detected_time = timestamp_sec

            current_frame += frame_step

        cap.release()
        return candidates

