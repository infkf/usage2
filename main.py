import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from database import init_db, insert_usage, get_latest_usage, get_historical_usage, get_average_usage, get_club_names
from scraper import scrape

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


async def scrape_and_store():
    logger.info("Running scheduled scrape...")
    try:
        records = await scrape()
        if records:
            insert_usage(records)
            logger.info(f"Stored {len(records)} records")
        else:
            logger.warning("No records scraped")
    except Exception as e:
        logger.error(f"Scrape failed: {e}", exc_info=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    logger.info("Database initialized")

    await scrape_and_store()

    scheduler.add_job(
        scrape_and_store,
        "cron",
        minute=0,
        id="hourly_scrape",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("Scheduler started (hourly at :00)")

    yield

    scheduler.shutdown()
    logger.info("Scheduler shut down")


app = FastAPI(title="Lemon Gym Usage Tracker", lifespan=lifespan)


@app.get("/api/current")
def api_current():
    return get_latest_usage()


@app.get("/api/historical/{club_name}")
def api_historical(club_name: str, days: int = 7):
    return get_historical_usage(club_name, days)


@app.get("/api/average/{club_name}")
def api_average(club_name: str):
    return get_average_usage(club_name)


@app.get("/api/clubs")
def api_clubs():
    return get_club_names()


@app.get("/")
def index():
    return FileResponse("static/index.html")


app.mount("/static", StaticFiles(directory="static"), name="static")