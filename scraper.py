import re
import logging
from datetime import datetime
from zoneinfo import ZoneInfo
import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

TARGET_URL = "https://www.lemongym.lt/klubu-uzimtumas/"

CITY_MAP = {
    "Šiaulių klubai": "Šiauliai",
    "Kauno klubai": "Kaunas",
    "Vilniaus klubai": "Vilnius",
}

MARKETING_TAGS = [
    r"\s*-\s*naujas✨",
    r"\s*\(atnaujintas✨\)",
    r"\s*-\s*jau greitai 🔜",
    r"\s*\(new\)",
    r"\s*NEW",
    r"\s*✨",
    r"\s*🔜",
]


def clean_club_name(name: str) -> str:
    name = name.strip()
    for pattern in MARKETING_TAGS:
        name = re.sub(pattern, "", name, flags=re.IGNORECASE)
    return name.strip()


def parse_html(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    records = []
    now = datetime.now(ZoneInfo("Europe/Vilnius")).replace(tzinfo=None)

    block = soup.find("div", class_="clubs-occupancy-block")
    if not block:
        block = soup

    current_city = None
    heading_tags = ["h1", "h2", "h3", "h4", "h5", "h6"]

    for element in block.find_all(recursive=True):
        if element.name in heading_tags:
            heading_text = element.get_text(strip=True)
            for lt_name, en_name in CITY_MAP.items():
                if lt_name.lower() in heading_text.lower():
                    current_city = en_name
                    break
            continue

        if element.name == "div" and "clubs-occupancy" in element.get("class", []):
            if "clubs-occupancies" in element.get("class", []):
                continue

            club_div = element.find("div", class_="clubs-occupancy__club")
            pct_tag = element.find(
                "h6", class_=lambda c: c and "clubs-occupancy__percentage" in c
            )

            if not club_div or not pct_tag:
                continue

            name_tag = club_div.find(
                lambda tag: tag.name in heading_tags
                and "xs-small" in (tag.get("class") or [])
            )
            if not name_tag:
                name_tag = club_div.find(lambda tag: tag.name in heading_tags)
            if not name_tag:
                name_tag = club_div.find("h6")

            addr_tag = club_div.find("p")

            raw_name = name_tag.get_text(strip=True) if name_tag else ""
            address = addr_tag.get_text(strip=True) if addr_tag else ""
            pct_text = pct_tag.get_text(strip=True)

            club_name = clean_club_name(raw_name)

            match = re.search(r"(\d+)", pct_text)
            usage = int(match.group(1)) if match else 0

            if not current_city:
                if "Vilnius" in address or "vilnius" in address.lower():
                    current_city = "Vilnius"
                elif "Kaunas" in address or "kaunas" in address.lower():
                    current_city = "Kaunas"
                elif "Šiauliai" in address or "šiauliai" in address.lower():
                    current_city = "Šiauliai"

            records.append(
                {
                    "club_name": club_name,
                    "city": current_city or "Unknown",
                    "address": address,
                    "usage_percentage": usage,
                    "timestamp": now,
                }
            )

    return records


async def scrape_with_playwright() -> list[dict]:
    from playwright.async_api import async_playwright

    logger.info("Starting Playwright scraper...")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(TARGET_URL, wait_until="networkidle", timeout=60000)
        await page.wait_for_selector(
            ".clubs-occupancy__percentage", timeout=30000
        )
        await page.wait_for_timeout(2000)
        html = await page.content()
        await browser.close()

    records = parse_html(html)
    logger.info(f"Scraped {len(records)} clubs with Playwright")
    return records


async def scrape_with_requests() -> list[dict]:
    logger.info("Starting requests-based scraper via API endpoint...")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "X-Requested-With": "XMLHttpRequest",
        "Accept": "application/json",
        "Referer": TARGET_URL,
    }

    api_url = (
        "https://www.lemongym.lt/wp-json/api/async-render-block"
        "?pid=MTI2NQ==&bid=YWNmL2NsdWJzLW9jY3VwYW5jeQ==&rest_language=lt"
    )

    async with httpx.AsyncClient(timeout=30) as client:
        try:
            resp = await client.get(api_url, headers=headers)
            resp.raise_for_status()
            data = resp.json()

            if data.get("success") and data.get("data", {}).get("success"):
                html_content = data["data"]["content"]
                records = parse_html(html_content)
                if records:
                    logger.info(f"Scraped {len(records)} clubs via API")
                    return records

            logger.warning("API response missing data, trying requests with full page...")
        except Exception as e:
            logger.warning(f"API endpoint failed: {e}, trying full page...")

        try:
            resp = await client.get(TARGET_URL, headers=headers)
            resp.raise_for_status()
            html = resp.text
            records = parse_html(html)
            if records:
                logger.info(f"Scraped {len(records)} clubs from full page")
                return records
            logger.warning("Full page returned no records (JS-rendered content missing)")
        except Exception as e:
            logger.warning(f"Full page request failed: {e}")

    return []


async def scrape() -> list[dict]:
    try:
        records = await scrape_with_requests()
        if records:
            return records
    except Exception as e:
        logger.warning(f"scrape_with_requests raised: {e}")

    logger.info("Falling back to Playwright for JS-rendered content...")
    return await scrape_with_playwright()