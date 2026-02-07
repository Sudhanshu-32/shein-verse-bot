"""
SQLite database for tracking
"""

import sqlite3
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from config import Config

logger = logging.getLogger(__name__)

class Database:
    def __init__(self, db_path: str = Config.DB_PATH):
        self.db_path = db_path
        self._init_database()
    
    def _init_database(self):
        """Initialize database tables"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Products table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS products (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                price REAL,
                original_price REAL,
                url TEXT NOT NULL,
                image_url TEXT,
                sizes TEXT,
                total_stock INTEGER,
                category TEXT DEFAULT 'Men',
                first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_alert TIMESTAMP,
                alert_count INTEGER DEFAULT 0,
                is_active INTEGER DEFAULT 1
            )
        ''')
        
        # Price history
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS price_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id TEXT,
                price REAL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (product_id) REFERENCES products (id)
            )
        ''')
        
        # Stock alerts
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS stock_alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id TEXT,
                alert_type TEXT,
                sizes TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (product_id) REFERENCES products (id)
            )
        ''')
        
        # Bot stats
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS bot_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                check_count INTEGER DEFAULT 0,
                products_found INTEGER DEFAULT 0,
                alerts_sent INTEGER DEFAULT 0,
                last_check TIMESTAMP,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
        logger.info("Database initialized")
    
    def _get_connection(self):
        """Get database connection"""
        return sqlite3.connect(self.db_path, timeout=20)
    
    async def check_product(self, product: Dict) -> Tuple[bool, bool]:
        """
        Check if product is new or restocked
        Returns: (is_new, is_restocked)
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT id, total_stock FROM products WHERE id = ?",
            (product['id'],)
        )
        
        existing = cursor.fetchone()
        
        if not existing:
            # New product
            conn.close()
            return True, False
        
        # Check for restock
        product_id, old_stock = existing
        new_stock = product.get('total_stock', 0)
        
        is_restocked = (old_stock == 0 and new_stock > 0)
        
        conn.close()
        return False, is_restocked
    
    async def save_product(self, product: Dict, is_new: bool, is_restock: bool):
        """Save or update product"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        now = datetime.now().isoformat()
        sizes_json = json.dumps(product.get('sizes', {}))
        
        if is_new:
            # Insert new product
            cursor.execute('''
                INSERT INTO products 
                (id, name, price, original_price, url, image_url, sizes, total_stock, 
                 category, first_seen, last_seen, is_active)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                product['id'],
                product['name'],
                float(product.get('price', 0)) if str(product.get('price', '0')).replace('.', '', 1).isdigit() else 0,
                float(product.get('original_price', 0)) if str(product.get('original_price', '0')).replace('.', '', 1).isdigit() else 0,
                product['url'],
                product.get('image', ''),
                sizes_json,
                product.get('total_stock', 0),
                product.get('category', 'Men'),
                now,
                now,
                1
            ))
        else:
            # Update existing
            cursor.execute('''
                UPDATE products 
                SET name = ?, price = ?, original_price = ?, url = ?, 
                    image_url = ?, sizes = ?, total_stock = ?, last_seen = ?, is_active = 1
                WHERE id = ?
            ''', (
                product['name'],
                float(product.get('price', 0)) if str(product.get('price', '0')).replace('.', '', 1).isdigit() else 0,
                float(product.get('original_price', 0)) if str(product.get('original_price', '0')).replace('.', '', 1).isdigit() else 0,
                product['url'],
                product.get('image', ''),
                sizes_json,
                product.get('total_stock', 0),
                now,
                product['id']
            ))
        
        # Record alert if needed
        if is_new or is_restock:
            alert_type = 'new' if is_new else 'restock'
            
            cursor.execute('''
                INSERT INTO stock_alerts (product_id, alert_type, sizes, timestamp)
                VALUES (?, ?, ?, ?)
            ''', (
                product['id'],
                alert_type,
                sizes_json,
                now
            ))
            
            # Update product alert info
            cursor.execute('''
                UPDATE products 
                SET last_alert = ?, alert_count = alert_count + 1 
                WHERE id = ?
            ''', (now, product['id']))
        
        # Update price history if changed
        cursor.execute('SELECT price FROM products WHERE id = ?', (product['id'],))
        old_price = cursor.fetchone()
        
        if old_price and float(old_price[0]) != float(product.get('price', 0)):
            cursor.execute('''
                INSERT INTO price_history (product_id, price)
                VALUES (?, ?)
            ''', (product['id'], float(product.get('price', 0))))
        
        conn.commit()
        conn.close()
    
    async def record_check(self, products_found: int, alerts_sent: int):
        """Record bot check statistics"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO bot_stats (check_count, products_found, alerts_sent, last_check)
            VALUES (1, ?, ?, ?)
        ''', (products_found, alerts_sent, datetime.now().isoformat()))
        
        conn.commit()
        conn.close()
    
    async def get_stats(self) -> Dict:
        """Get bot statistics"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Total products
        cursor.execute("SELECT COUNT(*) FROM products WHERE is_active = 1")
        total_products = cursor.fetchone()[0]
        
        # New today
        today = datetime.now().date().isoformat()
        cursor.execute('''
            SELECT COUNT(*) FROM stock_alerts 
            WHERE alert_type = 'new' AND DATE(timestamp) = ?
        ''', (today,))
        new_today = cursor.fetchone()[0]
        
        # Restocks today
        cursor.execute('''
            SELECT COUNT(*) FROM stock_alerts 
            WHERE alert_type = 'restock' AND DATE(timestamp) = ?
        ''', (today,))
        restocks_today = cursor.fetchone()[0]
        
        # Total alerts
        cursor.execute("SELECT COUNT(*) FROM stock_alerts")
        total_alerts = cursor.fetchone()[0]
        
        # Latest check
        cursor.execute("SELECT MAX(last_check) FROM bot_stats")
        last_check = cursor.fetchone()[0] or "Never"
        
        conn.close()
        
        return {
            'total_products': total_products,
            'new_today': new_today,
            'restocks_today': restocks_today,
            'alerts_sent': total_alerts,
            'last_check': last_check
        }
    
    async def cleanup_old_products(self, active_product_ids: List[str]):
        """Mark inactive products"""
        if not active_product_ids:
            return
        
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Create placeholders for query
        placeholders = ','.join(['?'] * len(active_product_ids))
        
        cursor.execute(f'''
            UPDATE products 
            SET is_active = 0 
            WHERE id NOT IN ({placeholders}) AND is_active = 1
        ''', active_product_ids)
        
        conn.commit()
        conn.close()
        
        logger.info(f"Cleaned up inactive products")
