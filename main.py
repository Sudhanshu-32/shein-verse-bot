"""
Main Shein Verse Bot for Railway
"""

import asyncio
import logging
import sys
import os
from datetime import datetime, timedelta
import signal
import random

# Configure logging
logging.basicConfig(
    level=os.getenv('LOG_LEVEL', 'INFO'),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('shein_bot.log')
    ]
)
logger = logging.getLogger(__name__)

# Import modules
from config import Config
from shein_client import SheinClient
from telegram_manager import TelegramManager
from database import Database

class SheinVerseBot:
    def __init__(self):
        self.telegram = TelegramManager()
        self.db = Database()
        self.running = False
        self.consecutive_failures = 0
        self.max_failures = 5
        self.stats = {
            'checks': 0,
            'products_found': 0,
            'alerts_sent': 0,
            'start_time': datetime.now()
        }
        
    async def initialize(self):
        """Initialize bot"""
        logger.info("🚀 Initializing Shein Verse Bot...")
        
        # Test Telegram
        if not await self.telegram.test_connection():
            logger.error("❌ Telegram connection failed. Check token/chat_id.")
            return False
        
        # Send startup message
        await self.telegram.send_startup_message()
        
        # Initial scan
        logger.info("🔍 Performing initial scan...")
        success = await self.scan_products()
        
        if success:
            logger.info("✅ Bot initialized successfully")
            return True
        else:
            logger.warning("⚠️ Initial scan failed, but continuing...")
            return True  # Continue anyway
    
    async def scan_products(self):
        """Scan for new products"""
        try:
            async with SheinClient() as client:
                # Get current products
                products = await client.get_shein_verse_men()
                
                if not products:
                    logger.warning("⚠️ No products found")
                    self.consecutive_failures += 1
                    return False
                
                logger.info(f"✅ Found {len(products)} Men's products")
                
                self.stats['checks'] += 1
                self.stats['products_found'] = len(products)
                self.consecutive_failures = 0  # Reset on success
                
                # Process each product
                alerts_sent = 0
                active_ids = []
                
                for product in products:
                    try:
                        active_ids.append(product['id'])
                        
                        # Check if new or restocked
                        is_new, is_restock = await self.db.check_product(product)
                        
                        if is_new or is_restock:
                            # Send alert
                            await self.telegram.send_product_alert(product, is_new)
                            alerts_sent += 1
                            self.stats['alerts_sent'] += 1
                            
                            logger.info(f"🚨 Alert sent: {product['name'][:50]}...")
                            
                            # Small delay between alerts
                            await asyncio.sleep(1)
                        
                        # Save to database
                        await self.db.save_product(product, is_new, is_restock)
                        
                    except Exception as e:
                        logger.error(f"Error processing product: {str(e)}")
                        continue
                
                # Cleanup old products
                await self.db.cleanup_old_products(active_ids)
                
                # Record statistics
                await self.db.record_check(len(products), alerts_sent)
                
                logger.info(f"📊 Scan complete. Alerts sent: {alerts_sent}")
                return True
                
        except Exception as e:
            self.consecutive_failures += 1
            logger.error(f"❌ Scan failed: {str(e)}")
            
            if self.consecutive_failures >= 3:
                await self.telegram.send_error_alert(str(e))
            
            return False
    
    async def run(self):
        """Main bot loop"""
        self.running = True
        
        logger.info("🔄 Starting main loop...")
        
        last_summary_time = datetime.now()
        summary_interval = timedelta(hours=2)
        
        while self.running:
            try:
                current_time = datetime.now()
                
                # Check if too many failures
                if self.consecutive_failures >= self.max_failures:
                    wait_time = 300  # 5 minutes
                    logger.warning(f"⚠️ Multiple failures. Waiting {wait_time}s...")
                    await asyncio.sleep(wait_time)
                    self.consecutive_failures = 0
                
                # Perform scan
                await self.scan_products()
                
                # Send summary every 2 hours
                if current_time - last_summary_time >= summary_interval:
                    stats = await self.db.get_stats()
                    await self.telegram.send_summary(stats)
                    last_summary_time = current_time
                    logger.info("📋 Sent periodic summary")
                
                # Calculate next check time with jitter
                interval_seconds = Config.CHECK_INTERVAL_MINUTES * 60
                jitter = random.randint(-30, 30)  # ±30 seconds
                wait_time = max(60, interval_seconds + jitter)
                
                logger.info(f"⏳ Next check in {wait_time//60} minutes...")
                await asyncio.sleep(wait_time)
                
            except asyncio.CancelledError:
                logger.info("Bot loop cancelled")
                break
            except Exception as e:
                logger.error(f"Main loop error: {str(e)}")
                await asyncio.sleep(60)  # Wait before retry
    
    async def shutdown(self):
        """Shutdown bot gracefully"""
        self.running = False
        
        logger.info("🛑 Shutting down bot...")
        
        # Send shutdown message
        uptime = datetime.now() - self.stats['start_time']
        stats = await self.db.get_stats()
        
        shutdown_msg = f"""
🛑 <b>SHEIN BOT SHUTTING DOWN</b>

📊 <b>Final Stats:</b>
• Total Checks: {self.stats['checks']}
• Products Found: {self.stats['products_found']}
• Alerts Sent: {self.stats['alerts_sent']}
• New Today: {stats['new_today']}
• Restocks: {stats['restocks_today']}

⏰ <b>Uptime:</b> {str(uptime).split('.')[0]}

👋 <b>Goodbye!</b>
"""
        
        await self.telegram.send_message(shutdown_msg)
        logger.info("✅ Bot shutdown complete")

# Health check for Railway
from aiohttp import web

async def health_handler(request):
    return web.Response(text="OK", status=200)

async def start_health_server():
    """Start health check server"""
    app = web.Application()
    app.router.add_get('/health', health_handler)
    app.router.add_get('/', health_handler)
    
    runner = web.AppRunner(app)
    await runner.setup()
    
    port = int(os.getenv('PORT', '8080'))
    site = web.TCPSite(runner, '0.0.0.0', port)
    
    await site.start()
    logger.info(f"🌐 Health server running on port {port}")
    
    return runner

async def main():
    """Main entry point"""
    
    # Check environment
    if not Config.TELEGRAM_BOT_TOKEN or not Config.TELEGRAM_CHAT_ID:
        logger.error("❌ Missing Telegram credentials")
        logger.info("💡 Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID environment variables")
        sys.exit(1)
    
    # Start health server
    health_runner = await start_health_server()
    
    # Create bot
    bot = SheinVerseBot()
    
    # Setup signal handlers
    def handle_signal(signum, frame):
        logger.info(f"Received signal {signum}")
        asyncio.create_task(shutdown_sequence(bot, health_runner))
    
    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)
    
    try:
        # Initialize bot
        if await bot.initialize():
            # Run main loop
            await bot.run()
        else:
            logger.error("Failed to initialize bot")
    
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
    except Exception as e:
        logger.error(f"Fatal error: {str(e)}")
    
    finally:
        # Shutdown
        await shutdown_sequence(bot, health_runner)

async def shutdown_sequence(bot, health_runner):
    """Complete shutdown sequence"""
    logger.info("Starting shutdown sequence...")
    
    # Shutdown bot
    await bot.shutdown()
    
    # Shutdown health server
    if health_runner:
        await health_runner.cleanup()
    
    logger.info("Shutdown complete")

if __name__ == "__main__":
    print("\n" + "="*50)
    print("🤖 SHEIN VERSE BOT - Railway Deployment")
    print("="*50)
    
    print("\n✅ Required Environment Variables:")
    print("   TELEGRAM_BOT_TOKEN - From @BotFather")
    print("   TELEGRAM_CHAT_ID - From @userinfobot")
    print("   CHECK_INTERVAL_MINUTES - (Optional, default: 5)")
    print("   SHEIN_COUNTRY - (Optional, default: IN)")
    
    print("\n🚀 Starting bot...")
    
    # Run main function
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Bot stopped by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")
