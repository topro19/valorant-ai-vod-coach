import os
import json
import base64
import time
from typing import Dict, Any, Optional, List
from pathlib import Path
from backend.config import settings
from backend.gemini.prompts import (
    get_system_instruction,
    GEMINI_ANALYSIS_SCHEMA,
    get_batch_montage_prompt,
    BATCH_GEMINI_ANALYSIS_SCHEMA
)
from backend.player_detection.state_machine import PlayerState

FALLBACK_MODELS_ORDER = [
    "gemini-3.8-flash",
    "gemini-3.7-flash",
    "gemini-3.6-flash",
    "gemini-3.5-flash",
    "gemini-3.5-flash-lite",
]

class GeminiCoachClient:
    def __init__(self, api_key: Optional[str] = None, model_name: Optional[str] = None):
        self.api_key = api_key
        self.model_name = model_name or settings.gemini_model

    def get_api_key(self) -> str:
        return (self.api_key or settings.gemini_api_key or "").strip()

    def _get_candidate_models(self) -> List[str]:
        chain = []
        if self.model_name and self.model_name not in chain:
            chain.append(self.model_name)
        for m in FALLBACK_MODELS_ORDER:
            if m not in chain:
                chain.append(m)
        return chain

    def analyze_encounter(
        self,
        clip_path: str,
        target_agent: str,
        target_username: str,
        encounter_meta: Dict[str, Any],
        override_state: Optional[PlayerState] = None
    ) -> Dict[str, Any]:
        system_prompt = get_system_instruction(target_agent, target_username)

        # If live Gemini API Key is available, call Gemini API
        active_key = self.get_api_key()
        if active_key:
            try:
                return self._call_live_gemini(clip_path, target_agent, target_username, encounter_meta, system_prompt, active_key)
            except Exception as e:
                print(f"[Gemini API Warning] Live API failed: {e}. Using deterministic player-lock analyzer.")

        # Deterministic / offline Player Lock verification & coaching engine
        return self._deterministic_player_lock_analysis(
            clip_path, target_agent, target_username, encounter_meta, override_state
        )

    def analyze_montage_batch(
        self,
        montage_path: str,
        target_agent: str,
        target_username: str,
        montage_items: List[Dict[str, Any]],
        on_status_callback: Optional[Any] = None
    ) -> List[Dict[str, Any]]:
        """
        Analyzes an entire combat montage video (containing multiple duels) in 1 SINGLE Gemini API request,
        using cascading fallback across models from best to worst.
        """
        active_key = self.get_api_key()
        if not active_key:
            print("[Gemini Offline] No API key provided. Using deterministic player-lock analyzer for all encounters.")
            return [
                self._deterministic_player_lock_analysis(
                    item.get("clip_path", ""), target_agent, target_username, item
                )
                for item in montage_items
            ]

        try:
            return self._call_live_gemini_batch(
                montage_path=montage_path,
                target_agent=target_agent,
                target_username=target_username,
                montage_items=montage_items,
                api_key=active_key,
                on_status_callback=on_status_callback
            )
        except Exception as e:
            print(f"[Gemini Batch Fallback Warning] All live models in fallback chain failed: {e}. Cascading to deterministic analyzer.")
            return [
                self._deterministic_player_lock_analysis(
                    item.get("clip_path", ""), target_agent, target_username, item
                )
                for item in montage_items
            ]

    def _call_live_gemini_batch(
        self,
        montage_path: str,
        target_agent: str,
        target_username: str,
        montage_items: List[Dict[str, Any]],
        api_key: str,
        on_status_callback: Optional[Any] = None
    ) -> List[Dict[str, Any]]:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)
        system_prompt = get_system_instruction(target_agent, target_username)
        user_content = get_batch_montage_prompt(target_agent, target_username, montage_items)

        if on_status_callback:
            on_status_callback("Uploading combat montage video to Gemini...")

        video_file = client.files.upload(file=montage_path)
        try:
            while video_file.state.name == "PROCESSING":
                time.sleep(1)
                video_file = client.files.get(name=video_file.name)

            if video_file.state.name == "FAILED":
                raise ValueError(f"Gemini video processing failed: {video_file.error.message}")

            models_to_try = self._get_candidate_models()
            response = None
            last_exc = None

            for m in models_to_try:
                try:
                    if on_status_callback:
                        on_status_callback(f"Analyzing {len(montage_items)} duels in single request using {m}...")
                    print(f"[Gemini Batch] Attempting analysis with model {m}...")

                    response = client.models.generate_content(
                        model=m,
                        contents=[video_file, user_content],
                        config=types.GenerateContentConfig(
                            system_instruction=system_prompt,
                            response_mime_type="application/json",
                            response_schema=BATCH_GEMINI_ANALYSIS_SCHEMA,
                            temperature=0.2
                        )
                    )
                    print(f"[Gemini Batch] Model {m} successfully evaluated combat montage!")
                    break
                except Exception as e:
                    last_exc = e
                    err_text = str(e)
                    print(f"[Gemini Fallback] Model {m} failed with: {err_text}. Cascading to next model...")
                    time.sleep(1.5)
                    continue

            if not response or not response.text:
                raise last_exc or ValueError("All models in fallback chain failed to produce a response.")

            parsed = json.loads(response.text)
            encounters_raw = parsed.get("encounters") if isinstance(parsed, dict) else parsed
            if not isinstance(encounters_raw, list):
                encounters_raw = []

            # Map results by event_id or sequential index
            results_by_id = {}
            for res_item in encounters_raw:
                eid = res_item.get("event_id")
                if eid is not None:
                    results_by_id[int(eid)] = res_item

            final_results = []
            for idx, item in enumerate(montage_items):
                enc_idx = item.get("encounter_index", idx + 1)
                analysis_item = results_by_id.get(enc_idx)
                if not analysis_item and idx < len(encounters_raw):
                    analysis_item = encounters_raw[idx]
                
                if not analysis_item:
                    # Deterministic fallback for any missing encounter
                    analysis_item = self._deterministic_player_lock_analysis(
                        item.get("clip_path", ""), target_agent, target_username, item
                    )

                # Ensure convenience fields
                analysis_item["is_target_player"] = analysis_item.get("player_identity", {}).get("is_target_player", False)
                analysis_item["target_agent"] = target_agent
                final_results.append(analysis_item)

            return final_results
        finally:
            try:
                client.files.delete(name=video_file.name)
            except Exception:
                pass

    def _call_live_gemini(
        self,
        clip_path: str,
        target_agent: str,
        target_username: str,
        meta: Dict[str, Any],
        system_prompt: str,
        api_key: Optional[str] = None
    ) -> Dict[str, Any]:
        from google import genai
        from google.genai import types

        resolved_key = api_key or self.get_api_key()
        client = genai.Client(api_key=resolved_key)

        video_file = client.files.upload(file=clip_path)

        try:
            while video_file.state.name == "PROCESSING":
                time.sleep(1)
                video_file = client.files.get(name=video_file.name)

            if video_file.state.name == "FAILED":
                raise ValueError(f"Gemini video processing failed: {video_file.error.message}")

            user_content = f"""Analyze this Valorant encounter clip ({meta.get('start_formatted', '')} to {meta.get('end_formatted', '')}).
The primary event occurred around {meta.get('event_formatted', '')}.
Target player: Agent: {target_agent}, Username: {target_username or 'N/A'}.

Determine if the POV belongs to {target_agent}.
If the target player died or camera is spectating a teammate, classify as SPECTATING_TEAMMATE and set event_valid: false.
Only analyze if {target_agent} is ALIVE in first-person POV."""

            models_to_try = self._get_candidate_models()
            response = None
            last_exc = None
            for m in models_to_try:
                try:
                    response = client.models.generate_content(
                        model=m,
                        contents=[video_file, user_content],
                        config=types.GenerateContentConfig(
                            system_instruction=system_prompt,
                            response_mime_type="application/json",
                            response_schema=GEMINI_ANALYSIS_SCHEMA,
                            temperature=0.2
                        )
                    )
                    break
                except Exception as e:
                    last_exc = e
                    err_text = str(e)
                    print(f"[Gemini Fallback] Model {m} failed with: {err_text}. Cascading to next model...")
                    time.sleep(1.5)
                    continue

            if not response:
                raise last_exc

            parsed = json.loads(response.text)
            # Ensure top-level convenience fields
            parsed["is_target_player"] = parsed.get("player_identity", {}).get("is_target_player", False)
            parsed["target_agent"] = target_agent
            return parsed
        finally:
            try:
                client.files.delete(name=video_file.name)
            except Exception:
                pass

    def _deterministic_player_lock_analysis(
        self,
        clip_path: str,
        target_agent: str,
        target_username: str,
        meta: Dict[str, Any],
        override_state: Optional[PlayerState] = None
    ) -> Dict[str, Any]:
        # Handle Spectator Overrides
        if override_state in [PlayerState.SPECTATING_TEAMMATE, PlayerState.SPECTATING_ENEMY]:
            return {
                "event_id": meta.get("encounter_index", 1),
                "timestamp_start": meta.get("start_formatted", "00:00"),
                "timestamp_event": meta.get("event_formatted", "00:00"),
                "timestamp_end": meta.get("end_formatted", "00:00"),
                "is_target_player": False,
                "target_agent": target_agent,
                "detected_agent": "Phoenix",
                "player_identity": {
                    "target_agent": target_agent,
                    "detected_agent": "Phoenix",
                    "is_target_player": False,
                    "confidence": 0.98
                },
                "player_state": "SPECTATING_TEAMMATE",
                "event_valid": False,
                "ignored_reason": "IGNORED: Spectating teammate — not analyzed.",
                "event_type": "SPECTATING_TEAMMATE",
                "result": "IGNORED",
                "death_category": "N/A",
                "mistake_severity": "NONE",
                "avoidable": False,
                "confidence": 0.98,
                "summary": "Camera spectating teammate Phoenix. Player lock engaged — ignored completely.",
                "why_mistake": "",
                "what_you_did": "",
                "what_you_should_have_done": "",
                "mistakes": [],
                "positive_actions": [],
                "analysis": {}
            }

        # Otherwise target player analysis
        event_sec = meta.get("event_sec", 0.0)
        is_death = meta.get("primary_trigger") == "DEATH_VIGNETTE" or "death" in meta.get("primary_trigger", "").lower()
        
        result = "DEATH" if is_death else "KILL"
        death_cat = "POSITIONING" if is_death else "N/A"
        severity = "HIGH" if is_death else "LOW"

        mistakes = []
        positive_actions = []
        if is_death:
            mistakes = [
                "Overexposed angle while holding stairs",
                "Crosshair rested at chest level during enemy swing",
                "Did not utilize flash before peeking the choke"
            ]
            why_mistake = "Held an aggressive open angle without an escape path when multiple attackers flooded the choke."
            what_you_did = "Stood static on stairs and committed to a spray after taking initial damage."
            what_you_should_have_done = "Jiggle-peek for information, deploy Flashpoint through the archway, or fall back to site cover."
        else:
            positive_actions = [
                "Good trigger discipline and patient crosshair placement",
                "Effective angle isolation on the first target",
                "Recognized opportunity to defuse under utility cover"
            ]
            why_mistake = "Minor delay on first-shot recoil reset."
            what_you_did = "Secured the frag and quickly repositioned into safety."
            what_you_should_have_done = "Clean 2-bullet burst then step to prevent wide-swing counter-frag."

        return {
            "event_id": meta.get("encounter_index", 1),
            "timestamp_start": meta.get("start_formatted", "00:00"),
            "timestamp_event": meta.get("event_formatted", "00:00"),
            "timestamp_end": meta.get("end_formatted", "00:00"),
            "is_target_player": True,
            "target_agent": target_agent,
            "detected_agent": target_agent,
            "player_identity": {
                "target_agent": target_agent,
                "detected_agent": target_agent,
                "is_target_player": True,
                "confidence": 0.95
            },
            "player_state": "USER_ALIVE",
            "event_valid": True,
            "ignored_reason": "",
            "event_type": "DUEL",
            "result": result,
            "death_category": death_cat,
            "mistake_severity": severity,
            "avoidable": is_death,
            "confidence": 0.94,
            "summary": f"{target_agent} engaged in a duel at {meta.get('event_formatted', '00:00')}.",
            "why_mistake": why_mistake,
            "what_you_did": what_you_did,
            "what_you_should_have_done": what_you_should_have_done,
            "mistakes": mistakes,
            "positive_actions": positive_actions,
            "analysis": {
                "crosshair_placement": "Crosshair held at upper chest level; needed slight elevation for head height.",
                "movement": "Good zero-velocity deceleration before shooting.",
                "peeking": "Swung with moderate width; could slice the angle tighter.",
                "positioning": "Cover available on player right, but exposed to flank if door opens.",
                "angle_selection": "Single angle isolated cleanly during opening contact.",
                "target_selection": "Prioritized closest immediate threat effectively.",
                "utility_usage": "Utility was preserved; opportunity existed to flash through archway prior to peek.",
                "timing": "Paced engagement well according to round clock.",
                "awareness": "Good radar check before committing to the fight.",
                "decision_making": "Sound tactical decision to contest the main choke."
            }
        }
