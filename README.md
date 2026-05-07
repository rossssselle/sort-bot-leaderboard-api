# Sort Bot Leaderboard API

An API for submitting sorting bots to compete on a leaderboard. Built with Python3 + FastAPI + SQLite + SQLAlchemy.

To run the server locally, copy the real input files into the `data/` folder, then:

```bash
pip3 install -r requirements.txt
uvicorn app.main:app --reload
```

Note: A `.db` file is created automatically on first run.

## API Documentation

FastAPI generates Swagger docs automatically. This includes examples for requests and responses bodies (with corresponding response codes). To view the full API documentation, run the server locally and go to: http://127.0.0.1:8000/docs

### Summary Table

| Request | Route          | Purpose                                  |
| ------- | -------------- | ---------------------------------------- |
| POST    | /bots          | Submit a new bot (triggers benchmarking) |
| GET     | /leaderboard   | View leaderboard                         |
| GET     | /bots/{bot_id} | Get bot performance details              |
| GET     | /algorithms    | List available sorting algorithms        |

Example `POST /bots` request:

```bash
curl -X 'POST' \
    'http://127.0.0.1:8000/bots' \
    -H 'accept: application/json' \
    -H 'Content-Type: application/json' \
    -d '{
    "name": "mr. bubbles",
    "algorithm": "bubble_sort"
}
```

Response body:

```
{
  "id": 3,
  "name": "mr. bubbles",
  "algorithm": "bubble_sort",
  "created_at": "2026-05-07T00:10:39.870778"
}
```

## Bot Evaluation

When a bot is submitted via `POST /bots`, it is immediately benchmarked against all loaded input sets. Each input file contains 19 test cases designed to expose the strengths and weaknesses of different sorting algorithms (already sorted, reversed, many duplicates, random). The evaluation process has 4 layers:

### Timing

Each test case is run 3 times using `time.perf_counter_ns()` for nanosecond precision. The median time is recorded to reduce noise from OS scheduling and garbage collection.

### Correctness

Correctness is validated on the first of three runs and subsequent runs are used only for timing stability. After each sort, the output is compared against Python's `sorted()`. A bot that produces an incorrect result is flagged but still appears on the leaderboard and receives no rank.

### Safety

Each sort call executes in an isolated subprocess with a 30 second timeout. If a bot hangs or enters an infinite loop, the process is terminated and the result is recorded as a failure `(time_ms=-1)`, and doesn't affect the server.

### Storage

Results are stored per case rather than as aggregates. This preserves the raw data for detailed analysis such as best/worst case identification, percentile breakdowns, and per-input-set leaderboards, without needing to rerun benchmarks.

## Design Decisions and Tradeoffs

- **Synchronous benchmarking** - Slow on large inputs
- **SQLite over PostgreSQL** - Zero setup
- **Predefined algorithms** - Avoids complexity and sandboxing
- **Individual results over precomputed summaries** - More DB writes at submission
- **Median over mean for timing** - Less inuitive, but robust for outliers
- **30 second timeout** - Long enough for O(n^2) computation, short enough for hanging
- **Visible failed bots/correctness** - A fast wrong bot is worse than a slow accurate bot

## Stretch Goals Implemented

### Handle bots that hang or go into infinite loops

Each sort call runs in a separate `multiprocessing.Process` with a 30 second timeout. If the bot hangs or enters an infinite loop, the process gets terminated and the result is recorded with `time_ms=-1` and `is_correct=False`. There's a fallback to `kill()` if `terminate()` doesn't work. This means that one bad bot won't affect the server running. A `sleep_sort` algorithm was added in `algorithms.py` for testing purposes.

### Enable filtering/sorting the leaderboard

Filters all are optional and can be combined. They are applied at the SQL level to ensure efficiency. `sort_by` supports `avg_time` (default), name, and correctness. Correct bots always rank above incorrect. The `GET /leaderboard` endpoint has these query params: `algorithm` (filter by algorithm name), `input_set` (filter results to a specific input set like "small" or "large"), and `correct_only` (boolean to hide incorrect bots).

### Get bot performance details (e.g. best input, worst input, avg time on all inputs, performance quartiles)

The bot detail endpoint now returns best case, worst case, median, and quartiles. This is to not only see just how fast a bot is on average, but how consistent it is and which specific inputs give it trouble. This was easy to add because I'd already made the decision to store per case results rather than aggregates.

## Bot Submission and Leaderboard Flow

![Submission Flow POST /bots](/diagrams/submission_flow.png "Submission Flow")

![Leaderboard Flow GET /leaderboard](/diagrams/get_leaderboard_flow.png "Get Leaderboard Flow")
