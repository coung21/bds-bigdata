import asyncio
import os
import re

from playwright.async_api import async_playwright
from loguru import logger
from dotenv import load_dotenv

load_dotenv()


BASE_URL = os.getenv("URL", "https://batdongsan.com.vn/ban-nha-dat")


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

async def extract_data(pages_to_crawl=1):

    data_list = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3"
        )
        page = await context.new_page()

        for page_num in range(1, pages_to_crawl + 1):
            url = f"{BASE_URL}/p{page_num}"

            logger.info(f"[Scraper] Đang quét trang {url}")
            
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)

                for _ in range(2):
                    await page.mouse.wheel(0, 1000)
                    await page.wait_for_timeout(600)

                cards = await page.query_selector_all("div.js__card")
                total_cards = len(cards)
                kept = 0
                skipped = 0

                for card in cards:
                    try:
                        prid = await card.get_attribute("prid")
                        link_el = await card.query_selector("a.js__product-link-for-product-id")
                        url_tin = f"https://batdongsan.com.vn{await link_el.get_attribute('href')}" if link_el else ""
                        title_el = await card.query_selector(".js__card-title")
                        title = await title_el.inner_text() if title_el else ""
                        price = await (await card.query_selector(".re__card-config-price")).inner_text() if await card.query_selector(".re__card-config-price") else ""
                        area = await (await card.query_selector(".re__card-config-area")).inner_text() if await card.query_selector(".re__card-config-area") else ""
                        location_el = await card.query_selector(".re__card-location")
                        location = await location_el.inner_text() if location_el else ""
                        location = location.replace("·", "").strip()
                        date_el = await card.query_selector(".re__card-published-info-published-at")
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

                logger.info(
                    f"[Scraper] Page {page_num}: kept {kept}/{total_cards} cards "
                    f"(skipped {skipped} incomplete records)"
                )

            except Exception as e:
                logger.error(f"Error: {e}")

        await browser.close()
    return data_list

