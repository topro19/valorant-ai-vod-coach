import cv2
import numpy as np
import os
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
    OpenCV event detector based on daseyun/valorant-timestamp-finder with
    dynamic resolution scaling and kill-banner/skull + killfeed detection.
    """
    def __init__(self, sample_interval_sec: float = 1.0):
        self.sample_interval_sec = sample_interval_sec
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

        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise ValueError(f"Could not open video with OpenCV: {video_path}")

        fps = cap.get(cv2.CAP_PROP_FPS) or 60.0
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = total_frames / fps if total_frames > 0 else 0.0

        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)) or 1920
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) or 1080

        # Normalized coordinates
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

            # 1. Killfeed region check
            kf_crop = frame[kf_y1:kf_y2, kf_x1:kf_x2]
            kf_hsv = cv2.cvtColor(kf_crop, cv2.COLOR_BGR2HSV)
            
            mask_red1 = cv2.inRange(kf_hsv, self.lower_red1, self.upper_red1)
            mask_red2 = cv2.inRange(kf_hsv, self.lower_red2, self.upper_red2)
            red_pixels = int(np.sum(mask_red1 > 0) + np.sum(mask_red2 > 0))

            mask_cyan = cv2.inRange(kf_hsv, self.lower_cyan, self.upper_cyan)
            cyan_pixels = int(np.sum(mask_cyan > 0))

            # 2. Kill Banner (bottom-center skull / kill confirmed badge)
            banner_crop = frame[banner_y1:banner_y2, banner_x1:banner_x2]
            banner_hsv = cv2.cvtColor(banner_crop, cv2.COLOR_BGR2HSV)
            mask_yellow = cv2.inRange(banner_hsv, self.lower_yellow, self.upper_yellow)
            yellow_pixels = int(np.sum(mask_yellow > 0))

            # Score detection
            is_kill_banner = yellow_pixels > (banner_crop.shape[0] * banner_crop.shape[1] * 0.015)
            is_killfeed_active = (red_pixels > 450 and cyan_pixels > 350) or (red_pixels > 1200)

            if (is_kill_banner or is_killfeed_active) and (timestamp_sec - last_detected_time >= 1.5):
                score = 0.9 if is_kill_banner else 0.75
                trigger = "KILL_BANNER" if is_kill_banner else "KILLFEED_COMBAT"
                candidates.append(CandidateTimestamp(timestamp_sec, score, trigger))
                last_detected_time = timestamp_sec

            current_frame += frame_step

        cap.release()
        return candidates
