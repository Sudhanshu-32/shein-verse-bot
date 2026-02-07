import os
import asyncio
import aiohttp
import hashlib
import logging
from datetime import datetime
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from telegram import Bot
from telegram.constants import ParseMode

# ---------------- LOGGING ----------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

class SheinVerseBot:
    def __init__(self):
        self.bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.chat_id = os.getenv("TELEGRAM_CHAT_ID")

        if not self.bot_token or not self.chat_id:
            raise ValueError("❌ Telegram env missing")

        self.bot = Bot(token=self.bot_token)

        self.urls = [
            "https://www.shein.in/c/sverse-5939-37961",
            "https://m.shein.in/c/sverse-5939-37961"
        ]

        self.headers = {
            "User-Agent": "Mozilla/5.0",
            "Accept-Language": "en-US,en;q=0.9"
        }

        self.seen_products = set()
        self.last_summary_count = 0

        logger.info("✅ MEN SHEIN VERSE BOT WITH SUMMARY READY")

    # ---------------- FETCH ----------------
    async def fetch(self, url):
        try:
            async with aiohttp.ClientSession(headers=self.headers) as session:
                async with session.get(url, timeout=15) as r:
                    if r.status == 200:
                        return await r.text()
        except Exception as e:
            logger.warning(e)
        return None

    # ---------------- EXTRACT ONLY MEN ----------------
    def extract_products(self, html):
        soup = BeautifulSoup(html, "html.parser")
        products = []

        men_keywords = [
            "men", "mens", "man",
            "tshirt", "shirt", "hoodie",
            "jacket", "cargo", "jeans",
            "track", "pants", "shorts"
        ]

        for a in soup.find_all("a", href=True):
            href = a["href"].lower()

            if "/p-" not in href:
                continue

            if not any(k in href for k in ["men", "mens"]):
                continue

            img = a.find("img")
            name = img.get("alt", "").lower() if img else ""

            if not any(k in name for k in men_keywords):
                continue

            product_url = urljoin("https://www.shein.in", href)
            pid = hashlib.md5(product_url.encode()).hexdigest()[:12]

            image = ""
            if img and img.get("src"):
                image = img["src"]
                if image.startswith("//"):
                    image = "https:" + image

            products.append({
                "id": pid,
                "name": name.title()[:80] or "Men SHEIN VERSE Product",
                "price": "₹---",
                "url": product_url,
                "image": image,
                "time": datetime.now()
            })

            if len(products) >= 30:
                break

        return products

    # ---------------- SEND ALERT ----------------
    async def send_alert(self, p):
        caption = (
            f"🔥 *MEN SHEIN VERSE STOCK ALERT*\n\n"
            f"*{p['name']}*\n"
            f"👕 Size: Any Size Available\n"
            f"💰 Price: {p['price']}\n\n"
            f"🛒 [BUY NOW]({p['url']})"
        )

        await self.bot.send_photo(
            chat_id=self.chat_id,
            photo=p["image"],
            caption=caption,
            parse_mode=ParseMode.MARKDOWN
        )

    # ---------------- SEND SUMMARY ----------------
    async def send_summary(self, total):
        msg = (
            f"📊 *MEN SHEIN VERSE STOCK SUMMARY*\n\n"
            f"👕 Total MEN Products Available: *{total}*\n"
            f"🕒 Updated: {datetime.now().strftime('%d %b %Y, %I:%M %p')}"
        )

        await self.bot.send_message(
            chat_id=self.chat_id,
            text=msg,
            parse_mode=ParseMode.MARKDOWN
        )

    # ---------------- CHECK STOCK ----------------
    async def check_stock(self):
        total_products = 0

        for url in self.urls:
            html = await self.fetch(url)
            if not html:
                continue

            products = self.extract_products(html)
            total_products += len(products)

            for p in products:
                if p["id"] not in self.seen_products:
                    self.seen_products.add(p["id"])
                    await self.send_alert(p)
                    logger.info(f"NEW MEN ITEM: {p['name']}")

        # send summary only if count changes
        if total_products != self.last_summary_count and total_products > 0:
            await self.send_summary(total_products)
            self.last_summary_count = total_products

    # ---------------- START ----------------
    async def start(self):
        await self.bot.send_message(
            chat_id=self.chat_id,
            text="🚀 *MEN SHEIN VERSE BOT STARTED*\nAlerts + Stock Summary Enabled 📊",
            parse_mode=ParseMode.MARKDOWN
        )

        while True:
            try:
                await self.check_stock()
                await asyncio.sleep(15)
            except Exception as e:
                logger.error(e)
                await asyncio.sleep(10)

# ---------------- MAIN ----------------
if __name__ == "__main__":
    bot = SheinVerseBot()
    asyncio.run(bot.start())
