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
