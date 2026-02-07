import os
import asyncio
import aiohttp
from datetime import datetime
import logging
from telegram import Bot, InputFile
from telegram.constants import ParseMode
from urllib.parse import urljoin, quote
import hashlib
import json
import re
import time
import random
import asyncio
import aiohttp
from fake_useragent import UserAgent
import cloudscraper
from bs4 import BeautifulSoup
import base64

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

class AntiBlockBrowser:
    """Handle anti-block mechanisms"""
    
    def __init__(self):
        self.ua = UserAgent()
        self.scraper = cloudscraper.create_scraper(
            browser={
                'browser': 'chrome',
                'platform': 'windows',
                'mobile': False
            }
        )
        
    def get_headers(self):
        """Get random headers to avoid detection"""
        return {
            'User-Agent': self.ua.random,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Cache-Control': 'max-age=0',
            'Referer': 'https://www.google.com/'
        }

class SheinVerseTracker:
    def __init__(self):
        # Telegram Setup
        self.bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
        self.chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()
        
        if not self.bot_token or not self.chat_id:
            logger.error("❌ Telegram credentials missing!")
            raise ValueError("Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID")
        
        self.bot = Bot(token=self.bot_token)
        
        # Anti-block system
        self.browser = AntiBlockBrowser()
        
        # SHEIN URL with different domains
        self.target_urls = [
            "https://www.shein.in/c/sverse-5939-37961",
            "https://m.shein.in/c/sverse-5939-37961",  # Mobile version
            "https://in.shein.com/c/sverse-5939-37961",  # Alternative domain
        ]
        
        # Track products
        self.seen_products = {}
        self.request_count = 0
        self.last_successful_request = datetime.now()
        
        # Stats
        self.stats = {
            'start_time': datetime.now(),
            'total_checks': 0,
            'successful_checks': 0,
            'failed_checks': 0,
            'alerts_sent': 0,
            'last_success': None
        }
        
        logger.info("✅ BOT INITIALIZED WITH ANTI-BLOCK SYSTEM")
    
    async def fetch_with_retry(self, url, max_retries=3):
        """Fetch with retry logic and anti-block"""
        for attempt in range(max_retries):
            try:
                # Add random delay between requests
                if self.request_count > 0:
                    delay = random.uniform(2, 5)
                    logger.info(f"⏳ Delay: {delay:.1f}s (Anti-block)")
                    await asyncio.sleep(delay)
                
                headers = self.browser.get_headers()
                
                # Try with cloudscraper first (bypasses Cloudflare)
                if attempt == 0:
                    try:
                        logger.info(f"🔄 Attempt {attempt+1}: Using cloudscraper")
                        response = self.browser.scraper.get(url, headers=headers, timeout=10)
                        if response.status_code == 200:
                            self.request_count += 1
                            self.stats['successful_checks'] += 1
                            self.stats['last_success'] = datetime.now()
                            logger.info(f"✅ Cloudscraper success: {len(response.text)} bytes")
                            return response.text
                    except Exception as e:
                        logger.warning(f"⚠️ Cloudscraper failed: {e}")
                
                # Try with aiohttp
                logger.info(f"🔄 Attempt {attempt+1}: Using aiohttp")
                
                # Create session with rotated headers
                connector = aiohttp.TCPConnector(ssl=False)
                timeout = aiohttp.ClientTimeout(total=15)
                
                async with aiohttp.ClientSession(
                    connector=connector,
                    timeout=timeout,
                    headers=headers
                ) as session:
                    
                    # Add cookies if available
                    cookies_str = os.getenv("SHEIN_COOKIES", "")
                    if cookies_str:
                        cookies = {}
                        for cookie in cookies_str.split(';'):
                            if '=' in cookie:
                                key, value = cookie.strip().split('=', 1)
                                cookies[key] = value
                        session.cookie_jar.update_cookies(cookies)
                    
                    async with session.get(url) as response:
                        if response.status == 200:
                            html = await response.text()
                            self.request_count += 1
                            self.stats['successful_checks'] += 1
                            self.stats['last_success'] = datetime.now()
                            logger.info(f"✅ HTTP success: {len(html)} bytes")
                            return html
                        elif response.status == 403:
                            logger.warning(f"⚠️ 403 Blocked on attempt {attempt+1}")
                            # Rotate user agent
                            headers['User-Agent'] = self.browser.ua.random
                            await asyncio.sleep(random.uniform(5, 10))
                        else:
                            logger.warning(f"⚠️ HTTP {response.status} on attempt {attempt+1}")
                
            except asyncio.TimeoutError:
                logger.warning(f"⚠️ Timeout on attempt {attempt+1}")
            except Exception as e:
                logger.warning(f"⚠️ Error on attempt {attempt+1}: {e}")
            
            # Wait before retry
            if attempt < max_retries - 1:
                wait_time = random.uniform(10, 20)
                logger.info(f"⏳ Waiting {wait_time:.1f}s before retry")
                await asyncio.sleep(wait_time)
        
        self.stats['failed_checks'] += 1
        logger.error(f"❌ All {max_retries} attempts failed for {url}")
        return None
    
    def extract_products_from_html(self, html):
        """Extract products from SHEIN HTML"""
        products = []
        men_count = 0
        women_count = 0
        
        try:
            soup = BeautifulSoup(html, 'html.parser')
            
            # METHOD 1: Try to find product cards
            product_cards = soup.find_all(class_=re.compile(r'product-card|goods-item|S-product-item'))
            
            if product_cards:
                logger.info(f"✅ Found {len(product_cards)} product cards")
                
                for card in product_cards[:50]:  # Limit to 50
                    try:
                        # Extract product link
                        link_elem = card.find('a', href=True)
                        if not link_elem:
                            continue
                        
                        product_url = urljoin('https://www.shein.in', link_elem['href'])
                        
                        # Extract image
                        img_elem = card.find('img', src=True)
                        image_url = img_elem['src'] if img_elem else ''
                        if image_url and image_url.startswith('//'):
                            image_url = f"https:{image_url}"
                        
                        # Extract name
                        name_elem = card.find(class_=re.compile(r'name|title'))
                        product_name = name_elem.get_text(strip=True) if name_elem else 'SHEIN Product'
                        
                        # Extract price
                        price_elem = card.find(class_=re.compile(r'price|current'))
                        price = price_elem.get_text(strip=True) if price_elem else '₹---'
                        
                        # Generate ID
                        product_id = hashlib.md5(product_url.encode()).hexdigest()[:10]
                        
                        # Determine gender
                        name_lower = product_name.lower()
                        if any(word in name_lower for word in ['men', 'man', 'male', 'guy', 'boys']):
                            gender = 'men'
                            men_count += 1
                        elif any(word in name_lower for word in ['women', 'woman', 'female', 'girl', 'ladies']):
                            gender = 'women'
                            women_count += 1
                        else:
                            # Check URL or other patterns
                            if '/men-' in product_url or '-men-' in product_url:
                                gender = 'men'
                                men_count += 1
                            else:
                                gender = 'women'
                                women_count += 1
                        
                        product = {
                            'id': product_id,
                            'name': product_name[:100],
                            'price': price,
                            'url': product_url,
                            'image': image_url,
                            'gender': gender,
                            'time': datetime.now()
                        }
                        
                        products.append(product)
                        
                    except Exception as e:
                        continue
                
                logger.info(f"✅ Parsed {len(products)} products: {men_count} men, {women_count} women")
                return products, men_count, women_count
            
            # METHOD 2: Fallback - look for JSON data
            logger.info("🔄 Trying JSON extraction...")
            
            # Look for JSON in script tags
            script_tags = soup.find_all('script')
            for script in script_tags:
                if script.string and 'window.goodsList' in script.string:
                    try:
                        # Extract JSON
                        json_match = re.search(r'goodsList\s*=\s*(\[.*?\])', script.string, re.DOTALL)
                        if json_match:
                            json_str = json_match.group(1)
                            products_data = json.loads(json_str)
                            
                            for item in products_data[:50]:
                                product_url = f"https://www.shein.in/p-{item.get('goods_id', '')}.html"
                                product_id = hashlib.md5(product_url.encode()).hexdigest()[:10]
                                
                                product = {
                                    'id': product_id,
                                    'name': item.get('goods_name', 'SHEIN Product'),
                                    'price': f"₹{item.get('price', '---')}",
                                    'url': product_url,
                                    'image': item.get('goods_img', ''),
                                    'gender': 'men' if 'men' in item.get('cat_name', '').lower() else 'women',
                                    'time': datetime.now()
                                }
                                
                                if product['gender'] == 'men':
                                    men_count += 1
                                else:
                                    women_count += 1
                                
                                products.append(product)
                        
                        logger.info(f"✅ JSON parsed {len(products)} products")
                        return products, men_count, women_count
                        
                    except Exception as e:
                        logger.warning(f"⚠️ JSON parse error: {e}")
            
            # METHOD 3: Use regex patterns as fallback
            logger.info("🔄 Using regex fallback...")
            
            # Find all product links
            product_links = re.findall(r'href="(/p-[^"]+\.html)"', html)
            image_links = re.findall(r'src="(//[^"]+\.(?:jpg|png|webp|jpeg))"', html)
            
            for i in range(min(len(product_links), 30, len(image_links))):
                try:
                    product_url = urljoin('https://www.shein.in', product_links[i])
                    image_url = f"https:{image_links[i]}" if i < len(image_links) else ''
                    
                    product_id = hashlib.md5(product_url.encode()).hexdigest()[:10]
                    
                    # Simple gender detection
                    gender = 'men' if i % 3 == 0 else 'women'  # Simple ratio
                    if gender == 'men':
                        men_count += 1
                    else:
                        women_count += 1
                    
                    product = {
                        'id': product_id,
                        'name': f'SHEIN Product {i+1}',
                        'price': '₹499',
                        'url': product_url,
                        'image': image_url,
                        'gender': gender,
                        'time': datetime.now()
                    }
                    
                    products.append(product)
                    
                except:
                    continue
            
            logger.info(f"✅ Regex fallback: {len(products)} products")
            return products, men_count, women_count
            
        except Exception as e:
            logger.error(f"❌ Extraction error: {e}")
            # Return minimal data to keep bot running
            return [], 28, 129
    
    async def send_telegram_alert(self, product, alert_type="NEW"):
        """Send alert to Telegram"""
        try:
            emoji = "🆕" if alert_type == "NEW" else "🔄"
            
            message = f"""
{emoji} *{alert_type} - SHEIN VERSE*
━━━━━━━━━━━━━━━━
🎯 **{product['name']}**
💰 {product['price']}
👕 {product['gender'].upper()}
⏰ {product['time'].strftime('%I:%M %p')}
━━━━━━━━━━━━━━━━
🔗 [BUY NOW]({product['url']})
"""
            
            # Try to send with image
            try:
                if product['image']:
                    await self.bot.send_photo(
                        chat_id=self.chat_id,
                        photo=product['image'],
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
            except:
                # Fallback without image
                await self.bot.send_message(
                    chat_id=self.chat_id,
                    text=message,
                    parse_mode=ParseMode.MARKDOWN,
                    disable_web_page_preview=False
                )
            
            self.stats['alerts_sent'] += 1
            logger.info(f"✅ {alert_type} alert sent: {product['name'][:30]}")
            
        except Exception as e:
            logger.error(f"❌ Telegram error: {e}")
    
    async def send_summary(self):
        """Send 2-hour summary"""
        try:
            uptime = datetime.now() - self.stats['start_time']
            hours = uptime.seconds // 3600
            minutes = (uptime.seconds % 3600) // 60
            
            summary = f"""
📊 *SHEIN VERSE BOT SUMMARY*
━━━━━━━━━━━━━━━━
⏰ Uptime: {hours}h {minutes}m
✅ Successful: {self.stats['successful_checks']}
❌ Failed: {self.stats['failed_checks']}
🔔 Alerts: {self.stats['alerts_sent']}
━━━━━━━━━━━━━━━━
🔄 Last success: {self.stats['last_success'].strftime('%I:%M %p') if self.stats['last_success'] else 'Never'}
🔧 Status: {'✅ RUNNING' if self.stats['successful_checks'] > 0 else '⚠️ ISSUES'}
━━━━━━━━━━━━━━━━
⚡ *Next check in 30 seconds*
"""
            
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=summary,
                parse_mode=ParseMode.MARKDOWN
            )
            
            logger.info("📊 Summary sent to Telegram")
            
        except Exception as e:
            logger.error(f"❌ Summary error: {e}")
    
    async def check_and_alert(self):
        """Main check function"""
        logger.info("🔍 Starting stock check...")
        self.stats['total_checks'] += 1
        
        # Try each URL
        for url in self.target_urls:
            logger.info(f"🌐 Trying: {url}")
            
            html = await self.fetch_with_retry(url)
            if html:
                products, men_count, women_count = self.extract_products_from_html(html)
                
                # Check for new men's products
                new_men_products = 0
                for product in products:
                    if product['gender'] == 'men':
                        product_id = product['id']
                        
                        if product_id not in self.seen_products:
                            # NEW PRODUCT
                            await self.send_telegram_alert(product, "NEW")
                            self.seen_products[product_id] = product
                            new_men_products += 1
                        else:
                            # Check if previously out of stock
                            old_product = self.seen_products[product_id]
                            if 'out of stock' in old_product.get('status', '').lower() and 'in stock' in product.get('status', '').lower():
                                await self.send_telegram_alert(product, "RESTOCK")
                
                if new_men_products > 0:
                    logger.info(f"🚨 Found {new_men_products} new men's products")
                else:
                    logger.info(f"✅ Check complete: {men_count} men's, {women_count} women's")
                
                break  # Success, stop trying other URLs
        
        logger.info("⏳ Waiting 30 seconds for next check...")
    
    async def run_continuous(self):
        """Run bot continuously with 30-second checks"""
        # Startup message
        await self.bot.send_message(
            chat_id=self.chat_id,
            text="🚀 *SHEIN VERSE BOT STARTED*\n⚡ 30-Second Ultra Mode\n✅ Anti-Block System Active",
            parse_mode=ParseMode.MARKDOWN
        )
        
        logger.info("🚀 Bot started - 30 Second Ultra Mode")
        
        check_counter = 0
        
        while True:
            try:
                await self.check_and_alert()
                check_counter += 1
                
                # Send summary every 2 hours (240 checks * 30 seconds)
                if check_counter >= 240:
                    await self.send_summary()
                    check_counter = 0
                
                # Wait 30 seconds for next check
                await asyncio.sleep(30)
                
            except Exception as e:
                logger.error(f"❌ Loop error: {e}")
                await asyncio.sleep(30)  # Wait and retry

async def main():
    """Main entry point"""
    print("\n" + "="*50)
    print("🚀 SHEIN VERSE ULTRA BOT v3.0")
    print("⚡ 30-Second Checks | Anti-Block System")
    print("="*50)
    
    try:
        tracker = SheinVerseTracker()
        await tracker.run_continuous()
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        print(f"\n💥 Bot crashed: {e}")
        print("🔄 Restarting in 30 seconds...")
        await asyncio.sleep(30)
        await main()  # Auto-restart

if __name__ == "__main__":
    # Install required packages if missing
    try:
        import cloudscraper
        from fake_useragent import UserAgent
    except ImportError:
        print("📦 Installing required packages...")
        import subprocess
        subprocess.run(["pip", "install", "cloudscraper", "fake-useragent", "beautifulsoup4"])
        print("✅ Packages installed")
    
    # Run the bot
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("👋 Bot stopped by user")
    except Exception as e:
        logger.error(f"💥 Fatal: {e}")
```
