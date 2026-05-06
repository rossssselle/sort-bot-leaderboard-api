import statistics
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Query
from sqlalchemy import Integer, func
from sqlalchemy.orm import Session

from app.algorithms import ALGORITHM_REGISTRY, get_sort_function
from app.benchmark import benchmark_bot
from app.database import Base, engine, get_db
from app.models import BenchmarkResult, Bot, InputSet
from app.schemas import (
    AlgorithmOut,
    BenchmarkResultOut,
    BotCreate,
    BotDetail,
    BotOut,
    InputSetOut,
    LeaderboardEntry,
    LeaderboardOut,
)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

def _seed_input_sets(db: Session) -> None:
    if not DATA_DIR.exists():
        print(f"Data directory not found at {DATA_DIR}. Create it and add input files.")
        return

    for txt_file in sorted(DATA_DIR.glob("inputs_*.txt")):
        # Derive a friendly name like "small" from "inputs_small.txt"
        name = txt_file.stem.replace("inputs_", "")

        existing = db.query(InputSet).filter(InputSet.name == name).first()
        if existing:
            continue

        # Count lines to know how many cases
        num_cases = sum(1 for line in txt_file.read_text().strip().splitlines() if line.strip())

        input_set = InputSet(
            name=name,
            file_path=str(txt_file),
            num_cases=num_cases,
        )
        db.add(input_set)
        print(f"Loaded input set '{name}' ({num_cases} cases) from {txt_file.name}")

    db.commit()

@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    db = next(get_db())
    try:
        _seed_input_sets(db)
    finally:
        db.close()
    yield

app = FastAPI(
    title="Sort Bot Leaderboard API",
    description="Submit sorting bots and compete on the leaderboard!",
    version="1.0.0",
    lifespan=lifespan,
)

@app.post("/bots", response_model=BotOut, status_code=201, tags=["bots"])
def create_bot(body: BotCreate, db: Session = Depends(get_db)):
    # Validate algorithm exists
    try:
        sort_fn = get_sort_function(body.algorithm)
    except KeyError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Check for duplicate name
    if db.query(Bot).filter(Bot.name == body.name).first():
        raise HTTPException(
            status_code=409,
            detail=f"A bot named '{body.name}' already exists.",
        )

    # Create bot
    bot = Bot(name=body.name, algorithm=body.algorithm)
    db.add(bot)
    # Get the bot.id before benchmarking
    db.flush() 

    # Benchmark against all input sets
    input_sets = db.query(InputSet).all()
    if not input_sets:
        raise HTTPException(
            status_code=503,
            detail="No input sets loaded. Add input files to the data/ directory.",
        )

    for input_set in input_sets:
        benchmark_bot(db, bot.id, sort_fn, input_set)

    db.commit()
    db.refresh(bot)
    return bot


@app.get("/leaderboard", response_model=LeaderboardOut, tags=["leaderboard"])
def get_leaderboard(
    sort_by: str = Query(
        default="avg_time",
        description="Sort leaderboard by: avg_time, name, or correctness",
    ),
    algorithm: Optional[str] = Query(
        default=None,
        description="Filter to only bots using this algorithm (e.g. quicksort)",
    ),
    input_set: Optional[str] = Query(
        default=None,
        description="Filter results to a specific input set (e.g. small, medium, large)",
    ),
    correct_only: bool = Query(
        default=False,
        description="If true, only show bots with 100% correctness",
    ),
    db: Session = Depends(get_db),
):
    # Build the base query
    query = (
        db.query(
            Bot.id,
            Bot.name,
            Bot.algorithm,
            func.avg(BenchmarkResult.time_ms).label("avg_time_ms"),
            func.sum(BenchmarkResult.is_correct.cast(Integer)).label("total_correct"),
            func.count(BenchmarkResult.id).label("total_cases"),
        )
        .join(BenchmarkResult, Bot.id == BenchmarkResult.bot_id)
    )

    # Apply filters
    if algorithm:
        query = query.filter(Bot.algorithm == algorithm)

    if input_set:
        query = query.join(InputSet, BenchmarkResult.input_set_id == InputSet.id).filter(
            InputSet.name == input_set
        )

    rows = query.group_by(Bot.id).all()

    # Build entries
    entries = []
    for row in rows:
        all_correct = int(row.total_correct) == int(row.total_cases)

        if correct_only and not all_correct:
            continue

        entries.append(
            {
                "bot_id": row.id,
                "bot_name": row.name,
                "algorithm": row.algorithm,
                "avg_time_ms": round(float(row.avg_time_ms), 4),
                "total_correct": int(row.total_correct),
                "total_cases": int(row.total_cases),
                "all_correct": all_correct,
            }
        )

    # Sort by correct bots first (by avg time), then incorrect bots
    if sort_by == "correctness":
        entries.sort(key=lambda e: (-e["total_correct"], e["avg_time_ms"]))
    elif sort_by == "name":
        entries.sort(key=lambda e: e["bot_name"].lower())
    else:  # default: avg_time
        entries.sort(key=lambda e: (not e["all_correct"], e["avg_time_ms"]))

    # Assign ranks
    leaderboard = []
    rank_counter = 0
    for entry in entries:
        if entry["all_correct"]:
            rank_counter += 1
            rank = rank_counter
        else:
            rank = -1

        leaderboard.append(
            LeaderboardEntry(
                rank=rank,
                bot_id=entry["bot_id"],
                bot_name=entry["bot_name"],
                algorithm=entry["algorithm"],
                avg_time_ms=entry["avg_time_ms"],
                total_correct=entry["total_correct"],
                total_cases=entry["total_cases"],
            )
        )

    return LeaderboardOut(entries=leaderboard, total_bots=len(leaderboard))