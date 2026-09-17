import unittest
import os
import tempfile
import subprocess
from pathlib import Path

from backend.clip_extractor.extractor import ClipExtractor
from backend.gemini.client import GeminiCoachClient, FALLBACK_MODELS_ORDER
from backend.gemini.prompts import get_batch_montage_prompt, BATCH_GEMINI_ANALYSIS_SCHEMA

class TestMontageBatch(unittest.TestCase):
    def test_fallback_models_order(self):
        client = GeminiCoachClient(model_name="gemini-3.8-flash")
        candidates = client._get_candidate_models()
        self.assertEqual(candidates[0], "gemini-3.8-flash")
        self.assertIn("gemini-3.7-flash", candidates)
        self.assertIn("gemini-3.6-flash", candidates)
        self.assertIn("gemini-3.5-flash", candidates)
        self.assertIn("gemini-3.5-flash-lite", candidates)
        # Verify ordering
        idx_38 = candidates.index("gemini-3.8-flash")
        idx_36 = candidates.index("gemini-3.6-flash")
        idx_lite = candidates.index("gemini-3.5-flash-lite")
        self.assertTrue(idx_38 < idx_36 < idx_lite)

    def test_batch_prompt_generation(self):
        items = [
            {"encounter_index": 1, "montage_start_str": "00:00", "montage_end_str": "00:15", "start_formatted": "02:10", "end_formatted": "02:25"},
            {"encounter_index": 2, "montage_start_str": "00:15", "montage_end_str": "00:32", "start_formatted": "04:45", "end_formatted": "05:02"},
        ]
        prompt = get_batch_montage_prompt("Jett", "AcePlayer", items)
        self.assertIn("Jett", prompt)
        self.assertIn("AcePlayer", prompt)
        self.assertIn("Duel #1", prompt)
        self.assertIn("Duel #2", prompt)
        self.assertIn("SPECTATING_TEAMMATE", prompt)

    def test_montage_chunking_and_offsets(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create two tiny 1-second synthetic video clips using ffmpeg
            clip1 = os.path.join(tmpdir, "enc1.mp4")
            clip2 = os.path.join(tmpdir, "enc2.mp4")
            for c in [clip1, clip2]:
                cmd = [
                    "ffmpeg", "-y",
                    "-f", "lavfi", "-i", "color=c=black:s=320x240:d=1.0",
                    "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono",
                    "-t", "1.0",
                    "-c:v", "libx264", "-c:a", "aac",
                    c
                ]
                subprocess.run(cmd, capture_output=True, check=True)

            encs = [
                {"encounter_index": 1, "clip_path": clip1, "duration": 1.0, "start_formatted": "00:10", "end_formatted": "00:11"},
                {"encounter_index": 2, "clip_path": clip2, "duration": 1.0, "start_formatted": "00:40", "end_formatted": "00:41"}
            ]

            montages = ClipExtractor.create_combat_montages(
                encounters=encs,
                output_dir=tmpdir,
                job_id="test_job",
                max_duration_sec=3600.0
            )

            self.assertEqual(len(montages), 1)
            m = montages[0]
            self.assertTrue(os.path.exists(m["montage_path"]))
            self.assertEqual(len(m["items"]), 2)
            self.assertEqual(m["items"][0]["montage_start_sec"], 0.0)
            self.assertEqual(m["items"][0]["montage_end_sec"], 1.0)
            self.assertEqual(m["items"][1]["montage_start_sec"], 1.0)
            self.assertEqual(m["items"][1]["montage_end_sec"], 2.0)

    def test_offline_batch_analysis(self):
        client = GeminiCoachClient(api_key="")
        items = [
            {"encounter_index": 1, "start_formatted": "00:10", "event_formatted": "00:15", "end_formatted": "00:20", "primary_trigger": "KILL_BANNER"},
            {"encounter_index": 2, "start_formatted": "01:10", "event_formatted": "01:15", "end_formatted": "01:20", "primary_trigger": "DEATH_VIGNETTE"}
        ]
        results = client.analyze_montage_batch(
            montage_path="",
            target_agent="Reyna",
            target_username="AimGod",
            montage_items=items
        )
        self.assertEqual(len(results), 2)
        self.assertTrue(results[0]["is_target_player"])
        self.assertEqual(results[0]["result"], "KILL")
        self.assertTrue(results[1]["is_target_player"])
        self.assertEqual(results[1]["result"], "DEATH")

if __name__ == "__main__":
    unittest.main()
