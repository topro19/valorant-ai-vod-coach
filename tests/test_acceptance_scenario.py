import unittest
import os
import json
from pathlib import Path

from backend.player_detection.state_machine import PlayerIdentityStateMachine, PlayerState
from backend.gemini.client import GeminiCoachClient
from backend.reports.generator import CoachingReportGenerator

class TestCriticalAcceptanceScenario(unittest.TestCase):
    """
    CRITICAL ACCEPTANCE TEST:
    Target Player: Agent = Breach, Username = TargetPlayer

    Timeline Scenario:
    - 00:30 Breach POV -> ANALYZE
    - 01:00 Breach dies -> ANALYZE (Breach death)
    - 01:05 Phoenix teammate POV
    - 01:10 Phoenix kills enemy
    - 01:20 Phoenix makes terrible peek
    - 01:25 Phoenix dies
    - 01:40 Next round
    - 01:45 Breach POV returns
    - 02:00 Breach takes duel

    Verifies:
    1. 00:30 is analyzed for Breach
    2. 01:00 is analyzed for Breach death
    3. 01:05-01:25 is IGNORED ENTIRELY
    4. ZERO coaching advice generated from Phoenix actions
    5. Phoenix kills/deaths/peeks are NEVER attributed to the user
    6. Report contains NO "Phoenix should have..." or "Phoenix made..."
    7. 01:45 resumes analysis
    8. 02:00 is analyzed for Breach
    """

    def setUp(self):
        self.target_agent = "Breach"
        self.target_user = "TargetPlayer"
        self.sm = PlayerIdentityStateMachine(target_agent=self.target_agent, target_username=self.target_user)
        self.gemini = GeminiCoachClient()

    def test_player_lock_state_machine_and_zero_advice(self):
        # 1. 00:00 - 00:30 Breach alive & in combat
        state_30 = self.sm.update_state(
            detected_agent="Breach",
            detected_username="TargetPlayer",
            is_alive=True,
            is_spectating=False,
            is_buy_phase=False,
            confidence=0.98,
            timestamp_sec=30.0
        )
        self.assertEqual(state_30, PlayerState.USER_ALIVE)
        self.assertTrue(self.sm.is_eligible_for_analysis(state_30))

        # Analyze 00:30 duel
        meta_30 = {"encounter_index": 1, "start_formatted": "00:15", "event_formatted": "00:30", "end_formatted": "00:35", "primary_trigger": "KILL_BANNER"}
        enc_30 = self.gemini._deterministic_player_lock_analysis("", self.target_agent, self.target_user, meta_30)
        self.assertTrue(enc_30["event_valid"])
        self.assertTrue(enc_30["player_identity"]["is_target_player"])
        self.assertEqual(enc_30["player_state"], "USER_ALIVE")

        # 2. 01:00 Breach dies
        state_60 = self.sm.update_state(
            detected_agent="Breach",
            detected_username="TargetPlayer",
            is_alive=False,
            is_spectating=False,
            is_buy_phase=False,
            confidence=0.95,
            timestamp_sec=60.0
        )
        self.assertEqual(state_60, PlayerState.USER_DIED)

        meta_60 = {"encounter_index": 2, "start_formatted": "00:50", "event_formatted": "01:00", "end_formatted": "01:03", "primary_trigger": "DEATH_VIGNETTE"}
        enc_60 = self.gemini._deterministic_player_lock_analysis("", self.target_agent, self.target_user, meta_60)
        self.assertTrue(enc_60["event_valid"])
        self.assertEqual(enc_60["result"], "DEATH")
        self.assertEqual(enc_60["player_identity"]["target_agent"], "Breach")

        # 3. 01:05 - 01:25 Camera switches to Phoenix teammate POV
        state_phoenix = self.sm.update_state(
            detected_agent="Phoenix",
            detected_username="TeammatePhoenix",
            is_alive=True,
            is_spectating=True,
            is_buy_phase=False,
            confidence=0.97,
            timestamp_sec=65.0
        )
        self.assertEqual(state_phoenix, PlayerState.SPECTATING_TEAMMATE)
        self.assertFalse(self.sm.is_eligible_for_analysis(state_phoenix))

        # Teammate Phoenix kills enemy at 01:10, bad peek at 01:20, dies at 01:25
        meta_phoenix = {
            "encounter_index": 3,
            "start_formatted": "01:05",
            "event_formatted": "01:15",
            "end_formatted": "01:25",
            "primary_trigger": "KILL_BANNER"
        }
        enc_phoenix = self.gemini._deterministic_player_lock_analysis(
            clip_path="",
            target_agent=self.target_agent,
            target_username=self.target_user,
            meta=meta_phoenix,
            override_state=PlayerState.SPECTATING_TEAMMATE
        )

        # CRITICAL CHECK: Spectator footage must be marked invalid with ZERO coaching advice
        self.assertFalse(enc_phoenix["event_valid"], "Spectator event must NOT be valid")
        self.assertFalse(enc_phoenix["player_identity"]["is_target_player"], "Phoenix must not be recognized as target player")
        self.assertEqual(enc_phoenix["player_state"], "SPECTATING_TEAMMATE")
        self.assertEqual(len(enc_phoenix["mistakes"]), 0, "Teammate bad peek must NOT generate mistakes for user")
        self.assertEqual(enc_phoenix["result"], "IGNORED")
        self.assertIn("IGNORED", enc_phoenix["ignored_reason"])

        # 4. 01:40 Next round transition -> 01:45 Breach returns
        state_buy = self.sm.update_state(
            detected_agent="Breach",
            detected_username="TargetPlayer",
            is_alive=True,
            is_spectating=False,
            is_buy_phase=True,
            confidence=0.96,
            timestamp_sec=100.0
        )
        self.assertEqual(state_buy, PlayerState.BUY_PHASE)

        # 5. 02:00 Breach takes duel
        state_120 = self.sm.update_state(
            detected_agent="Breach",
            detected_username="TargetPlayer",
            is_alive=True,
            is_spectating=False,
            is_buy_phase=False,
            confidence=0.98,
            timestamp_sec=120.0
        )
        self.assertEqual(state_120, PlayerState.USER_ALIVE)
        self.assertTrue(self.sm.is_eligible_for_analysis(state_120))

        meta_120 = {"encounter_index": 4, "start_formatted": "01:50", "event_formatted": "02:00", "end_formatted": "02:08", "primary_trigger": "KILL_BANNER"}
        enc_120 = self.gemini._deterministic_player_lock_analysis("", self.target_agent, self.target_user, meta_120)
        self.assertTrue(enc_120["event_valid"])
        self.assertTrue(enc_120["player_identity"]["is_target_player"])

        # 6. Generate Coaching Report
        all_encounters = [enc_30, enc_60, enc_phoenix, enc_120]
        report = CoachingReportGenerator.generate_report(
            target_agent=self.target_agent,
            target_username=self.target_user,
            encounters=all_encounters,
            video_metadata={"duration": 130.0}
        )

        report_json_str = json.dumps(report).lower()

        # VERIFY: Phoenix is NEVER mentioned as making mistakes or having advice
        self.assertNotIn("phoenix should have", report_json_str)
        self.assertNotIn("phoenix made", report_json_str)
        self.assertNotIn("you should have done what phoenix", report_json_str)

        # VERIFY: Exactly 3 target encounters analyzed, 1 spectator encounter ignored
        summary = report["match_summary"]
        self.assertEqual(summary["analyzed_target_encounters"], 3)
        self.assertEqual(summary["ignored_spectator_encounters"], 1)
        self.assertEqual(summary["target_agent"], "Breach")

        print("\n========================================================")
        print("CRITICAL ACCEPTANCE TEST PASSED SUCCESSFULLY!")
        print("[PASS] Breach 00:30 -> Analyzed")
        print("[PASS] Breach 01:00 -> Analyzed (Death)")
        print("[PASS] Phoenix 01:05-01:25 -> 100% IGNORED (Zero Advice)")
        print("[PASS] Breach 01:45-02:00 -> Resumed and Analyzed")
        print("[PASS] Coaching report contains ZERO advice for Phoenix")
        print("========================================================\n")

if __name__ == "__main__":
    unittest.main()
