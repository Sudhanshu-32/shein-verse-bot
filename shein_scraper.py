"""
Advanced Shein Scraper with Anti-Detection
"""

import asyncio
import random
import aiohttp
from datetime import datetime
from typing import Dict, List, Optional
import logging
import json
from fake_useragent import UserAgent
from bs4 import BeautifulSoup
import urllib.parse

logger = logging.getLogger(__name__)

class SheinScraper:
    def __init__(self):
        self.ua = UserAgent()
        self.session = None
        self.proxy_list = self._get_proxy_list()
        
    def _get_proxy_list(self):
        """Get free proxy list (rotate if needed)"""
        # These are example proxies, you should use actual proxy service
        return [
            None,  # No proxy sometimes
            # Add your proxy URLs here if you have
        ]
    
    def _get_headers(self) -> Dict:
        """Generate random headers for each request"""
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
            'Referer': 'https://www.google.com/',
        }
    
    def get_random_interval(self) -> int:
        """Get random interval between checks (120-300 seconds)"""
        return random.randint(120, 300)  # 2-5 minutes
    
    async def _get_session(self):
        """Get or create aiohttp session"""
        if self.session is None or self.session.closed:
            timeout = aiohttp.ClientTimeout(total=30)
            connector = aiohttp.TCPConnector(limit=10, force_close=True)
            self.session = aiohttp.ClientSession(
                timeout=timeout,
                connector=connector,
                headers=self._get_headers()
            )
        return self.session
    
    async def close(self):
        """Close session"""
        if self.session and not self.session.closed:
            await self.session.close()
    
    async def _request_with_retry(self, url: str, max_retries: int = 3) -> Optional[str]:
        """Make request with retry logic and anti-detection"""
        session = await self._get_session()
        
        for attempt in range(max_retries):
            try:
                # Random delay between requests
                await asyncio.sleep(random.uniform(1, 3))
                
                # Rotate headers
                session.headers.update(self._get_headers())
                
                # Use proxy randomly
                proxy = random.choice(self.proxy_list) if self.proxy_list else None
                
                logger.debug(f"Attempt {attempt+1} for {url[:50]}...")
                
                async with session.get(url, proxy=proxy, ssl=False) as response:
                    if response.status == 200:
                        return await response.text()
                    elif response.status == 403 or response.status == 429:
                        logger.warning(f"Blocked detected. Waiting...")
                        await asyncio.sleep(10 * (attempt + 1))  # Exponential backoff
                        continue
                    else:
                        logger.warning(f"Status {response.status} for {url}")
                        
            except Exception as e:
                logger.warning(f"Request failed (attempt {attempt+1}): {str(e)}")
                await asyncio.sleep(5 * (attempt + 1))
        
        return None
    
    async def get_men_products(self) -> List[Dict]:
        """
        Get Men's products from Shein Verse with anti-detection
        """
        base_url = "https://www.shein.in/shein-verse-men-c-2513.html"
        
        # Add random parameters to avoid caching
        params = {
            'v': str(int(datetime.now().timestamp())),
            'r': random.randint(1000, 9999)
        }
        url = f"{base_url}?{urllib.parse.urlencode(params)}"
        
        html = await self._request_with_retry(url)
        if not html:
            return []
        
        return self._parse_products(html)
    
    def _parse_products(self, html: str) -> List[Dict]:
        """Parse products from HTML with error handling"""
        products = []
        soup = BeautifulSoup(html, 'html.parser')
        
        # Multiple possible selectors (Shein changes these)
        selectors = [
            '.S-product-item',
            '.c-product-list__item',
            '.product-card',
            '.j-expose__product-item',
            '[data-product-id]'
        ]
        
        for selector in selectors:
            items = soup.select(selector)
            if items:
                logger.info(f"Found {len(items)} products with selector: {selector}")
                for item in items[:50]:  # Limit to 50 to avoid rate limiting
                    try:
                        product = self._extract_product(item)
                        if product and self._is_men_product(product):
                            products.append(product)
                    except Exception as e:
                        logger.debug(f"Error parsing item: {str(e)}")
                break
        
        logger.info(f"Parsed {len(products)} Men's products")
        return products
    
    def _extract_product(self, item) -> Optional[Dict]:
        """Extract product data from HTML element"""
        try:
            # Extract product ID
            product_id = item.get('data-product-id') or \
                        item.get('data-goods-id') or \
                        str(random.randint(1000000, 9999999))
            
            # Extract name
            name_elem = item.select_one('.product-name, .goods-name, .name')
            name = name_elem.get_text(strip=True) if name_elem else "Unknown Product"
            
            # Extract price
            price_elem = item.select_one('.price, .current-price, .goods-price')
            price = price_elem.get_text(strip=True) if price_elem else "₹0"
            
            # Extract image
            img_elem = item.select_one('img')
            image_url = img_elem.get('src') or img_elem.get('data-src') if img_elem else ""
            if image_url and not image_url.startswith('http'):
                image_url = f"https:{image_url}"
            
            # Extract URL
            link_elem = item.select_one('a')
            relative_url = link_elem.get('href') if link_elem else ""
            if relative_url and not relative_url.startswith('http'):
                product_url = f"https://www.shein.in{relative_url}"
            else:
                product_url = relative_url
            
            return {
                'id': product_id,
                'name': name[:200],  # Limit length
                'price': price,
                'image_url': image_url,
                'url': product_url,
                'category': 'Men',
                'timestamp': datetime.now().isoformat(),
                'is_new': 'new' in str(item).lower() or 'new' in name.lower()
            }
            
        except Exception as e:
            logger.debug(f"Extraction error: {str(e)}")
            return None
    
    def _is_men_product(self, product: Dict) -> bool:
        """Check if product belongs to Men's category"""
        name = product.get('name', '').lower()
        
        # Keywords that indicate Men's product
        men_keywords = ['men', 'man', 'male', 'boys', 'guy']
        women_keywords = ['women', 'woman', 'female', 'girls', 'ladies', 'dress']
        
        # Check for women keywords first (to exclude)
        for keyword in women_keywords:
            if keyword in name:
                return False
        
        # Check for men keywords
        for keyword in men_keywords:
            if keyword in name:
                return True
        
        # Default to True if unclear (you can change this)
        return True
    
    async def get_product_details(self, product: Dict) -> Dict:
        """
        Get detailed product info including sizes
        This uses product detail page
        """
        if not product.get('url'):
            return product
        
        # Add delay before detail request
        await asyncio.sleep(random.uniform(2, 5))
        
        html = await self._request_with_retry(product['url'])
        if not html:
            return product
        
        # Parse sizes from detail page
        sizes = self._parse_sizes(html)
        product['sizes'] = sizes
        product['available_sizes'] = [size for size in sizes if sizes[size] > 0]
        product['total_stock'] = sum(sizes.values())
        
        return product
    
    def _parse_sizes(self, html: str) -> Dict[str, int]:
        """Parse available sizes and quantities"""
        sizes = {}
        soup = BeautifulSoup(html, 'html.parser')
        
        # Try multiple selectors for sizes
        size_selectors = [
            '.product-size-select option',
            '.sku-item',
            '.size-option',
            '[data-size]'
        ]
        
        for selector in size_selectors:
            size_elements = soup.select(selector)
            if size_elements:
                for elem in size_elements:
                    size_text = elem.get_text(strip=True)
                    if size_text and len(size_text) < 10:
                        # Check if available (not disabled/sold-out)
                        is_disabled = 'disabled' in elem.get('class', []) or \
                                     'sold-out' in elem.get('class', []) or \
                                     'out-of-stock' in str(elem)
                        
                        if not is_disabled:
                            # Try to get quantity (default to 1 if unknown)
                            quantity = 1
                            stock_attr = elem.get('data-stock') or elem.get('data-quantity')
                            if stock_attr and stock_attr.isdigit():
                                quantity = int(stock_attr)
                            
                            sizes[size_text] = quantity
        
        # If no sizes found, add default sizes
        if not sizes:
            sizes = {'S': 1, 'M': 1, 'L': 1, 'XL': 1}
        
        return sizes
