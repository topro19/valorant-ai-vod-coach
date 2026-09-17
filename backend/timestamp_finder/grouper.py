from typing import List, Dict, Any
from backend.timestamp_finder.detector import CandidateTimestamp

class EncounterWindow:
    def __init__(
        self,
        encounter_index: int,
        start_sec: float,
        event_sec: float,
        end_sec: float,
        candidate_count: int,
        primary_trigger: str
    ):
        self.encounter_index = encounter_index
        self.start_sec = round(start_sec, 2)
        self.event_sec = round(event_sec, 2)
        self.end_sec = round(end_sec, 2)
        self.candidate_count = candidate_count
        self.primary_trigger = primary_trigger

    def to_dict(self) -> Dict[str, Any]:
        return {
            "encounter_index": self.encounter_index,
            "start_sec": self.start_sec,
            "event_sec": self.event_sec,
            "end_sec": self.end_sec,
            "duration": round(self.end_sec - self.start_sec, 2),
            "start_formatted": self.format_time(self.start_sec),
            "event_formatted": self.format_time(self.event_sec),
            "end_formatted": self.format_time(self.end_sec),
            "candidate_count": self.candidate_count,
            "primary_trigger": self.primary_trigger
        }

    @staticmethod
    def format_time(seconds: float) -> str:
        m = int(seconds // 60)
        s = int(seconds % 60)
        return f"{m:02d}:{s:02d}"

class EncounterGrouper:
    @staticmethod
    def group_events(
        candidates: List[CandidateTimestamp],
        video_duration: float,
        merge_window_sec: float = 5.0,
        clutch_merge_window_sec: float = 16.0,
        max_normal_cluster_sec: float = 16.0,
        max_clutch_cluster_sec: float = 60.0,
        pre_roll_sec: float = 7.0,
        post_roll_sec: float = 4.0
    ) -> List[EncounterWindow]:
        if not candidates:
            return []

        # Sort candidates by timestamp
        sorted_candidates = sorted(candidates, key=lambda c: c.timestamp_sec)
        
        # 1. Cluster nearby timestamps with adaptive clutch awareness
        clusters: List[List[CandidateTimestamp]] = []
        current_cluster: List[CandidateTimestamp] = [sorted_candidates[0]]

        for cand in sorted_candidates[1:]:
            prev_cand = current_cluster[-1]
            first_cand = current_cluster[0]

            # A cluster is a candidate clutch/multi-kill if it contains player KILL_BANNERs
            has_player_action = any(c.trigger_type == "KILL_BANNER" for c in current_cluster) or (cand.trigger_type == "KILL_BANNER")
            
            # Dynamic merge window and max duration based on whether it's an active player multi-kill/clutch sequence
            allowed_merge_window = clutch_merge_window_sec if has_player_action else merge_window_sec
            allowed_max_duration = max_clutch_cluster_sec if has_player_action else max_normal_cluster_sec

            is_close = (cand.timestamp_sec - prev_cand.timestamp_sec) <= allowed_merge_window
            is_within_limit = (cand.timestamp_sec - first_cand.timestamp_sec) <= allowed_max_duration

            if is_close and is_within_limit:
                current_cluster.append(cand)
            else:
                clusters.append(current_cluster)
                current_cluster = [cand]

        if current_cluster:
            clusters.append(current_cluster)

        # 2. Convert clusters to expanded encounter windows
        encounters: List[EncounterWindow] = []
        for idx, cluster in enumerate(clusters):
            # Check for clutch / multi-kill
            player_kills = sum(1 for c in cluster if c.trigger_type == "KILL_BANNER")
            is_clutch = player_kills >= 2

            event_sec = cluster[0].timestamp_sec
            for c in cluster:
                if c.trigger_type in ["KILL_BANNER", "DEATH_VIGNETTE"]:
                    event_sec = c.timestamp_sec
                    break

            start_sec = max(0.0, cluster[0].timestamp_sec - pre_roll_sec)
            end_sec = min(video_duration, cluster[-1].timestamp_sec + post_roll_sec)

            # Cap individual encounter duration: 65s for clutch/multi-kills, 25s for isolated duels
            max_encounter_dur = 65.0 if is_clutch else 25.0
            if (end_sec - start_sec) > max_encounter_dur:
                end_sec = start_sec + max_encounter_dur

            # Prevent overlap with previous encounter
            if encounters and start_sec < encounters[-1].end_sec:
                if encounters[-1].end_sec - encounters[-1].start_sec > 4.0:
                    midpoint = (encounters[-1].end_sec + start_sec) / 2.0
                    encounters[-1].end_sec = midpoint
                    start_sec = midpoint
                else:
                    start_sec = encounters[-1].end_sec + 0.5
                    end_sec = max(start_sec + 3.0, end_sec)

            trigger = "CLUTCH_MULTIKILL" if is_clutch else ("KILL_BANNER" if any(c.trigger_type == "KILL_BANNER" for c in cluster) else "KILLFEED_COMBAT")

            encounters.append(EncounterWindow(
                encounter_index=idx + 1,
                start_sec=start_sec,
                event_sec=event_sec,
                end_sec=end_sec,
                candidate_count=len(cluster),
                primary_trigger=trigger
            ))

        return encounters

