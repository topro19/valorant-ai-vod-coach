def get_system_instruction(target_agent: str, target_username: str) -> str:
    user_str = target_username if target_username else "Not provided"
    return f"""You are a professional Valorant VOD coach.

You are analyzing a recording belonging to ONE SPECIFIC PLAYER.

TARGET PLAYER:
Agent: {target_agent}
Username: {user_str}

Your job is to analyze ONLY the target player's gameplay.

ABSOLUTE RULE:
Never give gameplay advice about another player.

The recording may switch to teammates or enemies after the target player dies.
When that happens, IGNORE EVERYTHING that happens from the other player's POV.

Do not interpret the actions of a teammate as the target player's actions.
Do not interpret a teammate's kill as the target player's kill.
Do not interpret a teammate's death as the target player's death.
Do not interpret a teammate's positioning as the target player's positioning.
Do not give advice based on spectator footage.

Before analyzing ANY gameplay event, determine:
1. Who is currently being viewed? (Check agent HUD, ability icons, first-person hands/weapons, spectator bars, player names)
2. Is this the target player ({target_agent})?
3. Is the target player alive?
4. Is the footage actually first-person gameplay of the target?
5. Is there enough visual evidence to confidently establish identity?

If identity is uncertain or spectator camera:
CLASSIFY THE EVENT AS UNKNOWN or SPECTATING_TEAMMATE.
Do NOT analyze it.
Set event_valid: false, mistakes: [], positive_actions: [], coaching_advice: null, and set ignored_reason: "IGNORED: Spectating teammate — not analyzed."

Only analyze gameplay while:
CURRENT_PLAYER == TARGET_PLAYER
AND
TARGET_PLAYER_STATUS == ALIVE

If the target player dies:
Stop coaching immediately.
Ignore all subsequent spectator footage.
Resume only when the target player's own POV is visually confirmed again.

False positives are worse than false negatives.
When uncertain, DO NOT BLAME THE TARGET PLAYER.

Do not assume player senses or internal thoughts. Distinguish:
OBSERVED FACT vs INFERENCE vs UNCERTAIN.
Do not invent mistakes. If the player made a good play, explicitly praise it.
If the death was unavoidable, classify death_category as "UNAVOIDABLE".
If caused by mechanics: "MECHANICAL".
If caused by bad decision: "DECISION".
If caused by positioning: "POSITIONING".
If caused by utility: "UTILITY".
If caused by timing: "TIMING".
If mixed: "MIXED".

You must respond ONLY with a valid JSON object matching the requested schema.
"""

GEMINI_ANALYSIS_SCHEMA = {
    "type": "object",
    "properties": {
        "event_id": {"type": "integer"},
        "timestamp_start": {"type": "string"},
        "timestamp_event": {"type": "string"},
        "timestamp_end": {"type": "string"},
        "player_identity": {
            "type": "object",
            "properties": {
                "target_agent": {"type": "string"},
                "detected_agent": {"type": "string"},
                "is_target_player": {"type": "boolean"},
                "confidence": {"type": "number"}
            },
            "required": ["target_agent", "detected_agent", "is_target_player", "confidence"]
        },
        "player_state": {
            "type": "string",
            "enum": [
                "USER_ALIVE",
                "USER_DIED",
                "SPECTATING_TEAMMATE",
                "SPECTATING_ENEMY",
                "ROUND_TRANSITION",
                "BUY_PHASE",
                "UNKNOWN"
            ]
        },
        "event_valid": {"type": "boolean"},
        "ignored_reason": {"type": "string"},
        "event_type": {"type": "string"},
        "result": {"type": "string"},
        "death_category": {"type": "string"},
        "mistake_severity": {"type": "string", "enum": ["CRITICAL", "HIGH", "MEDIUM", "LOW", "NONE"]},
        "avoidable": {"type": "boolean"},
        "confidence": {"type": "number"},
        "summary": {"type": "string"},
        "why_mistake": {"type": "string"},
        "what_you_did": {"type": "string"},
        "what_you_should_have_done": {"type": "string"},
        "mistakes": {
            "type": "array",
            "items": {"type": "string"}
        },
        "positive_actions": {
            "type": "array",
            "items": {"type": "string"}
        },
        "analysis": {
            "type": "object",
            "properties": {
                "crosshair_placement": {"type": "string"},
                "movement": {"type": "string"},
                "peeking": {"type": "string"},
                "positioning": {"type": "string"},
                "angle_selection": {"type": "string"},
                "target_selection": {"type": "string"},
                "utility_usage": {"type": "string"},
                "timing": {"type": "string"},
                "awareness": {"type": "string"},
                "decision_making": {"type": "string"}
            }
        }
    },
    "required": [
        "player_identity",
        "player_state",
        "event_valid",
        "mistake_severity",
        "confidence"
    ]
}

BATCH_GEMINI_ANALYSIS_SCHEMA = {
    "type": "object",
    "properties": {
        "encounters": {
            "type": "array",
            "items": GEMINI_ANALYSIS_SCHEMA
        }
    },
    "required": ["encounters"]
}

def get_batch_montage_prompt(target_agent: str, target_username: str, montage_items: list) -> str:
    user_str = target_username if target_username else "Not provided"
    items_desc = []
    for item in montage_items:
        idx = item.get("encounter_index", 1)
        m_start = item.get("montage_start_str", "00:00")
        m_end = item.get("montage_end_str", "00:00")
        v_start = item.get("start_formatted", "")
        v_end = item.get("end_formatted", "")
        items_desc.append(f"- Duel #{idx}: Montage timestamp {m_start} - {m_end} (Match time {v_start} - {v_end})")
    
    duels_text = "\n".join(items_desc)
    
    return f"""This video is a concatenated combat montage containing {len(montage_items)} duels/fights from a Valorant match.
TARGET PLAYER TO COACH:
- Agent: {target_agent}
- Username: {user_str}

Below are the exact timestamps of each duel in this montage video:
{duels_text}

STRICT COACHING & PLAYER LOCK RULES:
1. For each duel listed above, examine the footage at that duel's montage timestamp range.
2. Determine if the first-person POV belongs to {target_agent} while alive.
3. If {target_agent} is dead and the camera is spectating a teammate or enemy, classify player_state as "SPECTATING_TEAMMATE", event_valid as false, mistakes as [], positive_actions as [], and ignored_reason as "IGNORED: Spectating teammate — not analyzed."
4. If {target_agent} is alive in first-person POV, provide an accurate tactical breakdown: mistakes, positive actions, crosshair placement, positioning, movement, and what the player should have done.
5. Provide one analysis entry in the 'encounters' list for each duel in sequential order, setting event_id to the duel index."""
