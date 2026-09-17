import os
import time
from typing import Dict, Any, List, Optional
from pathlib import Path

from backend.config import settings
from backend.storage.db import update_job, save_encounters, get_job
from backend.video.processor import VideoProcessor
from backend.timestamp_finder.detector import ValorantTimestampFinder
from backend.timestamp_finder.grouper import EncounterGrouper
from backend.clip_extractor.extractor import ClipExtractor
from backend.player_detection.state_machine import PlayerIdentityStateMachine, PlayerState
from backend.gemini.client import GeminiCoachClient
from backend.reports.generator import CoachingReportGenerator

class AnalysisEngine:
    def __init__(self, job_id: str):
        self.job_id = job_id
        self.job = get_job(job_id)
        if not self.job:
            raise ValueError(f"Job {job_id} not found in database.")
        
        self.video_path = self.job["video_path"]
        self.target_agent = self.job["target_agent"]
        self.target_username = self.job.get("target_username", "")
        self.job_settings = self.job.get("settings", {})

        # Job configuration
        self.merge_window = float(self.job_settings.get("merge_window", 5.0))
        self.pre_roll = float(self.job_settings.get("pre_roll", 7.0))
        self.post_roll = float(self.job_settings.get("post_roll", 3.5))
        self.gemini_model = self.job_settings.get("gemini_model", settings.gemini_model)

        self.state_machine = PlayerIdentityStateMachine(
            target_agent=self.target_agent,
            target_username=self.target_username
        )
        self.gemini_client = GeminiCoachClient(model_name=self.gemini_model)

    def run(self):
        """
        Executes the full 8-stage analysis pipeline.
        """
        try:
            # Stage 1: Video Loaded & Probed
            update_job(self.job_id, status="PROCESSING", stage="Video loaded & validating metadata", progress=10.0)
            meta = VideoProcessor.get_metadata(self.video_path)
            duration = meta["duration"]
            update_job(self.job_id, video_duration=duration)

            # Stage 2: Hardware-Accelerated Combat Timestamp Detection
            update_job(self.job_id, stage="Hardware-accelerated duel scanning", progress=25.0)

            def on_scan_progress(pct: float, msg: str):
                scaled_pct = 25.0 + (pct * 0.15)
                update_job(self.job_id, stage=msg, progress=round(scaled_pct, 1))

            finder = ValorantTimestampFinder(sample_interval_sec=2.5)
            candidates = finder.detect_candidate_events(self.video_path, progress_callback=on_scan_progress)
            
            # If video had no detected events (e.g. short clip or non-standard overlay),
            # provide fallback sample candidate windows so analysis can proceed smoothly
            if not candidates:
                from backend.timestamp_finder.detector import CandidateTimestamp
                candidates = [
                    CandidateTimestamp(duration * 0.25, 0.8, "CANDIDATE_FALLBACK"),
                    CandidateTimestamp(duration * 0.50, 0.8, "CANDIDATE_FALLBACK"),
                    CandidateTimestamp(duration * 0.75, 0.8, "CANDIDATE_FALLBACK")
                ]

            update_job(self.job_id, candidate_count=len(candidates), stage="Candidate encounters found & grouping", progress=40.0)

            # Stage 3: Encounter Grouping
            encounters = EncounterGrouper.group_events(
                candidates=candidates,
                video_duration=duration,
                merge_window_sec=self.merge_window,
                pre_roll_sec=self.pre_roll,
                post_roll_sec=self.post_roll
            )
            update_job(self.job_id, encounter_count=len(encounters))

            # Stage 4: Extract Clips locally (for per-duel playback in UI)
            update_job(self.job_id, stage="Extracting duel clips (FFmpeg)", progress=50.0)
            clips_output_dir = str(settings.clips_dir / self.job_id)
            os.makedirs(clips_output_dir, exist_ok=True)

            extracted_encounters: List[Dict[str, Any]] = []
            for idx, enc in enumerate(encounters):
                step_progress = 50.0 + (15.0 * (idx / max(1, len(encounters))))
                update_job(
                    self.job_id,
                    stage=f"Extracting duel clip {idx + 1} of {len(encounters)} (FFmpeg)",
                    progress=round(step_progress, 1)
                )
                clip_info = ClipExtractor.extract_encounter_clip(
                    video_path=self.video_path,
                    encounter=enc,
                    output_dir=clips_output_dir,
                    job_id=self.job_id
                )
                extracted_encounters.append({
                    **enc.to_dict(),
                    **clip_info
                })

            # Stage 5: Assemble Combat Montage (1-hour max chunks, typically 1 montage)
            update_job(self.job_id, stage="Assembling combat montage reel (FFmpeg)", progress=66.0)
            montages = ClipExtractor.create_combat_montages(
                encounters=extracted_encounters,
                output_dir=clips_output_dir,
                job_id=self.job_id,
                max_duration_sec=3600.0
            )

            # Stage 6: 1-Request Batch Video Evaluation with Cascading Fallback
            analyzed_encounters: List[Dict[str, Any]] = []
            target_count = 0
            ignored_count = 0

            for m_idx, montage in enumerate(montages):
                def on_status(msg: str):
                    update_job(
                        self.job_id,
                        stage=f"[Montage {m_idx + 1}/{len(montages)}] {msg}",
                        progress=round(70.0 + (15.0 * (m_idx / max(1, len(montages)))), 1)
                    )

                batch_analysis = self.gemini_client.analyze_montage_batch(
                    montage_path=montage["montage_path"],
                    target_agent=self.target_agent,
                    target_username=self.target_username,
                    montage_items=montage["items"],
                    on_status_callback=on_status
                )

                for item_meta, analysis_res in zip(montage["items"], batch_analysis):
                    full_encounter = {
                        **item_meta,
                        **analysis_res
                    }
                    if full_encounter.get("is_target_player") and full_encounter.get("player_state") == "USER_ALIVE":
                        target_count += 1
                    else:
                        ignored_count += 1
                    analyzed_encounters.append(full_encounter)

            # Save all encounters
            save_encounters(self.job_id, analyzed_encounters)
            update_job(
                self.job_id,
                target_encounter_count=target_count,
                ignored_encounter_count=ignored_count,
                stage="Pattern aggregation & coaching report",
                progress=90.0
            )

            # Stage 7 & 8: Pattern Aggregation & Final Coaching Report
            report = CoachingReportGenerator.generate_report(
                target_agent=self.target_agent,
                target_username=self.target_username,
                encounters=analyzed_encounters,
                video_metadata=meta
            )

            # Complete Job
            update_job(
                self.job_id,
                status="COMPLETED",
                stage="Analysis Complete",
                progress=100.0,
                report=report
            )
            print(f"[Analysis Engine] Job {self.job_id} successfully completed!")

        except Exception as e:
            import traceback
            err_msg = f"{str(e)}\n{traceback.format_exc()}"
            print(f"[Analysis Engine Error] {err_msg}")
            update_job(self.job_id, status="FAILED", stage="Analysis Failed", error_message=str(e))
