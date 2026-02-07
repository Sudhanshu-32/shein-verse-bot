"""
Configuration for Shein Bot
"""

import os
from typing import Dict, List
import random

class Config:
    # Telegram
    TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '')
    TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', '')
    
    # Shein Settings
    SHEIN_COUNTRY = os.getenv('SHEIN_COUNTRY', 'IN')
    SHEIN_BASE_URL = f"https://www.shein.{SHEIN_COUNTRY.lower()}"
    SHEIN_VERSE_URL = f"{SHEIN_BASE_URL}/c/sverse-5939-37961"
    
    # Bot Settings
    CHECK_INTERVAL_MINUTES = int(os.getenv('CHECK_INTERVAL_MINUTES', '5'))
    MAX_RETRIES = 3
    REQUEST_TIMEOUT = 30
    
    # Anti-Detection
    ENABLE_PROXY_ROTATION = os.getenv('ENABLE_PROXY_ROTATION', 'false').lower() == 'true'
    RANDOM_DELAY_MIN = 2
    RANDOM_DELAY_MAX = 5
    ROTATE_USER_AGENTS = True
    
    # Database
    DB_PATH = "shein_data.db"
    
    # Logging
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    
    # User Agents
    USER_AGENTS = [
        # Chrome Windows
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
        # Firefox Windows
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0',
        # Chrome Mac
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        # Safari
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15',
        # Mobile
        'Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1',
        'Mozilla/5.0 (Linux; Android 13; SM-S901B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36'
    ]
    
    # Proxies (Add your own)
    PROXY_LIST = [
        None,  # No proxy
        # Add your proxies here:
        # 'http://user:pass@proxy1.com:8080',
        # 'http://user:pass@proxy2.com:8080',
    ]
    
    # Shein Verse Men's Category ID
    MEN_CATEGORY_ID = "2513"
    
    @classmethod
    def get_random_user_agent(cls) -> str:
        return random.choice(cls.USER_AGENTS)
    
    @classmethod
    def get_random_delay(cls) -> float:
        return random.uniform(cls.RANDOM_DELAY_MIN, cls.RANDOM_DELAY_MAX)
    
    @classmethod
    def get_random_proxy(cls):
        if cls.ENABLE_PROXY_ROTATION and cls.PROXY_LIST:
            return random.choice(cls.PROXY_LIST)
        return None
