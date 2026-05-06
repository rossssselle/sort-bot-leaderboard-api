import multiprocessing
import statistics
import time
from pathlib import Path
from typing import Optional, Tuple

from sqlalchemy.orm import Session

from app.algorithms import SortFunction
from app.models import BenchmarkResult, InputSet

# Median of N runs per case
NUM_RUNS = 3 
# Max time allowed per single sort call
SORT_TIMEOUT_SECONDS = 30 

# In-memory cache: input_set_id -> list of int arrays
_input_cache = {}


def load_input_file(file_path: str) -> list:
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Input file not found: {file_path}")

    arrays = []
    for line in path.read_text().strip().splitlines():
        line = line.strip()
        if not line:
            continue
        arrays.append([int(x) for x in line.split(",")])
    return arrays


def get_input_arrays(db: Session, input_set: InputSet) -> list:
    if input_set.id not in _input_cache:
        _input_cache[input_set.id] = load_input_file(input_set.file_path)
    return _input_cache[input_set.id]


def _run_sort_in_process(
    sort_fn: SortFunction,
    arr: list,
    result_queue: multiprocessing.Queue,
) -> None:
    try:
        input_copy = arr.copy()
        start = time.perf_counter_ns()
        output = sort_fn(input_copy)
        elapsed_ns = time.perf_counter_ns() - start
        elapsed_ms = elapsed_ns / 1_000_000
        correct = output == sorted(arr)
        result_queue.put(("ok", elapsed_ms, correct))
    except Exception as e:
        result_queue.put(("error", str(e), False))


def _timed_sort(
    sort_fn: SortFunction,
    arr: list,
    timeout: float = SORT_TIMEOUT_SECONDS,
) -> Tuple[Optional[float], bool, bool]:

    queue = multiprocessing.Queue()
    proc = multiprocessing.Process(
        target=_run_sort_in_process,
        args=(sort_fn, arr, queue),
    )
    proc.start()
    proc.join(timeout=timeout)

    if proc.is_alive():
        # Bot is hanging — kill it
        proc.terminate()
        proc.join(timeout=2)
        if proc.is_alive():
            # Force kill if terminate didn't work
            proc.kill() 
            proc.join()
        return (None, False, True)

    if proc.exitcode != 0:
        return (None, False, False)

    try:
        status, value, correct = queue.get_nowait()
        if status == "ok":
            return (value, correct, False)
        else:
            return (None, False, False)
    except Exception:
        return (None, False, False)


def benchmark_bot(
    db: Session,
    bot_id: int,
    sort_fn: SortFunction,
    input_set: InputSet,
) -> list:
    arrays = get_input_arrays(db, input_set)
    results = []

    for case_index, arr in enumerate(arrays):
        timings = []
        correct = True
        timed_out = False

        for run in range(NUM_RUNS):
            elapsed_ms, is_correct, did_timeout = _timed_sort(sort_fn, arr)

            if did_timeout:
                timed_out = True
                break  # No point running more attempts

            if elapsed_ms is None:
                # Sort crashed — treat as incorrect
                correct = False
                break

            timings.append(elapsed_ms)

            if run == 0:
                correct = is_correct

        if timed_out or not timings:
            # Record a failed/timed-out result
            result = BenchmarkResult(
                bot_id=bot_id,
                input_set_id=input_set.id,
                case_index=case_index,
                # Sentinel value: -1 means timeout/failure
                time_ms=-1,  
                is_correct=False,
            )
        else:
            median_time = statistics.median(timings)
            result = BenchmarkResult(
                bot_id=bot_id,
                input_set_id=input_set.id,
                case_index=case_index,
                time_ms=round(median_time, 4),
                is_correct=correct,
            )

        results.append(result)

    db.add_all(results)
    return results