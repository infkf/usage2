# AGENTS.md

## Commands

```bash
# Run all tests (requires venv with deps installed)
python -m pytest tests/ -v

# Run a single test module
python -m pytest tests/test_scraper.py -v

# Build and run the full stack
docker compose up --build -d

# View logs
docker compose logs -f app

# Stop (data persists), or wipe data with -v flag
docker compose down
```

## Architecture

Single-container app. `main.py` is the FastAPI entrypoint that also starts an APScheduler on startup. There is no separate worker process — the scheduler runs inside uvicorn.

- **`scraper.py`** — Tries the WP REST API first (`/wp-json/api/async-render-block`), falls back to `requests` full-page fetch, then Playwright headless Chromium if the HTML has no occupancy data (JS-only rendering).
- **`database.py`** — Module-level globals `engine` / `SessionLocal` / `Base`. Tests monkeypatch these to use a temp SQLite file. The DB lives at `<CWD>/data/gym.db` created at import time.
- **`main.py`** — FastAPI app with lifespan handler that runs an initial scrape, then schedules hourly cron.

## Testing

- Tests swap `database.engine` and `database.SessionLocal` with in-memory/temp SQLite instances via fixture monkeypatching. This is how all three test files work — don't introduce a different pattern without updating all of them.
- API tests mock `main.scrape` with `AsyncMock(return_value=[])` to prevent real HTTP calls during TestClient startup (the lifespan handler calls `scrape_and_store`).
- `test_scraper.py` tests `parse_html` and `clean_club_name` against static HTML fixtures — no network calls.
- Database uses SQLite `strftime` (not `extract`) for day-of-week and hour grouping — SQLite doesn't support `EXTRACT`.

## Scraper gotchas

- The `MARKETING_TAGS` regex list must have `\(new\)` before `NEW` because the broader pattern must match first, otherwise the parentheses in `(new)` get partially stripped.
- The scraper identifies cities from `<h5>` headings (`Šiaulių klubai`, `Kauno klubai`, `Vilniaus klubai`). City resolution also falls back to checking the address string for the city name.
- Club name cleaning removes Lithuanian marketing tags: `- naujas✨`, `(atnaujintas✨)`, `- jau greitai 🔜`.

## Key files

| File | Role |
|------|------|
| `main.py` | FastAPI app + scheduler entrypoint |
| `scraper.py` | Scraping logic (API → requests → Playwright) |
| `database.py` | SQLAlchemy model and all query functions |
| `static/index.html` | Self-contained Chart.js dashboard |
| `docker-compose.yml` | Named volume `gym_data` at `/app/data` |

## Runtime

- Port: 8000
- Timezone: `Europe/Vilnius` (set in docker-compose)
- Playwright Chromium is installed in the Docker image — the fallback scraper needs it
- The `data/` directory is created at import time by `database.py` and mapped to a Docker volume for persistence