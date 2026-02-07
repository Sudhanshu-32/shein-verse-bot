"""
Database for tracking products
"""

import sqlite3
import json
import logging
from datetime import datetime, timedelta
import os

logger = logging.getLogger(__name__)

class Database:
    def __init__(self, db_path: str = "products.db"):
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        """Initialize database"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS products (
                id TEXT PRIMARY KEY,
                name TEXT,
                price TEXT,
                image_url TEXT,
                url TEXT,
                sizes TEXT,
                total_stock INTEGER,
                category TEXT,
                first_seen TIMESTAMP,
                last_seen TIMESTAMP,
                is_active INTEGER DEFAULT 1,
                alert_sent INTEGER DEFAULT 0
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id TEXT,
                alert_type TEXT,
                timestamp TIMESTAMP,
                FOREIGN KEY (product_id) REFERENCES products (id)
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def _get_connection(self):
        """Get database connection"""
        return sqlite3.connect(self.db_path)
    
    async def check_product(self, product: Dict) -> tuple[bool, bool]:
        """
        Check if product is new or restocked
        Returns: (is_new, is_restock)
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT id, total_stock, alert_sent FROM products WHERE id = ?",
            (product['id'],)
        )
        
        existing = cursor.fetchone()
        
        if not existing:
            # New product
            conn.close()
            return True, False
        
        # Check for restock
        product_id, old_stock, alert_sent = existing
        new_stock = product.get('total_stock', 0)
        
        is_restock = (old_stock == 0 and new_stock > 0)
        
        conn.close()
        return False, is_restock
    
    async def save_product(self, product: Dict, is_new: bool, is_restock: bool):
        """Save or update product in database"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        now = datetime.now().isoformat()
        
        if is_new:
            # Insert new product
            cursor.execute('''
                INSERT INTO products 
                (id, name, price, image_url, url, sizes, total_stock, category, first_seen, last_seen)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                product['id'],
                product['name'],
                product['price'],
                product.get('image_url', ''),
                product['url'],
                json.dumps(product.get('sizes', {})),
                product.get('total_stock', 0),
                product.get('category', 'Men'),
                now,
                now
            ))
        else:
            # Update existing product
            cursor.execute('''
                UPDATE products 
                SET name = ?, price = ?, image_url = ?, url = ?, 
                    sizes = ?, total_stock = ?, last_seen = ?, is_active = 1
                WHERE id = ?
            ''', (
                product['name'],
                product['price'],
                product.get('image_url', ''),
                product['url'],
                json.dumps(product.get('sizes', {})),
                product.get('total_stock', 0),
                now,
                product['id']
            ))
        
        # Record alert if sent
        if is_new or is_restock:
            alert_type = 'new' if is_new else 'restock'
            cursor.execute('''
                INSERT INTO alerts (product_id, alert_type, timestamp)
                VALUES (?, ?, ?)
            ''', (product['id'], alert_type, now))
            
            # Mark alert sent
            cursor.execute(
                "UPDATE products SET alert_sent = 1 WHERE id = ?",
                (product['id'],)
            )
        
        conn.commit()
        conn.close()
    
    async def get_stats(self) -> Dict:
        """Get statistics"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        today = datetime.now().date().isoformat()
        
        # Total products
        cursor.execute("SELECT COUNT(*) FROM products WHERE is_active = 1")
        total_products = cursor.fetchone()[0]
        
        # New today
        cursor.execute('''
            SELECT COUNT(*) FROM alerts 
            WHERE alert_type = 'new' AND DATE(timestamp) = ?
        ''', (today,))
        new_today = cursor.fetchone()[0]
        
        # Restocks today
        cursor.execute('''
            SELECT COUNT(*) FROM alerts 
            WHERE alert_type = 'restock' AND DATE(timestamp) = ?
        ''', (today,))
        restocks_today = cursor.fetchone()[0]
        
        conn.close()
        
        return {
            'total_products': total_products,
            'new_today': new_today,
            'restocks_today': restocks_today
      }
