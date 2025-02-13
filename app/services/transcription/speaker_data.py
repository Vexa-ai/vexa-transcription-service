from dataclasses import dataclass
from typing import List

@dataclass
class SpeakerActivity:
    speaker: str
    start_time: float
    end_time: float
    mic_level: float

@dataclass
class SpeakerData:
    speaker: str
    activities: List[SpeakerActivity] 