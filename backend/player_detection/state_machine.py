from enum import Enum
from typing import Optional, Dict, Any, List

class PlayerState(str, Enum):
    USER_ALIVE = "USER_ALIVE"
    USER_DIED = "USER_DIED"
    SPECTATING_TEAMMATE = "SPECTATING_TEAMMATE"
    SPECTATING_ENEMY = "SPECTATING_ENEMY"
    ROUND_TRANSITION = "ROUND_TRANSITION"
    BUY_PHASE = "BUY_PHASE"
    UNKNOWN = "UNKNOWN"

class PlayerIdentityStateMachine:
    """
    Strict State Machine enforcing the Player Lock System.
    Guarantees that teammate/enemy spectator segments are never analyzed
    as user gameplay decisions.
    """
    def __init__(self, target_agent: str, target_username: Optional[str] = None):
        self.target_agent = target_agent.strip().capitalize() if target_agent else ""
        self.target_username = target_username.strip() if target_username else ""
        self.current_state = PlayerState.UNKNOWN
        self.history: List[Dict[str, Any]] = []

    def update_state(
        self,
        detected_agent: Optional[str],
        detected_username: Optional[str],
        is_alive: bool,
        is_spectating: bool,
        is_buy_phase: bool,
        confidence: float,
        timestamp_sec: float
    ) -> PlayerState:
        """
        Transitions the state machine according to strict player lock rules.
        """
        detected_agent_norm = detected_agent.strip().capitalize() if detected_agent else ""
        detected_user_norm = detected_username.strip() if detected_username else ""

        # Identity match logic
        agent_matches = bool(self.target_agent and detected_agent_norm and self.target_agent.lower() == detected_agent_norm.lower())
        user_matches = bool(self.target_username and detected_user_norm and self.target_username.lower() in detected_user_norm.lower())

        is_identity_confirmed = agent_matches or user_matches

        # State transition evaluation
        next_state = PlayerState.UNKNOWN

        if is_buy_phase:
            if is_identity_confirmed and not is_spectating:
                next_state = PlayerState.BUY_PHASE
            else:
                next_state = PlayerState.ROUND_TRANSITION
        elif is_spectating:
            next_state = PlayerState.SPECTATING_TEAMMATE
        elif not is_alive:
            if self.current_state == PlayerState.USER_ALIVE and is_identity_confirmed:
                next_state = PlayerState.USER_DIED
            else:
                next_state = PlayerState.SPECTATING_TEAMMATE
        else:
            # Player is alive and not explicitly in spectator mode
            if is_identity_confirmed and confidence >= 0.70:
                # Can only return to USER_ALIVE with strong confirmation
                next_state = PlayerState.USER_ALIVE
            elif self.current_state in [PlayerState.SPECTATING_TEAMMATE, PlayerState.USER_DIED]:
                # If previously spectating or dead, DO NOT eagerly switch back without confirmed match
                next_state = PlayerState.SPECTATING_TEAMMATE
            else:
                next_state = PlayerState.UNKNOWN

        # Record history
        self.history.append({
            "timestamp_sec": timestamp_sec,
            "previous_state": self.current_state.value,
            "next_state": next_state.value,
            "detected_agent": detected_agent_norm,
            "detected_username": detected_user_norm,
            "confidence": confidence
        })

        self.current_state = next_state
        return self.current_state

    def is_eligible_for_analysis(self, state: Optional[PlayerState] = None) -> bool:
        """
        Strict Rule: Only USER_ALIVE segments are eligible for gameplay coaching.
        UNKNOWN must NEVER be treated as USER_ALIVE.
        """
        check_state = state or self.current_state
        return check_state == PlayerState.USER_ALIVE
