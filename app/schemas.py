
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

# Request models for creating a new bot
class BotCreate(BaseModel):
    name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        examples=["speedy-sorter"],
        description="A unique display name for your bot.",
    )
    algorithm: str = Field(
        ...,
        examples=["quicksort"],
        description="The sorting algorithm to use. See GET /algorithms for options.",
    )


# Response models
class BenchmarkResultOut(BaseModel):
    input_set: str
    case_index: int
    time_ms: float
    is_correct: bool

    model_config = {"from_attributes": True}

class BotOut(BaseModel):
    id: int
    name: str
    algorithm: str
    created_at: datetime

    model_config = {"from_attributes": True}

class PerformanceStats(BaseModel):
    avg_time_ms: Optional[float] = None
    median_time_ms: Optional[float] = None
    best_time_ms: Optional[float] = None
    worst_time_ms: Optional[float] = None
    best_case: Optional[str] = None   # e.g. "small/case_3"
    worst_case: Optional[str] = None  # e.g. "large/case_12"
    p25_time_ms: Optional[float] = None
    p75_time_ms: Optional[float] = None
    total_correct: int = 0
    total_cases: int = 0

class BotDetail(BotOut):
    results: List[BenchmarkResultOut] = []
    performance: Optional[PerformanceStats] = None

class LeaderboardEntry(BaseModel):
    rank: int
    bot_id: int
    bot_name: str
    algorithm: str
    avg_time_ms: float
    total_correct: int
    total_cases: int

# Full leaderboard response
class LeaderboardOut(BaseModel):
    entries: list[LeaderboardEntry]
    total_bots: int

class InputSetOut(BaseModel):
    id: int
    name: str
    num_cases: int

    model_config = {"from_attributes": True}

class AlgorithmOut(BaseModel):
    name: str
    description: str