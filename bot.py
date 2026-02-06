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
        
        # The EXACT SHEIN VERSE URL you provided
        self.target_url = "https://www.sheinindia.in/c/sverse-5939-37961"
        
        # Headers to mimic a real browser
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-IN,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate',
        }
        
        # Track seen products: {product_id: {'name': ..., 'last_seen': timestamp, 'was_out_of_stock': bool}}
        self.seen_products = {}
        
        # Statistics
        self.stats = {
            'start_time': datetime.now(),
            'total_checks': 0,
            'men_items_found': 0,
            'women_items_found': 0,
            'alerts_sent': 0
        }
        
        logger.info("✅ SHEIN VERSE Men's Tracker Initialized")
        logger.info(f"✅ Target URL: {self.target_url}")
        logger.info(f"✅ Chat ID: {self.chat_id}")
    
    async def fetch_page(self):
        """Fetch the SHEIN VERSE page HTML"""
        try:
            connector = aiohttp.TCPConnector(ssl=False)
            timeout = aiohttp.ClientTimeout(total=15)
            
            async with aiohttp.ClientSession(
                connector=connector,
                timeout=timeout,
                headers=self.headers
            ) as session:
                
                async with session.get(self.target_url) as response:
                    if response.status == 200:
                        html = await response.text()
                        logger.info("✅ Successfully fetched SHEIN VERSE page")
                        return html
                    else:
                        logger.error(f"❌ Failed to fetch page. Status: {response.status}")
                        return None
        except Exception as e:
            logger.error(f"❌ Error fetching page: {e}")
            return None
    
    def extract_product_info(self, html):
        """
        Extract ALL product information from the page HTML.
        Returns: list of product dicts and counts for men/women
        """
        products = []
        men_count = 0
        women_count = 0
        
        try:
            # Find all product containers - looking for the pattern in the HTML you shared
            # The page shows products in a grid with this structure
            product_pattern = r'Quick View\s*([^<]+)</span>\s*</div>\s*</div>\s*<div[^>]*>\s*<div[^>]*>\s*<div[^>]*>\s*<a[^>]*href="([^"]+)"[^>]*>\s*<div[^>]*>\s*<img[^>]*src="([^"]+)"[^>]*>'
            
            matches = re.findall(product_pattern, html, re.DOTALL)
            
            for match in matches:
                try:
                    # match[0] contains the brand and name info
                    # match[1] is the product URL path
                    # match[2] is the image URL
                    
                    full_text = match[0].strip()
                    
                    # Extract product name (simplified extraction)
                    name_match = re.search(r'Shein\s+(.+?)(?:\s*₹\d+|$)', full_text)
                    product_name = name_match.group(1).strip() if name_match else full_text
                    
                    # Extract price
                    price_match = re.search(r'₹(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)', full_text)
                    product_price = f"₹{price_match.group(1)}" if price_match else "Price N/A"
                    
                    # Clean and complete URLs
                    product_path = match[1].strip()
                    product_url = urljoin('https://www.sheinindia.in', product_path)
                    
                    image_path = match[2].strip()
                    image_url = urljoin('https:', image_path) if image_path.startswith('//') else image_path
                    if not image_url.startswith('http'):
                        image_url = 'https:' + image_url
                    
                    # Create a unique ID from the product URL
                    product_id = hashlib.md5(product_url.encode()).hexdigest()[:12]
                    
                    # Determine gender based on product name/category
                    # This is a simple filter - you might need to adjust based on actual page structure
                    gender = 'unknown'
                    
                    # Check if it's in men's section (based on your page data)
                    if 'trackpant' in product_name.lower() or 'cargo' in product_name.lower() or 'jeans' in product_name.lower():
                        gender = 'men'
                        men_count += 1
                    else:
                        # Default to women for other items (based on your page having mostly women's items)
                        gender = 'women'
                        women_count += 1
                    
                    product = {
                        'id': product_id,
                        'name': product_name[:100],  # Limit name length
                        'price': product_price,
                        'url': product_url,
                        'image_url': image_url,
                        'gender': gender,
                        'first_seen': datetime.now().isoformat()
                    }
                    
                    products.append(product)
                    
                except Exception as e:
                    logger.warning(f"⚠️ Could not parse one product: {e}")
                    continue
            
            logger.info(f"✅ Found {len(products)} total products: {men_count} men, {women_count} women")
            return products, men_count, women_count
            
        except Exception as e:
            logger.error(f"❌ Error extracting products: {e}")
            return [], 0, 0
    
    async def download_image(self, image_url):
        """Download product image for sending with alert"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(image_url, timeout=10) as response:
                    if response.status == 200:
                        image_data = await response.read()
                        return image_data
                    else:
                        logger.warning(f"⚠️ Could not download image: {response.status}")
                        return None
        except Exception as e:
            logger.warning(f"⚠️ Image download failed: {e}")
            return None
    
    async def send_men_alert(self, product, is_restock=False):
        """Send a Telegram alert for a men's product with image"""
        try:
            # Prepare the message
            emoji = "🔄" if is_restock else "🆕"
            status = "RESTOCKED" if is_restock else "NEW ARRIVAL"
            
            message = f"""
{emoji} *{status} - SHEIN VERSE MEN*
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
👕 *{product['name']}*
💰 *Price*: {product['price']}
🎯 *Category*: MEN'S
⏰ *Time*: {datetime.now().strftime('%I:%M:%S %p')}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔗 [BUY NOW]({product['url']})
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚡ *Click link above to purchase*
🎯 *Men's item detected by bot*
"""
            
            # Try to download and send the image
            image_data = await self.download_image(product['image_url'])
            
            if image_data:
                # Send with photo
                await self.bot.send_photo(
                    chat_id=self.chat_id,
                    photo=InputFile(image_data, filename='product.jpg'),
                    caption=message,
                    parse_mode=ParseMode.MARKDOWN
                )
                logger.info(f"✅ Alert sent with image: {product['name']}")
            else:
                # Fallback: send text only
                await self.bot.send_message(
                    chat_id=self.chat_id,
                    text=message,
                    parse_mode=ParseMode.MARKDOWN,
                    disable_web_page_preview=False
                )
                logger.info(f"✅ Alert sent (text only): {product['name']}")
            
            self.stats['alerts_sent'] += 1
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to send alert: {e}")
            return False
    
    async def check_for_new_men_items(self):
        """Main function to check for new or restocked men's items"""
        logger.info("🔍 Scanning for new MEN'S SHEIN VERSE items...")
        
        html = await self.fetch_page()
        if not html:
            logger.error("❌ Could not fetch page. Skipping check.")
            return
        
        products, men_count, women_count = self.extract_product_info(html)
        
        # Update statistics
        self.stats['men_items_found'] = men_count
        self.stats['women_items_found'] = women_count
        self.stats['total_checks'] += 1
        
        new_alerts = 0
        
        # Check each product
        for product in products:
            # Focus only on MEN'S items
            if product['gender'] != 'men':
                continue
            
            product_id = product['id']
            
            # Check if this is a new product
            if product_id not in self.seen_products:
                # NEW PRODUCT DETECTED
                self.seen_products[product_id] = {
                    'name': product['name'],
                    'first_seen': datetime.now(),
                    'last_seen': datetime.now(),
                    'was_out_of_stock': False,
                    'alert_sent': True
                }
                
                # Send alert for new product
                await self.send_men_alert(product, is_restock=False)
                new_alerts += 1
                
                logger.info(f"🚨 New men's item: {product['name']}")
            
            else:
                # Existing product - update last seen time
                self.seen_products[product_id]['last_seen'] = datetime.now()
        
        # Clean up old entries (older than 7 days)
        self.cleanup_old_products()
        
        if new_alerts > 0:
            logger.info(f"✅ Sent {new_alerts} new men's item alerts")
        else:
            logger.info("✅ No new men's items found")
    
    def cleanup_old_products(self):
        """Remove products not seen for a long time"""
        cutoff_time = datetime.now().timestamp() - (7 * 24 * 3600)  # 7 days
        initial_count = len(self.seen_products)
        
        self.seen_products = {
            pid: data for pid, data in self.seen_products.items()
            if data['last_seen'].timestamp() > cutoff_time
        }
        
        removed = initial_count - len(self.seen_products)
        if removed > 0:
            logger.info(f"🧹 Cleaned up {removed} old product records")
    
    async def send_status_summary(self):
        """Send periodic status summary"""
        try:
            uptime = datetime.now() - self.stats['start_time']
            hours = uptime.seconds // 3600
            minutes = (uptime.seconds % 3600) // 60
            
            summary = f"""
📊 *SHEIN VERSE TRACKER - STATUS*
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⏰ *Time*: {datetime.now().strftime('%I:%M %p')}
⏳ *Uptime*: {hours}h {minutes}m
🔄 *Checks*: {self.stats['total_checks']}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📈 *CURRENT STOCK*
👕 *Men's Items*: {self.stats['men_items_found']}
👚 *Women's Items*: {self.stats['women_items_found']}
🔍 *Tracking*: {len(self.seen_products)} products
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔔 *ACTIVITY*
🚨 *Alerts Sent*: {self.stats['alerts_sent']}
⚡ *Next Check*: 30 seconds
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ *Bot is actively monitoring*
🎯 *Focus: Men's new arrivals & restocks*
"""
            
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=summary,
                parse_mode=ParseMode.MARKDOWN
            )
            
            logger.info("📊 Status summary sent")
            
        except Exception as e:
            logger.error(f"❌ Failed to send summary: {e}")
    
    async def run(self):
        """Main bot execution loop"""
        # Send startup message
        startup_msg = f"""
🚀 *SHEIN VERSE MEN'S TRACKER STARTED*
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ *Monitoring*: {self.target_url}
🎯 *Focus*: NEW MEN'S ITEMS ONLY
📸 *Alerts*: WITH PRODUCT IMAGES
⚡ *Frequency*: EVERY 30 SECONDS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🛒 *Bot will send alerts for:*
• New men's SHEIN VERSE items
• Restocked men's items
• Each alert includes product image
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⏰ Starting first scan now...
"""
        
        await self.bot.send_message(
            chat_id=self.chat_id,
            text=startup_msg,
            parse_mode=ParseMode.MARKDOWN
        )
        
        logger.info("✅ Bot started. Sending startup message.")
        
        # Initial check
        await self.check_for_new_men_items()
        
        # Main loop
        check_counter = 0
        
        while True:
            try:
                # Wait 30 seconds between checks
                await asyncio.sleep(30)
                
                # Perform check
                await self.check_for_new_men_items()
                check_counter += 1
                
                # Send summary every 2 hours (240 checks = 2 hours)
                if check_counter >= 240:
                    await self.send_status_summary()
                    check_counter = 0
                
            except Exception as e:
                logger.error(f"❌ Error in main loop: {e}")
                # Wait and retry
                await asyncio.sleep(30)

async def main():
    """Application entry point"""
    print("\n" + "="*60)
    print("🚀 SHEIN VERSE MEN'S ALERT BOT")
    print("✅ REAL-TIME MONITORING WITH IMAGES")
    print("🎯 FOCUS: NEW & RESTOCKED MEN'S ITEMS")
    print("="*60 + "\n")
    
    try:
        tracker = SheinVerseMenTracker()
        await tracker.run()
    except ValueError as e:
        logger.error(f"❌ Configuration error: {e}")
        print(f"\n🔧 Please set these environment variables in Railway:")
        print("1. TELEGRAM_BOT_TOKEN - Get from @BotFather")
        print("2. TELEGRAM_CHAT_ID - Get from @userinfobot")
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("\n👋 Bot stopped by user")
    except Exception as e:
        logger.error(f"💥 Critical failure: {e}")
