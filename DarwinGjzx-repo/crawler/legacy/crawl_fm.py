from crawl4ai import AsyncWebCrawler
from crawl4ai import JsonCssExtractionStrategy
from crawl4ai.async_configs import BrowserConfig, CrawlerRunConfig
import json
import csv
import asyncio
from urllib.parse import urljoin, urlparse
import re
from datetime import datetime
import time


class ForestMarketCrawler:
    def __init__(self):
        self.base_url = "https://www.forestmarket.net"
        self.visited_urls = set()
        self.products = []
        self.all_links = set()
        
    async def discover_urls(self):
        """Discover all possible URLs on the Forest Market website"""
        browser_config = BrowserConfig(browser_type="chromium", headless=True)
        
        # Start with known working URLs
        urls_to_check = [
            self.base_url,
            f"{self.base_url}/en-SG",
            f"{self.base_url}/en-US",
            f"{self.base_url}/en-HK",
            f"{self.base_url}/en-KR",
            f"{self.base_url}/en-JP",
        ]
        
        # Add category URLs to check  
        categories = ["digital-goods", "depin", "electronics", "fashion", "collectibles", "custom", "other"]
        locales = ["", "/en-US", "/en-SG", "/en-HK", "/en-KR", "/en-JP"]
        
        for locale in locales:
            for category in categories:
                urls_to_check.extend([
                    f"{self.base_url}{locale}/{category}",
                    f"{self.base_url}{locale}/categories/{category}",
                    f"{self.base_url}{locale}/products/{category}",
                ])
        
        # Add known product URLs from previous runs
        known_product_ids = [
            "jocY8fxxfRzl", "XntoeP9TP9-g", "HgzFisNSKXv6", "-91denl7WPh2",
            "OE9bJFIaQD5Z", "lUCtlVMqQYBH", "qI0Yzc6LyREJ", "DHdMHDtZ57iy",
            "VCz-Aaxv-Xli", "i2Tz7nKcCzjy", "uD9l5XnLYm9n", "k5GQN8LRDaHj",
            "snhacBgOOUoG"
        ]
        
        for locale in ["/en-SG", "/en-US", ""]:
            for product_id in known_product_ids:
                urls_to_check.append(f"{self.base_url}{locale}/product/{product_id}")
        
        async with AsyncWebCrawler(config=browser_config) as crawler:
            for url in urls_to_check:
                try:
                    print(f"🔍 Discovering URLs from: {url}")
                    result = await crawler.arun(url=url)
                    
                    if result and result.html:
                        # Extract all links from the page
                        links = re.findall(r'href=["\']([^"\']+)["\']', result.html)
                        for link in links:
                            full_url = urljoin(url, link)
                            if self.is_forest_market_url(full_url):
                                self.all_links.add(full_url)
                                
                        # Also look for product links in a more specific way
                        product_links = re.findall(r'href=["\']([^"\']*\/product\/[^"\']+)["\']', result.html)
                        for link in product_links:
                            full_url = urljoin(url, link)
                            if self.is_forest_market_url(full_url):
                                self.all_links.add(full_url)
                                print(f"🎯 Found product URL: {full_url}")
                                
                except Exception as e:
                    print(f"❌ Error discovering URLs from {url}: {e}")
                    
        print(f"🎉 Discovered {len(self.all_links)} unique URLs")
        return list(self.all_links)
    
    def is_forest_market_url(self, url):
        """Check if URL belongs to Forest Market domain"""
        parsed = urlparse(url)
        return parsed.netloc in ['www.forestmarket.net', 'forestmarket.net']
    
    async def extract_detailed_product_info(self, url):
        """Extract detailed product information from individual product pages"""
        browser_config = BrowserConfig(
            browser_type="chromium", 
            headless=True,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )
        
        # Comprehensive product extraction strategy
        detailed_product_config = CrawlerRunConfig(
            wait_for="css:body",
            page_timeout=30000,
            extraction_strategy=JsonCssExtractionStrategy(
                schema={
                    "name": "Detailed Forest Market Product",
                    "baseSelector": "body",
                    "fields": [
                        # Core product information
                        {"name": "product_title", "selector": "h1, .product-title, [class*='title'], [data-testid*='title']", "type": "text"},
                        {"name": "product_subtitle", "selector": "h2, .product-subtitle, .subtitle", "type": "text"},
                        {"name": "product_id", "selector": "[data-product-id], [id*='product']", "type": "attribute", "attribute": "data-product-id"},
                        
                        # Pricing information
                        {"name": "current_price", "selector": ".price, .current-price, [class*='price']:not([class*='original']), .cost, [data-testid*='price']", "type": "text"},
                        {"name": "original_price", "selector": ".original-price, .was-price, [class*='original'][class*='price'], .strike, .crossed", "type": "text"},
                        {"name": "currency", "selector": ".currency, [class*='currency']", "type": "text"},
                        {"name": "discount", "selector": ".discount, .sale, [class*='discount'], [class*='save']", "type": "text"},
                        
                        # Product images
                        {"name": "main_image", "selector": ".product-image img, .main-image img, .hero-image img, img[class*='product']", "type": "attribute", "attribute": "src"},
                        {"name": "gallery_images", "selector": ".gallery img, .product-gallery img, .thumbnails img", "type": "attribute", "attribute": "src", "multiple": True},
                        {"name": "image_alt", "selector": ".product-image img, .main-image img", "type": "attribute", "attribute": "alt"},
                        
                        # Product description
                        {"name": "short_description", "selector": ".short-desc, .product-summary, .brief, [class*='summary']", "type": "text"},
                        {"name": "full_description", "selector": ".description, .product-description, .details, [class*='description'], .product-details", "type": "text"},
                        {"name": "features", "selector": ".features li, .product-features li, .specs li", "type": "text", "multiple": True},
                        {"name": "specifications", "selector": ".specs, .specifications, .product-specs", "type": "text"},
                        
                        # Seller information
                        {"name": "seller_name", "selector": ".seller-name, .vendor, .merchant, [class*='seller'], [class*='vendor']", "type": "text"},
                        {"name": "seller_rating", "selector": ".seller-rating, .vendor-rating, [class*='seller'][class*='rating']", "type": "text"},
                        {"name": "seller_reviews", "selector": ".seller-reviews, .vendor-reviews", "type": "text"},
                        {"name": "seller_location", "selector": ".seller-location, .vendor-location, [class*='location']", "type": "text"},
                        {"name": "seller_profile_link", "selector": ".seller-profile a, .vendor-profile a", "type": "attribute", "attribute": "href"},
                        
                        # Product condition and availability
                        {"name": "condition", "selector": ".condition, .product-condition, [class*='condition']", "type": "text"},
                        {"name": "availability", "selector": ".availability, .stock, .in-stock, .out-of-stock, [class*='stock'], [class*='availability']", "type": "text"},
                        {"name": "quantity_available", "selector": ".quantity, .stock-count, [class*='quantity']", "type": "text"},
                        
                        # Payment and shipping
                        {"name": "payment_methods", "selector": ".payment-methods, .accepted-payments, [class*='payment']", "type": "text", "multiple": True},
                        {"name": "shipping_info", "selector": ".shipping, .delivery, [class*='shipping'], [class*='delivery']", "type": "text"},
                        {"name": "shipping_cost", "selector": ".shipping-cost, .delivery-cost, [class*='shipping'][class*='cost']", "type": "text"},
                        {"name": "return_policy", "selector": ".returns, .return-policy, [class*='return']", "type": "text"},
                        {"name": "warranty", "selector": ".warranty, .guarantee, [class*='warranty']", "type": "text"},
                        
                        # Reviews and ratings
                        {"name": "overall_rating", "selector": ".rating, .product-rating, .stars, [class*='rating']", "type": "text"},
                        {"name": "review_count", "selector": ".review-count, .reviews-count, [class*='review'][class*='count']", "type": "text"},
                        {"name": "recent_reviews", "selector": ".review-text, .customer-review", "type": "text", "multiple": True},
                        
                        # Category and tags
                        {"name": "category", "selector": ".category, .breadcrumb, [class*='category'], .product-category", "type": "text"},
                        {"name": "tags", "selector": ".tags, .product-tags, .keywords", "type": "text", "multiple": True},
                        {"name": "brand", "selector": ".brand, .manufacturer, [class*='brand']", "type": "text"},
                        
                        # Additional metadata
                        {"name": "sku", "selector": ".sku, .product-code, [class*='sku']", "type": "text"},
                        {"name": "date_listed", "selector": ".date-listed, .created-date, [class*='date']", "type": "text"},
                        {"name": "last_updated", "selector": ".last-updated, .modified-date", "type": "text"},
                    ],
                }
            )
        )
        
        async with AsyncWebCrawler(config=browser_config) as crawler:
            try:
                print(f"🔍 Extracting detailed product info from: {url}")
                result = await crawler.arun(url=url, config=detailed_product_config)
                
                if result and result.extracted_content:
                    try:
                        extracted_data = json.loads(result.extracted_content)
                        if extracted_data:
                            # Clean and enhance the extracted data
                            product = self.clean_product_data(extracted_data, url)
                            return product
                    except json.JSONDecodeError as e:
                        print(f"JSON decode error for {url}: {e}")
                
                # Fallback: try to extract from HTML structure
                if result and result.html:
                    return self.extract_product_from_html(result.html, url)
                    
            except Exception as e:
                print(f"❌ Error extracting detailed info from {url}: {e}")
                
        return None
    
    def clean_product_data(self, raw_data, url):
        """Clean and structure the extracted product data"""
        product = {
            'url': url,
            'crawled_at': datetime.now().isoformat(),
        }
        
        # Map and clean the fields
        for key, value in raw_data.items():
            if value and str(value).strip():
                if isinstance(value, list):
                    # Clean list values
                    cleaned_list = [str(v).strip() for v in value if v and str(v).strip()]
                    if cleaned_list:
                        product[key] = cleaned_list
                else:
                    # Clean single values
                    cleaned_value = str(value).strip()
                    if cleaned_value and cleaned_value not in ['null', 'undefined', 'None']:
                        product[key] = cleaned_value
        
        # Extract product ID from URL if not found
        if 'product_id' not in product:
            product_id_match = re.search(r'/product/([^/?]+)', url)
            if product_id_match:
                product['product_id'] = product_id_match.group(1)
        
        return product
    
    def extract_product_from_html(self, html, url):
        """Fallback method to extract product data from raw HTML"""
        product = {
            'url': url,
            'crawled_at': datetime.now().isoformat(),
        }
        
        # Extract title from various possible locations
        title_patterns = [
            r'<h1[^>]*>([^<]+)</h1>',
            r'<title>([^<]+)</title>',
            r'property="og:title"\s+content="([^"]+)"',
            r'name="title"\s+content="([^"]+)"'
        ]
        
        for pattern in title_patterns:
            match = re.search(pattern, html, re.IGNORECASE)
            if match:
                product['product_title'] = match.group(1).strip()
                break
        
        # Extract price patterns
        price_patterns = [
            r'[\$€£¥₹][\d,]+\.?\d*',
            r'\b\d+\.\d{2}\s*(?:USD|EUR|GBP|SGD)\b',
            r'price["\']:\s*["\']?([^"\']+)["\']?'
        ]
        
        for pattern in price_patterns:
            matches = re.findall(pattern, html, re.IGNORECASE)
            if matches:
                product['current_price'] = matches[0]
                break
        
        # Extract images
        img_pattern = r'<img[^>]+src=["\']([^"\']+)["\'][^>]*>'
        images = re.findall(img_pattern, html)
        if images:
            product['main_image'] = images[0]
            if len(images) > 1:
                product['gallery_images'] = images[1:5]  # Limit to first 5 additional images
        
        return product if len(product) > 2 else None  # Return only if we found meaningful data
    
    async def extract_products_from_page(self, url):
        """Extract product information from a single page"""
        # Check if this is a product detail page
        if '/product/' in url:
            detailed_product = await self.extract_detailed_product_info(url)
            return [detailed_product] if detailed_product else []
        
        # For other pages, use the original extraction method
        browser_config = BrowserConfig(browser_type="chromium", headless=True)
        
        # Generic product extraction strategy for listing pages
        crawler_config = CrawlerRunConfig(
            extraction_strategy=JsonCssExtractionStrategy(
                schema={
                    "name": "Forest Market Product Listings",
                    "baseSelector": "div, article, section, .product, .item, [class*='product'], [class*='item']",
                    "fields": [
                        {"name": "title", "selector": "h1, h2, h3, h4, .title, [class*='title'], [class*='name']", "type": "text"},
                        {"name": "price", "selector": ".price, [class*='price'], .cost, [class*='cost']", "type": "text"},
                        {"name": "description", "selector": ".description, [class*='description'], .desc, p", "type": "text"},
                        {"name": "image", "selector": "img", "type": "attribute", "attribute": "src"},
                        {"name": "link", "selector": "a", "type": "attribute", "attribute": "href"},
                        {"name": "category", "selector": ".category, [class*='category'], .tag, [class*='tag']", "type": "text"},
                        {"name": "availability", "selector": ".stock, [class*='stock'], .available, [class*='available']", "type": "text"},
                        {"name": "rating", "selector": ".rating, [class*='rating'], .stars, [class*='stars']", "type": "text"},
                    ],
                }
            )
        )
        
        async with AsyncWebCrawler(config=browser_config) as crawler:
            try:
                print(f"📄 Extracting from listing page: {url}")
                result = await crawler.arun(url=url, config=crawler_config)
                
                if result and result.extracted_content:
                    try:
                        products = json.loads(result.extracted_content)
                        if isinstance(products, list):
                            # Filter out empty or irrelevant results
                            valid_products = []
                            for product in products:
                                if self.is_valid_product(product):
                                    product['source_url'] = url
                                    product['crawled_at'] = datetime.now().isoformat()
                                    valid_products.append(product)
                            return valid_products
                    except json.JSONDecodeError:
                        print(f"JSON decode error for {url}")
                        
                # Fallback: extract any text content that might be products
                if result and result.markdown:
                    return self.extract_from_markdown(result.markdown, url)
                    
            except Exception as e:
                print(f"Error extracting from {url}: {e}")
                
        return []
    
    def is_valid_product(self, product):
        """Check if extracted data represents a valid product"""
        if not isinstance(product, dict):
            return False
            
        # Must have at least a title or description
        title = product.get('title', '').strip()
        description = product.get('description', '').strip()
        
        if not title and not description:
            return False
            
        # Filter out common non-product content
        exclude_terms = ['privacy', 'cookie', 'terms', 'about', 'contact', 'faq', 'support', 'login', 'register']
        text_to_check = f"{title} {description}".lower()
        
        if any(term in text_to_check for term in exclude_terms):
            return False
            
        # Prefer items with price information
        return len(title) > 3 or len(description) > 10
    
    def extract_from_markdown(self, markdown, url):
        """Extract product-like information from markdown content"""
        products = []
        lines = markdown.split('\n')
        
        current_product = {}
        for line in lines:
            line = line.strip()
            if not line:
                if current_product:
                    current_product['source_url'] = url
                    current_product['crawled_at'] = datetime.now().isoformat()
                    products.append(current_product)
                    current_product = {}
                continue
                
            # Look for headers that might be product titles
            if line.startswith('#') and len(line) > 5:
                if current_product:
                    current_product['source_url'] = url
                    current_product['crawled_at'] = datetime.now().isoformat()
                    products.append(current_product)
                current_product = {'title': line.lstrip('#').strip()}
                
            # Look for price patterns
            elif '$' in line or '€' in line or '£' in line or 'USD' in line:
                current_product['price'] = line
                
            # General content
            elif line and 'title' not in current_product:
                current_product['description'] = line
                
        if current_product:
            current_product['source_url'] = url
            current_product['crawled_at'] = datetime.now().isoformat()
            products.append(current_product)
            
        return [p for p in products if self.is_valid_product(p)]
    
    async def crawl_product_detail_pages(self):
        """Focus on crawling individual product detail pages for comprehensive data"""
        print("🚀 Starting detailed Forest Market product crawler...")
        
        # Discover all URLs
        all_urls = await self.discover_urls()
        
        # Filter for product detail pages
        product_urls = [url for url in all_urls if '/product/' in url]
        print(f"🎯 Found {len(product_urls)} product detail pages to crawl")
        
        # Crawl each product URL with detailed extraction
        for i, url in enumerate(product_urls):
            if url not in self.visited_urls:
                self.visited_urls.add(url)
                
                print(f"📦 Processing product {i+1}/{len(product_urls)}: {url}")
                
                # Add rate limiting to be respectful
                if i > 0:
                    await asyncio.sleep(1)  # 1 second delay between requests
                
                product = await self.extract_detailed_product_info(url)
                if product:
                    self.products.append(product)
                    print(f"✅ Successfully extracted product: {product.get('product_title', 'Unknown')}")
                else:
                    print(f"❌ Failed to extract product from {url}")
                    
        print(f"🎉 Total detailed products extracted: {len(self.products)}")
        return self.products
    
    async def crawl_all_products(self):
        """Main method to crawl all products from Forest Market"""
        print("Starting Forest Market crawler...")
        
        # Discover all URLs
        all_urls = await self.discover_urls()
        
        # Crawl each URL for products
        for url in all_urls:
            if url not in self.visited_urls:
                self.visited_urls.add(url)
                products = await self.extract_products_from_page(url)
                if products:
                    self.products.extend(products)
                    print(f"Found {len(products)} products on {url}")
                    
        print(f"Total products found: {len(self.products)}")
        return self.products
    
    def save_to_csv(self, filename="forest_market_products.csv"):
        """Save extracted products to CSV file"""
        if not self.products:
            print("No products to save")
            return
            
        # Get all unique fields from all products
        all_fields = set()
        for product in self.products:
            all_fields.update(product.keys())
        
        fieldnames = sorted(list(all_fields))
        
        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            
            for product in self.products:
                # Clean the data
                clean_product = {}
                for field in fieldnames:
                    value = product.get(field, '')
                    if isinstance(value, str):
                        clean_product[field] = value.strip()
                    else:
                        clean_product[field] = str(value) if value is not None else ''
                        
                writer.writerow(clean_product)
                
        print(f"Saved {len(self.products)} products to {filename}")


async def main():
    crawler = ForestMarketCrawler()
    
    print("Choose crawling mode:")
    print("1. Detailed product extraction (recommended for comprehensive data)")
    print("2. General page extraction (faster but less detailed)")
    
    # For automation, default to detailed extraction
    mode = "1"  # You can change this to "2" for general extraction
    
    if mode == "1":
        products = await crawler.crawl_product_detail_pages()
        filename = "forest_market_detailed_products.csv"
    else:
        products = await crawler.crawl_all_products()
        filename = "forest_market_products.csv"
    
    if products:
        crawler.save_to_csv(filename)
        print(f"\n📊 Successfully saved {len(products)} products to {filename}")
        
        print("\n🔍 Sample detailed product information:")
        for i, product in enumerate(products[:2]):
            print(f"\n📦 Product {i+1}:")
            for key, value in product.items():
                if value and key not in ['crawled_at', 'url']:
                    if isinstance(value, list):
                        print(f"  {key}: {', '.join(map(str, value))}")
                    else:
                        print(f"  {key}: {value}")
    else:
        print("❌ No products found. The website might not have visible products or may require different extraction methods.")


if __name__ == "__main__":
    asyncio.run(main())