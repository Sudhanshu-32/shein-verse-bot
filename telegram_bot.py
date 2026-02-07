"""
Telegram bot for sending alerts
"""

import aiohttp
import asyncio
import logging
from datetime import datetime
import os

logger = logging.getLogger(__name__)

class TelegramBot:
    def __init__(self):
        self.token = os.getenv('TELEGRAM_BOT_TOKEN')
        self.chat_id = os.getenv('TELEGRAM_CHAT_ID')
        self.base_url = f"https://api.telegram.org/bot{self.token}"
        
    async def test_connection(self) -> bool:
        """Test Telegram connection"""
        if not self.token or not self.chat_id:
            logger.error("Telegram credentials not set")
            return False
        
        url = f"{self.base_url}/getMe"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        logger.info("✅ Telegram connection successful")
                        return True
        except Exception as e:
            logger.error(f"Telegram connection failed: {str(e)}")
        
        return False
    
    async def send_message(self, text: str, parse_mode: str = "HTML") -> bool:
        """Send message to Telegram"""
        url = f"{self.base_url}/sendMessage"
        
        payload = {
            'chat_id': self.chat_id,
            'text': text,
            'parse_mode': parse_mode,
            'disable_web_page_preview': False
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload) as response:
                    return response.status == 200
        except Exception as e:
            logger.error(f"Send message error: {str(e)}")
            return False
    
    async def send_product_alert(self, product: Dict, is_new: bool, is_restock: bool):
        """Send product alert with all details"""
        
        # Create app deep link
        app_link = self._create_deep_link(product['url'])
        
        # Format sizes info
        sizes = product.get('sizes', {})
        sizes_text = ""
        if sizes:
            sizes_text = "📏 <b>Available Sizes:</b>\n"
            for size, qty in sizes.items():
                if qty > 0:
                    sizes_text += f"  • <code>{size}</code>: {qty} pcs\n"
        else:
            sizes_text = "📏 <b>Sizes:</b> Check product page\n"
        
        # Determine alert type
        if is_new:
            alert_type = "🆕 NEW PRODUCT"
            emoji = "🔥"
        elif is_restock:
            alert_type = "🔄 RESTOCK"
            emoji = "⚡"
        else:
            alert_type = "📦 UPDATE"
            emoji = "📢"
        
        message = f"""
{emoji} <b>{alert_type}</b> {emoji}

🏷️ <b>{product['name']}</b>

💰 <b>Price:</b> {product['price']}
{sizes_text}
📦 <b>Total Stock:</b> {product.get('total_stock', 'N/A')}

🛒 <b>BUY NOW:</b> <a href="{app_link}">Open in SHEIN App</a>
🔗 <b>Web Link:</b> <a href="{product['url']}">Click here</a>

⏰ <i>{datetime.now().strftime('%H:%M:%S')}</i>
        """
        
        # Send message
        await self.send_message(message)
        
        # Send image if available
        if product.get('image_url'):
            await self.send_photo(product['image_url'], product['name'][:50])
    
    async def send_photo(self, photo_url: str, caption: str = ""):
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
                async with session.post(url, json=payload) as response:
                    return response.status == 200
        except:
            return False
    
    def _create_deep_link(self, web_url: str) -> str:
        """Create deep link for SHEIN app"""
        import re
        
        # Extract product ID
        match = re.search(r'p-(\d+)\.html', web_url)
        if match:
            product_id = match.group(1)
            return f"shein://product?id={product_id}"
        
        return web_url
    
    async def send_startup_message(self):
        """Send startup message"""
        message = f"""
🤖 <b>SHEIN VERSE BOT STARTED</b> 🤖

✅ <b>Status:</b> Running on Railway
✅ <b>Tracking:</b> Men's Section Only
✅ <b>Anti-Detection:</b> Active
✅ <b>Alerts:</b> Enabled

⚡ <b>You will receive:</b>
• New product alerts
• Restock notifications
• Size & quantity details
• Direct app links

🕒 <i>Started: {datetime.now().strftime('%H:%M:%S')}</i>
        """
        
        await self.send_message(message)
