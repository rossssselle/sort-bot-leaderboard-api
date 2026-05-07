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
    LeaderboardEntry,
    LeaderboardOut,
    PerformanceStats,
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

@app.get("/bots/{bot_id}", response_model=BotDetail, tags=["bots"])
def get_bot(bot_id: int, db: Session = Depends(get_db)):
    bot = db.query(Bot).filter(Bot.id == bot_id).first()
    if not bot:
        raise HTTPException(status_code=404, detail="Bot not found.")

    results = (
        db.query(BenchmarkResult)
        .filter(BenchmarkResult.bot_id == bot_id)
        .all()
    )

    result_list = []
    for r in results:
        result_list.append(
            BenchmarkResultOut(
                input_set=r.input_set.name,
                case_index=r.case_index,
                time_ms=r.time_ms,
                is_correct=r.is_correct,
            )
        )

    # Compute performance stats (exclude timed out results with time_ms=-1)
    valid_results = [r for r in results if r.time_ms >= 0]
    valid_times = [r.time_ms for r in valid_results]

    if valid_times:
        sorted_times = sorted(valid_times)
        n = len(sorted_times)

        best_r = min(valid_results, key=lambda r: r.time_ms)
        worst_r = max(valid_results, key=lambda r: r.time_ms)

        # Percentiles (nearest rank method) are slightly off
        # TODO: Could use statistics.quantiles()
        p25_idx = max(0, int(n * 0.25) - 1)
        p75_idx = max(0, int(n * 0.75) - 1)

        perf = PerformanceStats(
            avg_time_ms=round(statistics.mean(valid_times), 4),
            median_time_ms=round(statistics.median(valid_times), 4),
            best_time_ms=round(sorted_times[0], 4),
            worst_time_ms=round(sorted_times[-1], 4),
            best_case=f"{best_r.input_set.name}/case_{best_r.case_index}",
            worst_case=f"{worst_r.input_set.name}/case_{worst_r.case_index}",
            p25_time_ms=round(sorted_times[p25_idx], 4),
            p75_time_ms=round(sorted_times[p75_idx], 4),
            total_correct=sum(1 for r in results if r.is_correct),
            total_cases=len(results),
        )
    else:
        perf = PerformanceStats(
            total_correct=0,
            total_cases=len(results),
        )

    return BotDetail(
        id=bot.id,
        name=bot.name,
        algorithm=bot.algorithm,
        created_at=bot.created_at,
        results=result_list,
        performance=perf,
    )


@app.get("/algorithms", response_model=list[AlgorithmOut], tags=["info"])
def list_algorithms():
    return [
        AlgorithmOut(name=name, description=info["description"])
        for name, info in ALGORITHM_REGISTRY.items()
    ]
