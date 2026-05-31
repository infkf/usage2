# Lemon Gym Usage Tracker

Containerized web application that scrapes gym occupancy data from [Lemon Gym](https://www.lemongym.lt/klubu-uzimtumas/), stores it in SQLite, and visualizes it on a dashboard.

## Architecture

| Component | Technology | Purpose |
|-----------|-----------|---------|
| Scraper | Python + Playwright + BeautifulSoup | Fetches occupancy data hourly via the site's REST API, falling back to headless browser if needed |
| Database | SQLite via SQLAlchemy ORM | Persists records to `/app/data/gym.db` on a Docker volume |
| Scheduler | APScheduler (async) | Triggers scraping at the top of every hour; runs once on startup |
| API | FastAPI | Serves REST endpoints on port 8000 |
| Frontend | Vanilla JS + Chart.js | Dark-themed dashboard with current load cards, historical line charts, and a weekly heatmap |

## Quick Start

```bash
docker compose up --build -d
```

Open [http://localhost:8000](http://localhost:8000).

To stop:

```bash
docker compose down        # keeps data volume
docker compose down -v      # wipes data volume
```

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /` | Dashboard UI |
| `GET /api/current` | Latest occupancy for all clubs |
| `GET /api/historical/{club_name}?days=7` | Historical data for a specific club |
| `GET /api/average/{club_name}` | Average occupancy by day-of-week and hour |
| `GET /api/clubs` | List of all tracked club names |

## Running Tests

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m pytest tests/ -v
```

The test suite covers:

- **`tests/test_scraper.py`** — HTML parsing, club name cleaning (marketing tag removal), city assignment
- **`tests/test_database.py`** — SQLAlchemy CRUD, latest-per-club queries, historical filtering, average aggregation
- **`tests/test_api.py`** — All FastAPI endpoints via TestClient, response schemas, edge cases

## Project Structure

```
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
├── database.py          # ORM model and query functions
├── main.py              # FastAPI app, scheduler, endpoints
├── scraper.py           # API → requests → Playwright scraping pipeline
├── static/
│   └── index.html       # Chart.js dashboard
└── tests/
    ├── test_scraper.py
    ├── test_database.py
    └── test_api.py
```

## How the Scraper Works

1. Tries the WordPress REST API endpoint (`/wp-json/api/async-render-block`) first — fast, no browser needed
2. If that fails, falls back to requesting the full page with `requests`
3. If no occupancy data is found in the static HTML (JS-only rendering), launches Playwright Chromium to render the page and extract data
4. Marketing tags (`- naujas✨`, `(atnaujintas✨)`, `- jau greitai 🔜`, etc.) are stripped from club names

## Configuration

The timezone for the scheduler is set via the `TZ` environment variable in `docker-compose.yml` (defaults to `Europe/Vilnius`). The scraping interval is fixed at hourly (`:00`).