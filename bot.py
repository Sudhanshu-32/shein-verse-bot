import os
import asyncio
import aiohttp
from datetime import datetime
import logging
import re
from telegram import Bot, InputFile
from telegram.constants import ParseMode
from urllib.parse import urljoin
import hashlib

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

class SheinVerseMenTracker:
    def __init__(self):
        # Telegram Setup
        self.bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
        self.chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()
        
        if not self.bot_token or not self.chat_id:
            logger.error("❌ Telegram credentials missing!")
            raise ValueError("Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID")
        
        self.bot = Bot(token=self.bot_token)
        
        # SHEIN VERSE URL
        self.target_url = "https://www.sheinindia.in/c/sverse-5939-37961"
        
        # Headers
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        }
        
        # Track products
        self.seen_products = {}
        self.stats = {
            'start_time': datetime.now(),
            'total_checks': 0,
            'men_count': 0,
            'women_count': 0,
            'alerts_sent': 0
        }
        
        logger.info("✅ Bot initialized")
    
    async def fetch_page(self):
        """Fetch SHEIN page"""
        try:
            connector = aiohttp.TCPConnector(ssl=False)
            timeout = aiohttp.ClientTimeout(total=10)
            
            async with aiohttp.ClientSession(
                connector=connector,
                timeout=timeout,
                headers=self.headers
            ) as session:
                
                async with session.get(self.target_url) as response:
                    if response.status == 200:
                        return await response.text()
                    return None
        except Exception as e:
            logger.error(f"❌ Fetch error: {e}")
            return None
    
    def extract_products(self, html):
        """Extract products from page"""
        products = []
        try:
            # Find product listings
            product_pattern = r'Quick View\s*([^<]+)</span>.*?href="([^"]+)".*?src="([^"]+)"'
            matches = re.findall(product_pattern, html, re.DOTALL)
            
            for match in matches[:50]:  # First 50 only
                try:
                    full_text = match[0].strip()
                    
                    # Get product name
                    name_match = re.search(r'Shein\s+(.+?)(?:\s*₹\d+|$)', full_text)
                    product_name = name_match.group(1).strip() if name_match else full_text[:50]
                    
                    # Get price
                    price_match = re.search(r'₹(\d+)', full_text)
                    product_price = f"₹{price_match.group(1)}" if price_match else "₹---"
                    
                    # Build URLs
                    product_path = match[1].strip()
                    product_url = urljoin('https://www.sheinindia.in', product_path)
                    
                    image_path = match[2].strip()
                    image_url = urljoin('https:', image_path) if image_path.startswith('//') else image_path
                    
                    # Create ID
                    product_id = hashlib.md5(product_url.encode()).hexdigest()[:10]
                    
                    # Simple gender detection
                    gender = 'men' if any(word in product_name.lower() for word in 
                                       ['track', 'cargo', 'jeans', 'tshirt', 'shirt', 'hoodie', 'sweatshirt']) else 'women'
                    
                    products.append({
                        'id': product_id,
                        'name': product_name[:80],
                        'price': product_price,
                        'url': product_url,
                        'image': image_url,
                        'gender': gender,
                        'time': datetime.now()
                    })
                    
                except:
                    continue
            
            # Count by gender
            men_count = sum(1 for p in products if p['gender'] == 'men')
            women_count = len(products) - men_count
            
            return products, men_count, women_count
            
        except Exception as e:
            logger.error(f"❌ Extract error: {e}")
            return [], 0, 0
    
    async def download_image(self, image_url):
        """Download product image"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(image_url, timeout=5) as response:
                    if response.status == 200:
                        return await response.read()
        except:
            return None
    
    async def send_alert(self, product, is_new=True):
        """Send alert with image"""
        try:
            emoji = "🆕" if is_new else "🔄"
            status = "NEW" if is_new else "RESTOCK"
            
            message = f"""
{emoji} *{status} - SHEIN VERSE MEN*
━━━━━━━━━━━━━━━━
👕 {product['name']}
💰 {product['price']}
⏰ {product['time'].strftime('%I:%M %p')}
━━━━━━━━━━━━━━━━
🔗 [BUY NOW]({product['url']})
"""
            
            # Try with image
            image_data = await self.download_image(product['image'])
            if image_data:
                await self.bot.send_photo(
                    chat_id=self.chat_id,
                    photo=InputFile(image_data, 'product.jpg'),
                    caption=message,
                    parse_mode=ParseMode.MARKDOWN
                )
            else:
                await self.bot.send_message(
                    chat_id=self.chat_id,
                    text=message,
                    parse_mode=ParseMode.MARKDOWN,
                    disable_web_page_preview=False
                )
            
            self.stats['alerts_sent'] += 1
            logger.info(f"✅ Alert: {product['name'][:30]}")
            
        except Exception as e:
            logger.error(f"❌ Alert error: {e}")
    
    async def send_summary(self, is_startup=False):
        """Send summary with current stock"""
        try:
            # Get fresh data for current stock
            html = await self.fetch_page()
            if html:
                _, men_count, women_count = self.extract_products(html)
                self.stats['men_count'] = men_count
                self.stats['women_count'] = women_count
            
            uptime = datetime.now() - self.stats['start_time']
            hours = uptime.seconds // 3600
            minutes = (uptime.seconds % 3600) // 60
            
            if is_startup:
                title = "📊 SHEIN VERSE - CURRENT STOCK"
                extra = "✅ Bot Started & Monitoring"
            else:
                title = f"📊 SHEIN VERSE SUMMARY ({hours}h {minutes}m)"
                extra = f"🔄 Next in 2h | ✅ Active"
            
            summary = f"""
{title}
━━━━━━━━━━━━━━━━
⏰ {datetime.now().strftime('%I:%M %p')}
━━━━━━━━━━━━━━━━
👕 MEN'S: {self.stats['men_count']}
👚 WOMEN'S: {self.stats['women_count']}
🔗 TOTAL: {self.stats['men_count'] + self.stats['women_count']}
━━━━━━━━━━━━━━━━
🔔 Alerts: {self.stats['alerts_sent']}
⚡ Checks: {self.stats['total_checks']}
━━━━━━━━━━━━━━━━
{extra}
"""
            
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=summary,
                parse_mode=ParseMode.MARKDOWN
            )
            
            logger.info("📊 Summary sent")
            
        except Exception as e:
            logger.error(f"❌ Summary error: {e}")
    
    async def check_stock(self):
        """Check for new stock"""
        try:
            logger.info("🔍 Checking stock...")
            
            html = await self.fetch_page()
            if not html:
                return
            
            products, men_count, women_count = self.extract_products(html)
            
            # Update stats with current counts
            self.stats['men_count'] = men_count
            self.stats['women_count'] = women_count
            self.stats['total_checks'] += 1
            
            # Check for new men's products
            for product in products:
                if product['gender'] != 'men':
                    continue
                
                product_id = product['id']
                
                if product_id not in self.seen_products:
                    await self.send_alert(product, is_new=True)
                    self.seen_products[product_id] = product
            
            logger.info(f"✅ Men: {men_count}, Women: {women_count}")
            
        except Exception as e:
            logger.error(f"❌ Check error: {e}")
    
    async def run(self):
        """Main bot loop"""
        # 1. SIMPLE STARTUP MESSAGE
        await self.bot.send_message(
            chat_id=self.chat_id,
            text="✅ SHEIN VERSE Bot Started",
            parse_mode=ParseMode.MARKDOWN
        )
        
        logger.info("✅ Bot started")
        
        # 2. IMMEDIATELY SEND FIRST SUMMARY (Current stock)
        await self.send_summary(is_startup=True)
        
        # 3. FIRST STOCK CHECK
        await self.check_stock()
        
        # Main loop
        check_counter = 0
        
        while True:
            try:
                await asyncio.sleep(30)  # Every 30 seconds
                
                await self.check_stock()
                check_counter += 1
                
                # Every 2 hours send summary
                if check_counter >= 240:  # 30s * 240 = 2 hours
                    await self.send_summary(is_startup=False)
                    check_counter = 0
                
            except Exception as e:
                logger.error(f"❌ Loop error: {e}")
                await asyncio.sleep(30)

async def main():
    """Entry point"""
    print("\n🚀 SHEIN VERSE BOT")
    print("📊 Summary at Start + Every 2h")
    
    try:
        tracker = SheinVerseMenTracker()
        await tracker.run()
    except ValueError as e:
        logger.error(f"❌ Config: {e}")
    except Exception as e:
        logger.error(f"❌ Error: {e}")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("👋 Bot stopped")
    except Exception as e:
        logger.error(f"💥 Crash: {e}")
