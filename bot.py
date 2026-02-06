import os
import asyncio
import aiohttp
from datetime import datetime
import logging
from telegram import Bot
from telegram.constants import ParseMode
import json

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

class SheinVerseMenBot:
    def __init__(self):
        # Telegram credentials
        self.bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
        self.chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()
        
        if not self.bot_token or not self.chat_id:
            logger.error("❌ Telegram credentials missing!")
            raise ValueError("Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID")
        
        logger.info(f"✅ Bot Token: {self.bot_token[:15]}...")
        logger.info(f"✅ Chat ID: {self.chat_id}")
        
        self.bot = Bot(token=self.bot_token)
        
        # SHEIN Verse API URLs (Men's Focus)
        self.urls = {
            "men_new": "https://www.shein.in/api/goodsList/get?cat_id=22542&page=1&page_size=60&sort=7",
            "men_all": "https://www.shein.in/api/goodsList/get?cat_id=22542&page=1&page_size=100",
            "women_all": "https://www.shein.in/api/goodsList/get?cat_id=22543&page=1&page_size=100",
        }
        
        # Cookies (Optional but better)
        self.cookies = self.parse_cookies(os.getenv("SHEIN_COOKIES", ""))
        
        # Headers
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json',
            'Referer': 'https://www.shein.in/'
        }
        
        # Tracking
        self.men_products = {}
        self.women_products = {}
        self.seen_product_ids = set()
        
        # Stats
        self.stats = {
            "start_time": datetime.now(),
            "men_count": 0,
            "women_count": 0,
            "alerts_sent": 0,
            "last_check": None
        }
        
        logger.info("✅ Bot initialized - MEN'S FOCUS MODE")
    
    def parse_cookies(self, cookie_str):
        """Parse cookies string"""
        cookies = {}
        if cookie_str:
            for item in cookie_str.strip().split(';'):
                if '=' in item:
                    key, value = item.strip().split('=', 1)
                    cookies[key] = value
        return cookies
    
    async def fetch_shein_data(self, url):
        """Fetch data from SHEIN API"""
        try:
            timeout = aiohttp.ClientTimeout(total=15)
            
            async with aiohttp.ClientSession(
                timeout=timeout,
                headers=self.headers
            ) as session:
                
                # Add cookies if available
                if self.cookies:
                    for key, value in self.cookies.items():
                        session.cookie_jar.update_cookies({key: value})
                
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        logger.info(f"✅ Fetched: {url.split('?')[0]}")
                        return data
                    else:
                        logger.warning(f"⚠️ HTTP {response.status} for {url}")
                        return None
                        
        except asyncio.TimeoutError:
            logger.error(f"⏱️ Timeout for {url}")
            return None
        except Exception as e:
            logger.error(f"❌ Fetch error: {str(e)[:100]}")
            return None
    
    async def get_real_counts(self):
        """Get ACTUAL counts from SHEIN"""
        try:
            logger.info("📊 Getting real stock counts...")
            
            # Fetch men's products
            men_data = await self.fetch_shein_data(self.urls["men_all"])
            women_data = await self.fetch_shein_data(self.urls["women_all"])
            
            men_count = 0
            women_count = 0
            
            if men_data and 'info' in men_data and 'goods' in men_data['info']:
                men_count = len(men_data['info']['goods'])
                # Store men's products for alerts
                for item in men_data['info']['goods'][:30]:  # First 30 only
                    try:
                        product_id = str(item.get('goods_id', ''))
                        if product_id and product_id not in self.seen_product_ids:
                            self.men_products[product_id] = {
                                'id': product_id,
                                'name': item.get('goods_name', 'Unknown')[:40],
                                'price': item.get('salePrice', {}).get('amount', 'N/A'),
                                'image': f"https:{item.get('goods_img', '')}" if item.get('goods_img') else None,
                                'link': f"https://www.shein.in{item.get('goods_url_path', '')}",
                                'is_new': True
                            }
                    except:
                        continue
            
            if women_data and 'info' in women_data and 'goods' in women_data['info']:
                women_count = len(women_data['info']['goods'])
            
            # Update stats
            self.stats["men_count"] = men_count
            self.stats["women_count"] = women_count
            self.stats["last_check"] = datetime.now().strftime("%H:%M:%S")
            
            logger.info(f"✅ Real counts: 👕 Men={men_count}, 👚 Women={women_count}")
            return men_count, women_count
            
        except Exception as e:
            logger.error(f"❌ Count error: {e}")
            return 0, 0
    
    async def check_new_men_products(self):
        """Check for NEW men's products only"""
        try:
            logger.info("🔍 Checking for NEW men's products...")
            
            men_new_data = await self.fetch_shein_data(self.urls["men_new"])
            
            if not men_new_data or 'info' not in men_new_data:
                return 0
            
            new_products = men_new_data['info'].get('goods', [])
            new_count = 0
            
            for item in new_products[:20]:  # Check first 20
                try:
                    product_id = str(item.get('goods_id', ''))
                    if not product_id or product_id in self.seen_product_ids:
                        continue
                    
                    # New product found!
                    product_name = item.get('goods_name', 'New Product')[:50]
                    product_price = item.get('salePrice', {}).get('amount', 'N/A')
                    product_image = f"https:{item.get('goods_img', '')}" if item.get('goods_img') else None
                    product_link = f"https://www.shein.in{item.get('goods_url_path', '')}"
                    
                    # Send URGENT alert
                    await self.send_men_alert(
                        product_name, 
                        product_price, 
                        product_link, 
                        product_image
                    )
                    
                    # Mark as seen
                    self.seen_product_ids.add(product_id)
                    new_count += 1
                    self.stats["alerts_sent"] += 1
                    
                    logger.info(f"🚨 NEW Men's: {product_name[:30]}")
                    
                except Exception as e:
                    logger.error(f"Product error: {e}")
                    continue
            
            if new_count > 0:
                logger.info(f"✅ Found {new_count} NEW men's products")
            else:
                logger.info("✅ No new men's products")
            
            return new_count
            
        except Exception as e:
            logger.error(f"❌ New products check error: {e}")
            return 0
    
    async def send_men_alert(self, name, price, link, image_url=None):
        """Send alert for men's product"""
        try:
            message = f"""
🚨 *NEW MEN'S STOCK - SHEIN VERSE*
━━━━━━━━━━━━━━━━━━━━━━
👕 *{name}*
💰 *Price*: ₹{price}
⏰ *Time*: {datetime.now().strftime('%I:%M:%S %p')}
━━━━━━━━━━━━━━━━━━━━━━
🔗 [BUY NOW]({link})
━━━━━━━━━━━━━━━━━━━━━━
⚡ *FAST - Limited Stock!*
"""
            
            # Try with image
            if image_url:
                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.get(image_url, timeout=5) as resp:
                            if resp.status == 200:
                                image_data = await resp.read()
                                await self.bot.send_photo(
                                    chat_id=self.chat_id,
                                    photo=image_data,
                                    caption=message,
                                    parse_mode=ParseMode.MARKDOWN
                                )
                                return
                except:
                    pass
            
            # Text only
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=message,
                parse_mode=ParseMode.MARKDOWN,
                disable_web_page_preview=False
            )
            
        except Exception as e:
            logger.error(f"❌ Alert error: {e}")
    
    async def send_summary_report(self, force_update=False):
        """Send summary report with REAL counts"""
        try:
            if force_update:
                await self.get_real_counts()
            
            uptime = datetime.now() - self.stats["start_time"]
            hours = uptime.seconds // 3600
            minutes = (uptime.seconds % 3600) // 60
            
            summary = f"""
📊 *SHEIN VERSE - REAL TIME SUMMARY*
━━━━━━━━━━━━━━━━━━━━━━
⏰ *Last Check*: {self.stats["last_check"]}
⏳ *Bot Uptime*: {hours}h {minutes}m
━━━━━━━━━━━━━━━━━━━━━━
👕 *MEN'S COLLECTION*: {self.stats["men_count"]} items
👚 *WOMEN'S COLLECTION*: {self.stats["women_count"]} items
🔔 *ALERTS SENT*: {self.stats["alerts_sent"]}
━━━━━━━━━━━━━━━━━━━━━━
⚡ *Next Check*: 30 seconds
🎯 *Focus*: MEN'S NEW ARRIVALS
━━━━━━━━━━━━━━━━━━━━━━
✅ *Status*: ACTIVE & MONITORING
"""
            
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=summary,
                parse_mode=ParseMode.MARKDOWN
            )
            
            logger.info("📊 Summary report sent")
            
        except Exception as e:
            logger.error(f"❌ Summary error: {e}")
    
    async def send_startup_summary(self):
        """Send detailed startup summary"""
        try:
            # Get REAL counts first
            men_count, women_count = await self.get_real_counts()
            
            startup_msg = f"""
🚀 *SHEIN VERSE BOT ACTIVATED*
━━━━━━━━━━━━━━━━━━━━━━
✅ *Status*: MONITORING STARTED
⚡ *Speed*: 30 SECOND SCANS
🎯 *Focus*: MEN'S NEW ARRIVALS
📱 *Alerts*: IMAGE + BUY LINK
━━━━━━━━━━━━━━━━━━━━━━
📊 *CURRENT STOCK STATUS*
👕 Men's Collection: {men_count} items
👚 Women's Collection: {women_count} items
🔗 Total Products: {men_count + women_count}
━━━━━━━━━━━━━━━━━━━━━━
⚠️ *ALERTS WILL COME FOR:*
• New Men's Products
• Men's Restocks
• Limited Stock Items
━━━━━━━━━━━━━━━━━━━━━━
⏰ Next check in 30 seconds...
"""
            
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=startup_msg,
                parse_mode=ParseMode.MARKDOWN
            )
            
            logger.info("✅ Startup summary sent with REAL counts")
            
        except Exception as e:
            logger.error(f"❌ Startup error: {e}")
    
    async def run(self):
        """Main bot loop"""
        # Send startup summary with REAL counts
        await self.send_startup_summary()
        
        # Check counters
        check_counter = 0
        summary_counter = 0
        
        # Main loop
        while True:
            try:
                # Every 30 seconds: Check for NEW men's products
                new_found = await self.check_new_men_products()
                check_counter += 1
                
                # Every 5 minutes: Update real counts
                if check_counter % 10 == 0:  # 30s * 10 = 5 minutes
                    await self.get_real_counts()
                
                # Every 2 hours: Send summary
                if check_counter >= 240:  # 30s * 240 = 2 hours
                    await self.send_summary_report()
                    check_counter = 0
                    summary_counter += 1
                
                # Wait 30 seconds
                await asyncio.sleep(30)
                
            except Exception as e:
                logger.error(f"❌ Main loop error: {e}")
                await asyncio.sleep(30)  # Wait and retry

async def main():
    """Entry point"""
    print("\n" + "="*50)
    print("🚀 SHEIN VERSE MEN'S FOCUS BOT")
    print("🎯 Priority: Men's New Arrivals")
    print("⚡ Speed: 30-second checks")
    print("="*50 + "\n")
    
    try:
        bot = SheinVerseMenBot()
        await bot.run()
    except ValueError as e:
        logger.error(f"❌ Configuration error: {e}")
    except Exception as e:
        logger.error(f"❌ Startup failed: {e}")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("\n👋 Bot stopped by user")
    except Exception as e:
        logger.error(f"💥 Fatal: {e}")
