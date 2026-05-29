import asyncio
import os
import re
import random
import time
from typing import List, Optional

from playwright.async_api import async_playwright
from loguru import logger
from dotenv import load_dotenv

load_dotenv()


BASE_URL = os.getenv("URL", "https://batdongsan.com.vn/ban-nha-dat")
USER_AGENT_LIST = os.getenv(
    "USER_AGENT_LIST",
    """
Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3,
Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Safari/605.1.15,
Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/88.0.4324.96 Safari/537.36
""",
)
PROXY_LIST = os.getenv("PROXY_LIST", "")
MAX_GOTO_RETRIES = int(os.getenv("MAX_GOTO_RETRIES", "3"))

CARD_SELECTORS = [
    "div.js__card",
    "article.js__card",
    "article[prid]",
    "div[prid]",
]


def _has_digits(value: str) -> bool:
    return bool(value and re.search(r"\d", value))


def _is_price_usable(price: str) -> bool:
    if not price:
        return False
    normalized = price.strip().lower()
    if "thỏa thuận" in normalized or "thoả thuận" in normalized:
        return False
    return _has_digits(normalized)


def _is_area_usable(area: str) -> bool:
    return _has_digits(area)


def _is_record_complete(record: dict) -> bool:
    return (
        bool(record.get("ID"))
        and bool(record.get("Title"))
        and bool(record.get("URL"))
        and bool(record.get("Location"))
        and _is_price_usable(record.get("Price_Raw", ""))
        and _is_area_usable(record.get("Area_Raw", ""))
    )


def _parse_user_agent_list(env_value: str) -> List[str]:
    parts = [p.strip() for p in env_value.split(",") if p.strip()]
    return parts if parts else []


def _choose_proxy() -> Optional[str]:
    if not PROXY_LIST:
        return None
    proxies = [p.strip() for p in PROXY_LIST.split(",") if p.strip()]
    return random.choice(proxies) if proxies else None


def _choose_user_agent() -> str:
    uas = _parse_user_agent_list(USER_AGENT_LIST)
    if uas:
        return random.choice(uas)
    # fallback
    return (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3"
    )


async def _wait_for_listing_cards(page) -> None:
    """Wait until the listing cards are present before extracting data."""
    selector = ", ".join(CARD_SELECTORS)
    try:
        await page.wait_for_selector(selector, timeout=15000)
    except Exception:
        logger.warning("[Scraper] Không thấy card sau khi tải trang; sẽ thử quét với selector dự phòng.")


async def _collect_listing_cards(page):
    for selector in CARD_SELECTORS:
        cards = await page.query_selector_all(selector)
        if cards:
            return cards
    return []

async def extract_data(pages_to_crawl=1):

    data_list = []

    async with async_playwright() as p:
        # Choose proxy and user-agent (anti-bot)
        proxy = _choose_proxy()
        user_agent = _choose_user_agent()

        launch_kwargs = {"headless": True}
        if proxy:
            try:
                launch_kwargs["proxy"] = {"server": proxy}
                logger.info(f"[Scraper] Using proxy: {proxy}")
            except Exception:
                logger.warning("[Scraper] Invalid proxy format, ignoring proxy")

        browser = await p.chromium.launch(**launch_kwargs)

        context = await browser.new_context(user_agent=user_agent)
        page = await context.new_page()

        for page_num in range(1, pages_to_crawl + 1):
            url = f"{BASE_URL}/p{page_num}"

            logger.info(f"[Scraper] Đang quét trang {url}")
            
            try:
                # retry/backoff for navigation to handle transient anti-bot blocks
                nav_succeeded = False
                for attempt in range(MAX_GOTO_RETRIES):
                    try:
                        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                        nav_succeeded = True
                        break
                    except Exception as e:
                        backoff = (2 ** attempt) * random.uniform(0.5, 1.5)
                        logger.warning(f"[Scraper] goto failed (attempt {attempt + 1}): {e}; backoff {backoff:.1f}s")
                        await page.wait_for_timeout(int(backoff * 1000))

                if not nav_succeeded:
                    logger.error(f"[Scraper] Failed to navigate to {url} after retries")
                    continue

                await _wait_for_listing_cards(page)

                # small randomized delay after load
                await page.wait_for_timeout(random.randint(500, 1500))

                # randomized scrolls / human-like movement
                scroll_count = random.randint(2, 4)
                for _ in range(scroll_count):
                    amount = random.randint(600, 1200)
                    await page.mouse.wheel(0, amount)
                    await page.wait_for_timeout(random.randint(400, 1200))
                    # occasional small mouse movement
                    if random.random() < 0.3:
                        try:
                            await page.mouse.move(random.randint(0, 800), random.randint(0, 600))
                        except Exception:
                            pass

                cards = await _collect_listing_cards(page)
                total_cards = len(cards)
                kept = 0
                skipped = 0

                for card in cards:
                    try:
                        prid = await card.get_attribute("prid")
                        link_el = await card.query_selector("a.js__product-link-for-product-id, a[href*='/ban-']")
                        url_tin = f"https://batdongsan.com.vn{await link_el.get_attribute('href')}" if link_el else ""
                        title_el = await card.query_selector(".js__card-title, a.js__card-title, [class*='card-title']")
                        title = await title_el.inner_text() if title_el else ""
                        price_el = await card.query_selector(".re__card-config-price, [class*='card-config-price']")
                        price = await price_el.inner_text() if price_el else ""
                        area_el = await card.query_selector(".re__card-config-area, [class*='card-config-area']")
                        area = await area_el.inner_text() if area_el else ""
                        location_el = await card.query_selector(".re__card-location, [class*='card-location']")
                        location = await location_el.inner_text() if location_el else ""
                        location = location.replace("·", "").strip()
                        date_el = await card.query_selector(".re__card-published-info-published-at, [aria-label*='Đăng'], [class*='published-at']")
                        published_date = await date_el.get_attribute("aria-label") if date_el else "N/A"

                        record = {
                            "ID": prid,
                            "Title": title.strip().replace('\n', ' '),
                            "Price_Raw": price.strip(),
                            "Area_Raw": area.strip(),
                            "Location": location.strip(),
                            "Published_Date": published_date,
                            "URL": url_tin
                        }

                        if _is_record_complete(record):
                            data_list.append(record)
                            kept += 1
                        else:
                            skipped += 1
                    except:
                        skipped += 1
                        continue
                    # small randomized pause between processing cards to reduce request rate
                    try:
                        await page.wait_for_timeout(random.randint(20, 150))
                    except Exception:
                        pass

                logger.info(
                    f"[Scraper] Page {page_num}: kept {kept}/{total_cards} cards "
                    f"(skipped {skipped} incomplete records)"
                )

            except Exception as e:
                logger.error(f"Error: {e}")

        await browser.close()
    return data_list

