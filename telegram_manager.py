"""
Telegram alert manager
"""

import asyncio
import aiohttp
import logging
from datetime import datetime
import os
from typing import Dict, List

from config import Config

logger = logging.getLogger(__name__)

class TelegramManager:
    def __init__(self):
        self.token = Config.TELEGRAM_BOT_TOKEN
        self.chat_id = Config.TELEGRAM_CHAT_ID
        self.base_url = f"https://api.telegram.org/bot{self.token}"
        
    async def test_connection(self) -> bool:
        """Test Telegram connection"""
        if not self.token or not self.chat_id:
            logger.error("Telegram credentials missing")
            return False
        
        url = f"{self.base_url}/getMe"
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=10) as response:
                    if response.status == 200:
                        logger.info("✅ Telegram connection successful")
                        return True
                    else:
                        logger.error(f"Telegram error: {response.status}")
                        return False
        except Exception as e:
            logger.error(f"Telegram connection failed: {str(e)}")
            return False
    
    async def send_message(self, text: str, parse_mode: str = "HTML") -> bool:
        """Send message to Telegram"""
        if not self.token or not self.chat_id:
            logger.error("Cannot send: Telegram not configured")
            return False
        
        url = f"{self.base_url}/sendMessage"
        
        payload = {
            'chat_id': self.chat_id,
            'text': text,
            'parse_mode': parse_mode,
            'disable_web_page_preview': False
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, timeout=10) as response:
                    if response.status == 200:
                        return True
                    else:
                        error = await response.text()
                        logger.error(f"Telegram send error: {error}")
                        return False
        except Exception as e:
            logger.error(f"Send message error: {str(e)}")
            return False
    
    async def send_product_alert(self, product: Dict, is_new: bool = True):
        """Send product alert with all details"""
        
        # Create app deep link
        app_link = self._create_app_link(product['url'])
        
        # Prepare size info
        size_info = product.get('size_details', '')
        if not size_info and product.get('available_sizes'):
            size_info = "\n".join([f"• {size}" for size in product['available_sizes']])
        
        if not size_info:
            size_info = "Check product page for sizes"
        
        # Determine alert type
        if is_new:
            alert_type = "🆕 NEW PRODUCT"
            emoji = "🔥"
        else:
            alert_type = "🔄 RESTOCK"
            emoji = "⚡"
        
        # Format message
        message = f"""
{emoji} <b>{alert_type}</b> {emoji}

🏷️ <b>{product['name']}</b>

💰 <b>Price:</b> ₹{product['price']}
📏 <b>Available Sizes:</b>
{size_info}

📦 <b>Total Stock:</b> {product.get('total_stock', 'N/A')}

🛒 <b>BUY NOW:</b> <a href="{app_link}">Open in SHEIN App</a>
🔗 <b>Web Link:</b> <a href="{product['url']}">Click Here</a>

⏰ <i>{datetime.now().strftime('%H:%M:%S')}</i>

⚡ <b>Be quick! Limited stock available!</b>
"""
        
        # Send message
        success = await self.send_message(message)
        
        # Send image if available
        if success and product.get('image'):
            await self.send_photo(product['image'], product['name'][:50])
        
        return success
    
    async def send_photo(self, photo_url: str, caption: str = "") -> bool:
        """Send photo to Telegram"""
        url = f"{self.base_url}/sendPhoto"
        
        payload = {
            'chat_id': self.chat_id,
            'photo': photo_url,
            'caption': caption[:100],
            'parse_mode': 'HTML'
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, timeout=10) as response:
                    return response.status == 200
        except Exception as e:
            logger.error(f"Send photo error: {str(e)}")
            return False
    
    def _create_app_link(self, web_url: str) -> str:
        """Create deep link for SHEIN app"""
        import re
        
        # Extract product ID
        match = re.search(r'p-(\d+)\.html', web_url)
        if match:
            product_id = match.group(1)
            return f"shein://product?id={product_id}"
        
        # Fallback to web URL
        return web_url
    
    async def send_startup_message(self):
        """Send bot startup message"""
        message = f"""
🤖 <b>SHEIN VERSE BOT ACTIVATED</b> 🤖

✅ <b>Status:</b> Running on Railway
✅ <b>Tracking:</b> Shein Verse - Men's Section
✅ <b>Anti-Detection:</b> Active
✅ <b>Alerts:</b> Enabled with images & links

⚡ <b>You will receive:</b>
• New product alerts
• Restock notifications  
• Size availability
• Direct app links
• Product images

🛡️ <b>Protection:</b> Advanced anti-blocking
🕒 <b>Check Interval:</b> {Config.CHECK_INTERVAL_MINUTES} minutes

🎯 <i>Ready to monitor stock...</i>
"""
        
        await self.send_message(message)
    
    async def send_summary(self, stats: Dict):
        """Send periodic summary"""
        message = f"""
📊 <b>SHEIN VERSE - STATUS SUMMARY</b>

📅 {datetime.now().strftime('%d %b %Y %H:%M')}

📦 <b>Total Products:</b> {stats.get('total_products', 0)}
🆕 <b>New Today:</b> {stats.get('new_today', 0)}
🔄 <b>Restocks Today:</b> {stats.get('restocks_today', 0)}
🚨 <b>Alerts Sent:</b> {stats.get('alerts_sent', 0)}

⏰ <b>Last Check:</b> {stats.get('last_check', 'N/A')}
✅ <b>Bot Status:</b> Running
"""
        
        await self.send_message(message)
    
    async def send_error_alert(self, error: str):
        """Send error alert"""
        message = f"""
⚠️ <b>BOT ERROR DETECTED</b>

❌ <b>Error:</b> {error[:100]}

🔧 <b>Action:</b> Bot will attempt recovery
⏰ <b>Time:</b> {datetime.now().strftime('%H:%M:%S')}
"""
        
        await self.send_message(message)
