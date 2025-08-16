from crawl4ai import AsyncWebCrawler, LLMConfig, LLMExtractionStrategy
from crawl4ai.async_configs import BrowserConfig, CrawlerRunConfig
from crawl4ai.extraction_strategy import JsonCssExtractionStrategy
import json
import csv
import asyncio
from urllib.parse import urljoin, urlparse
import re
from datetime import datetime
import time
import os
from pydantic import BaseModel
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class FMModel(BaseModel):
    product_title: str
    product_description: str
    product_condition: str
    shipping_details: str
    return_details: str
    price: float
    currency: str
    discount_price: float
    main_image: str
    product_images: list[str]
    image_alts: list[str]
    sizes: list[str]
    colors: list[str]
    payment_methods: list[str]
    seller_name: str



class DetailedForestMarketCrawler:
    def __init__(self, input_csv=None, selected_countries=None):
        self.base_url = "https://www.forestmarket.net"
        self.products = []
        self.failed_urls = []
        self.input_csv = input_csv
        self.selected_countries = selected_countries or []
        
        # Available countries mapping
        self.available_countries = {
            'en-US': 'United States',
            'en-SG': 'Singapore', 
            'en-HK': 'Hong Kong',
            'en-KR': 'South Korea',
            'en-JP': 'Japan'
        }
        
        
    def load_product_urls_from_csv(self):
        """Load product URLs from CSV file (supports both single-column and multi-location formats)"""
        product_urls = []
        
        if not self.input_csv or not os.path.exists(self.input_csv):
            print(f"CSV file not found: {self.input_csv}")
            return []
            
        try:
            with open(self.input_csv, 'r', encoding='utf-8') as file:
                reader = csv.DictReader(file)
                headers = reader.fieldnames
                
                # Check if it's a multi-location CSV (has country columns)
                country_columns = [col for col in headers if col in self.available_countries]
                
                if country_columns:
                    # Multi-location CSV format (from crawl_fm_url_enhanced.py)
                    print(f" Detected multi-location CSV with countries: {', '.join(country_columns)}")
                    
                    # Determine which countries to use
                    if self.selected_countries:
                        # Filter to only selected countries
                        selected_columns = [col for col in self.selected_countries if col in country_columns]
                        if not selected_columns:
                            print(f" None of the selected countries {self.selected_countries} found in CSV")
                            print(f"Available countries: {country_columns}")
                            return []
                        use_columns = selected_columns
                        print(f" Using selected countries: {', '.join(use_columns)}")
                    else:
                        # Use all available countries
                        use_columns = country_columns
                        print(f" Using all available countries: {', '.join(use_columns)}")
                    
                    # Extract URLs from selected country columns and track availability
                    self.product_country_mapping = {}  # Store which countries each product is available in
                    
                    for row in reader:
                        product_id = row.get('product_id', '')
                        if product_id:
                            # Track availability for this product across all countries
                            product_availability = {}
                            for country in self.available_countries.keys():
                                url = row.get(country, '').strip()
                                product_availability[country] = bool(url)
                            
                            # Add URLs from selected countries
                            for country in use_columns:
                                url = row.get(country, '').strip()
                                if url and url not in product_urls:
                                    product_urls.append(url)
                                    # Store availability info for this URL
                                    self.product_country_mapping[url] = {
                                        'product_id': product_id,
                                        'source_country': country,
                                        'availability': product_availability
                                    }
                                    
                    print(f"📦 Loaded {len(product_urls)} product URLs from {len(use_columns)} countries")
                    
                else:
                    # Single-column CSV format (legacy)
                    print(" Detected single-column CSV format")
                    self.product_country_mapping = {}  # Initialize empty mapping for legacy format
                    
                    for row in reader:
                        # Handle different possible column names
                        url = (row.get('product_url') or row.get('Product URL') or 
                              row.get('url') or row.get('URL') or '').strip()
                        if url and url not in product_urls:
                            product_urls.append(url)
                            # For single URLs, we can't determine availability across countries
                            self.product_country_mapping[url] = {
                                'product_id': None,
                                'source_country': None,
                                'availability': {}
                            }
                    
                    print(f" Loaded {len(product_urls)} product URLs from single-column format")
                
                return product_urls
                        
        except Exception as e:
            print(f"Error loading CSV file: {e}")
            return []
    
    
    async def extract_detailed_product_info(self, url):
        """Extract comprehensive product information from individual product pages"""
        # Determine region from URL or mapping for cookies
        region_code = 'en-US'  # default
        if hasattr(self, 'product_country_mapping') and url in self.product_country_mapping:
            source_country = self.product_country_mapping[url].get('source_country')
            if source_country:
                region_code = source_country
        else:
            # Try to extract region from URL
            region_match = re.search(r'forestmarket\.net/([a-z]{2}-[A-Z]{2})/', url)
            if region_match and region_match.group(1) in self.available_countries:
                region_code = region_match.group(1)

        # Region-specific cookies (based on crawl_fm_url.py)
        cookies = [
            {
                "name": "NEXT_LOCALE",
                "value": region_code,
                "domain": "www.forestmarket.net",
                "path": "/",
            }
        ]

        browser_config = BrowserConfig(
            browser_type="chromium", 
            headless=True,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            cookies=cookies,
            # Speed optimizations
            extra_args=[
                "--no-sandbox",
                "--disable-dev-shm-usage", 
                "--disable-gpu",
                "--disable-images",
                "--disable-extensions",
                "--disable-plugins"
            ]
        )
        
        # Forest Market specific JavaScript automation based on user analysis
        interactive_js = """
        console.log("Starting Forest Market interactive automation...");
        
        // Wait for React components to render (reduced for speed)
        await new Promise(resolve => setTimeout(resolve, 1500));
        
        // Helper function for safer clicking with error handling
        async function clickElement(element, description) {
            if (!element) {
                console.log(`${description}: Element not found`);
                return false;
            }
            
            try {
                element.scrollIntoView({ behavior: 'smooth', block: 'center' });
                await new Promise(resolve => setTimeout(resolve, 200));
                element.click();
                console.log(`${description}: Successfully clicked`);
                await new Promise(resolve => setTimeout(resolve, 500));
                return true;
            } catch (error) {
                console.log(` ${description}: Click failed - ${error.message}`);
                return false;
            }
        }
        
        // Helper function to open Forest Market disclosure sections
        function openDetailsSection(sectionName) {
            console.log(`Looking for section: "${sectionName}"`);
            
            // Find the button/span with matching text in h3 elements
            const button = Array.from(document.querySelectorAll('h3 button, h3 span'))
                                .find(el => el.textContent.trim() === sectionName);
            
            if (!button) {
                console.log(` Section "${sectionName}" not found`);
                return null;
            }
            
            console.log(` Found "${sectionName}" section, clicking...`);
            
            // Click to toggle the disclosure
            button.click();
            
            // Wait for panel to expand and extract items
            setTimeout(() => {
                const panel = button.closest('h3').nextElementSibling;
                if (panel && panel.classList.contains('prose')) {
                    const items = Array.from(panel.querySelectorAll('li'))
                                       .map(li => li.textContent.trim());
                    console.log(` ${sectionName} expanded with ${items.length} items`);
                } else {
                    console.log(` Panel for "${sectionName}" not found or not expanded`);
                }
            }, 1000);
            
            return true;
        }
        
        // 1. Click "Read More" button using exact Forest Market method
        console.log("\\n1. Looking for Read More button...");
        const readMoreBtn = Array.from(document.querySelectorAll('button'))
                                  .find(btn => btn.textContent.trim() === 'Read more');
        
        if (readMoreBtn) {
            console.log(' Found Read More button');
            await clickElement(readMoreBtn, 'Read More button');
            
            // Wait and verify the button text changed (reduced for speed)
            await new Promise(resolve => setTimeout(resolve, 1000));
            const newText = readMoreBtn.textContent.trim();
            console.log(`Button text after click: "${newText}"`);
        } else {
            console.log(' Read More button not found (description might be short)');
        }
        
        // 2. Open "Product Condition" section
        console.log("\\n2. Opening Product Condition section...");
        openDetailsSection('Product Condition');
        await new Promise(resolve => setTimeout(resolve, 1000));
        
        // 3. Open "Shipping & Return" section  
        console.log("\\n3. Opening Shipping & Return section...");
        openDetailsSection('Shipping & Return');
        await new Promise(resolve => setTimeout(resolve, 1000));
        
        // 4. Try to find and expand size/color options (if any)
        console.log("\\n4. Looking for size/color options...");
        const sizeColorElements = Array.from(document.querySelectorAll('*'))
            .filter(el => {
                const text = el.textContent.toLowerCase();
                return (text.includes('size') || text.includes('color')) && 
                       el.tagName.match(/^(BUTTON|SELECT|DIV)$/) &&
                       el.offsetParent !== null;
            });
        
        if (sizeColorElements.length > 0) {
            console.log(`Found ${sizeColorElements.length} potential size/color elements`);
            for (let i = 0; i < Math.min(sizeColorElements.length, 3); i++) {
                await clickElement(sizeColorElements[i], `Size/Color element ${i+1}`);
            }
        } else {
            console.log('No size/color options found');
        }
        
        // Final wait for all content to be fully loaded (reduced for speed)
        await new Promise(resolve => setTimeout(resolve, 1500));
        console.log("\\n Forest Market automation completed successfully!");
        """
        
        instruction = """
        Extract product information from this Forest Market product page. 
        Focus on product title, description, price, currency, discount price, main image, product images, image alt texts, payment method(no need image url jsut the payment method), sizes, colors, seller_name, shipping_details, and return_details.
        Be accurate and extract only what's visible on the page. Do not make any modification of the content. Ignore socail media links.
        """
        
        llm_extraction_strategy = LLMExtractionStrategy(
            llm_config = LLMConfig(provider=os.getenv("MODEL"), api_token=os.getenv("OPENAI_API_KEY"), base_url=os.getenv("BASE_URL")), #get from .env
            schema=FMModel.model_json_schema(),
            extraction_type="schema",
            instruction=instruction,
            chunk_token_threshold=4096,
            overlap_rate=0,
            apply_chunking=False,
            extra_args={"temperature": 1, "max_tokens": 4096},
            verbose=False
        )
        # Define comprehensive extraction schema optimized for Forest Market (React/Next.js)
        extraction_schema = {
            "name": "Forest Market Product Details",
            "baseSelector": "body",
            "fields": [
                # Basic product information - React app uses h1-h3 for titles
                {"name": "product_title", "selector": "h1, h2, [data-testid*='title'], [data-testid*='product'], main h1, main h2", "type": "text"},
                {"name": "product_description", "selector": "p, div p, .prose p, [class*='description'], [data-testid*='description'], main p", "type": "text", "multiple": True},
                
                # Price information - look for currency symbols and numbers
                {"name": "price", "selector": "[data-testid*='price'], span:contains('$'), div:contains('$'), [class*='price']", "type": "text"},
                {"name": "price_amount", "selector": "span[class*='price'], div[class*='price'], [data-testid*='amount']", "type": "text"},
                {"name": "currency", "selector": "[class*='currency'], [data-testid*='currency']", "type": "text"},
                {"name": "discount_price", "selector": "[class*='discount'], [class*='sale'], [data-testid*='discount']", "type": "text"},
                
                # Images - React apps often use img tags in various containers
                {"name": "main_image", "selector": "img[src*='product'], img[alt*='product'], main img, [class*='image'] img", "type": "attribute", "attribute": "src"},
                {"name": "product_images", "selector": "img[src*='http'], img[src*='data:'], picture img, figure img", "type": "attribute", "attribute": "src", "multiple": True},
                {"name": "image_alts", "selector": "img[alt]", "type": "attribute", "attribute": "alt", "multiple": True},
                
                # Brand and category information
                {"name": "brand", "selector": "[data-testid*='brand'], [class*='brand'], span[class*='vendor'], a[href*='brand']", "type": "text"},
                {"name": "category", "selector": "[data-testid*='category'], [class*='category'], nav a, [class*='breadcrumb'] a", "type": "text"},
                {"name": "breadcrumbs", "selector": "nav a, [class*='breadcrumb'] a, [role='navigation'] a", "type": "text", "multiple": True},
                
                # Product variants - sizes, colors, options
                {"name": "sizes", "selector": "[data-testid*='size'], [class*='size'] button, [class*='size'] span, select option", "type": "text", "multiple": True},
                {"name": "colors", "selector": "[data-testid*='color'], [class*='color'] button, [class*='color'] span", "type": "text", "multiple": True},
                {"name": "variants", "selector": "[role='button'], [class*='option'] button, [class*='variant'], button[data-testid]", "type": "text", "multiple": True},
                
                # Availability and stock
                {"name": "availability", "selector": "[data-testid*='stock'], [class*='stock'], [class*='available'], span:contains('available'), div:contains('stock')", "type": "text"},
                {"name": "in_stock", "selector": "[class*='in-stock'], span:contains('in stock'), div:contains('available')", "type": "text"},
                
                # Seller information
                {"name": "seller_name", "selector": "[data-testid*='seller'], [class*='seller'], [class*='vendor'], a[href*='seller'], a[href*='shop']", "type": "text"},
                {"name": "seller_info", "selector": "[class*='seller'] span, [class*='vendor'] div, [data-testid*='shop']", "type": "text", "multiple": True},
                {"name": "rating", "selector": "[data-testid*='rating'], [class*='rating'], [class*='star'], span:contains('★')", "type": "text"},
                
                # Interactive content (after JS execution)
                {"name": "expanded_description", "selector": ".prose div, [class*='expanded'], [class*='full-description']", "type": "text", "multiple": True},
                {"name": "condition_details", "selector": "[class*='condition'] div, [data-testid*='condition'], h3:contains('Condition') + div", "type": "text", "multiple": True},
                {"name": "shipping_details", "selector": "[class*='shipping'] div, [data-testid*='shipping'], h3:contains('Shipping') + div", "type": "text", "multiple": True},
                {"name": "return_details", "selector": "[class*='return'] div, [data-testid*='return'], h3:contains('Return') + div", "type": "text", "multiple": True},
                
                # Payment and purchasing
                {"name": "payment_methods", "selector": "[class*='payment'], [data-testid*='payment'], [class*='checkout'] div", "type": "text", "multiple": True},
                {"name": "buttons", "selector": "button, [role='button'], a[class*='button']", "type": "text", "multiple": True},
                
                # All headings for structure understanding
                {"name": "all_headings", "selector": "h1, h2, h3, h4, h5, h6", "type": "text", "multiple": True},
                
                # All links for navigation context
                {"name": "all_links", "selector": "a[href]", "type": "text", "multiple": True},
                {"name": "link_urls", "selector": "a[href]", "type": "attribute", "attribute": "href", "multiple": True},
                
                # Data attributes that might contain product info
                {"name": "data_testids", "selector": "[data-testid]", "type": "attribute", "attribute": "data-testid", "multiple": True},
                
                # Any text that might contain price information
                {"name": "price_text", "selector": "span:contains('$'), div:contains('$'), p:contains('$')", "type": "text", "multiple": True},
                
                # Meta information
                {"name": "page_title", "selector": "title", "type": "text"},
                {"name": "meta_description", "selector": "meta[name='description']", "type": "attribute", "attribute": "content"}
            ]
        }
        
        # Create extraction strategy
        extraction_strategy = JsonCssExtractionStrategy(extraction_schema, verbose=True)
        
        # Comprehensive product extraction strategy with LLM (optimized for speed)
        detailed_product_config = CrawlerRunConfig(
            exclude_social_media_domains=True,
            wait_for="css:body",
            page_timeout=30000,  # Reduced timeout for speed
            js_code=[interactive_js],  # Add the interactive JavaScript
            extraction_strategy=llm_extraction_strategy,  # Use LLM strategy
        )
        
        async with AsyncWebCrawler(config=browser_config) as crawler:
            try:
                print(f" Extracting detailed product info from: {url}")
                result = await crawler.arun(url=url, config=detailed_product_config)
                
                # Use the same region_code determined earlier for markdown saving
                
                if result and result.extracted_content:
                    try:
                        extracted_data = json.loads(result.extracted_content)
                        if extracted_data:
                            # Handle both list and dictionary responses
                            if isinstance(extracted_data, list):
                                # If it's a list, take the first non-empty item
                                for item in extracted_data:
                                    if item and isinstance(item, dict):
                                        product = self.clean_product_data(item, url)
                                        if product:
                                            return product
                                print(f" No valid product data found in list response for {url}")
                            elif isinstance(extracted_data, dict):
                                # If it's a dictionary, process normally
                                product = self.clean_product_data(extracted_data, url)
                                return product
                            else:
                                print(f" Unexpected data type for {url}: {type(extracted_data)}")
                    except json.JSONDecodeError as e:
                        print(f"JSON decode error for {url}: {e}")
                
                    
            except Exception as e:
                print(f" Error extracting detailed info from {url}: {e}")
                self.failed_urls.append({"url": url, "error": str(e)})
                
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
                    if cleaned_value and cleaned_value not in ['null', 'undefined', 'None', '']:
                        product[key] = cleaned_value
        
        # Extract product ID from URL if not found
        if 'product_id' not in product:
            product_id_match = re.search(r'/product/([^/?]+)', url)
            if product_id_match:
                product['product_id'] = product_id_match.group(1)
        
        # Add country availability information
        if hasattr(self, 'product_country_mapping') and url in self.product_country_mapping:
            mapping_info = self.product_country_mapping[url]
            
            # Add source country information
            if mapping_info.get('source_country'):
                product['source_country'] = mapping_info['source_country']
            
            # Add availability columns for each country
            availability = mapping_info.get('availability', {})
            for country_code in self.available_countries.keys():
                country_name = self.available_countries[country_code]
                availability_key = f"{country_code}_available"
                product[availability_key] = availability.get(country_code, False)
        
        return product
    
    
    async def crawl_all_detailed_products(self, max_products=None, start_index=0, concurrent_limit=2):
        """Crawl product URLs for detailed information with controlled parallelism"""
        print("Starting detailed Forest Market product crawler...")
        
        # Load URLs from CSV 
        if self.input_csv:
            product_urls = self.load_product_urls_from_csv()
        else:
            print("No input CSV provided")
            return []
            
        if not product_urls:
            print(" No product URLs found to crawl")
            return []
            
        # Apply limits if specified
        if start_index > 0:
            product_urls = product_urls[start_index:]
            print(f"Starting from index {start_index}")
            
        if max_products:
            product_urls = product_urls[:max_products]
            print(f"Limited to {max_products} products")
            
        print(f" Found {len(product_urls)} product URLs to crawl")
        print(f" Using {concurrent_limit} concurrent workers")
        
        # Process URLs in parallel with controlled concurrency
        semaphore = asyncio.Semaphore(concurrent_limit)
        
        async def process_single_url(url, index):
            async with semaphore:
                print(f" Processing product {index+1}/{len(product_urls)}: {url}")
                
                # Add small delay to spread out requests
                await asyncio.sleep(index * 0.2)  # Stagger start times
                
                product = await self.extract_detailed_product_info(url)
                if product:
                    title = product.get('product_title', 'Unknown')
                    print(f" ✅ Successfully extracted: {title}")
                    return product
                else:
                    print(f" ❌ Failed to extract product from {url}")
                    return None
        
        # Create tasks for all URLs
        tasks = [process_single_url(url, i) for i, url in enumerate(product_urls)]
        
        # Execute all tasks concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        for result in results:
            if isinstance(result, Exception):
                print(f" ⚠️ Task failed with exception: {result}")
            elif result:
                self.products.append(result)
                
        print(f" Total detailed products extracted: {len(self.products)}")
        print(f" Failed URLs: {len(self.failed_urls)}")
        return self.products
    

    async def crawl_single_url(self, url):
        """Crawl a single product URL for detailed information"""
        print(f"Starting single URL crawl for: {url}")
        
        # Initialize product_country_mapping for single URL
        if not hasattr(self, 'product_country_mapping'):
            self.product_country_mapping = {}
        
        # Extract product ID from URL if possible
        product_id_match = re.search(r'/product/([^/?]+)', url)
        product_id = product_id_match.group(1) if product_id_match else None
        
        # Determine region from URL
        region_match = re.search(r'forestmarket\.net/([a-z]{2}-[A-Z]{2})/', url)
        source_country = region_match.group(1) if region_match and region_match.group(1) in self.available_countries else 'en-US'
        
        # Store URL mapping for single URL
        self.product_country_mapping[url] = {
            'product_id': product_id,
            'source_country': source_country,
            'availability': {source_country: True}
        }
        
        # Crawl the product
        product = await self.extract_detailed_product_info(url)
        
        if product:
            self.products.append(product)
            print(f" ✅ Successfully extracted: {product.get('product_title', 'Unknown')}")
            return product
        else:
            print(f" ❌ Failed to extract product from {url}")
            return None

    def save_to_json(self, filename="forest_market_detailed_products.json"):
        """Save extracted products to JSON file"""
        if not self.products:
            print("No products to save")
            return
            
        # Prepare data for JSON serialization
        json_data = {
            "metadata": {
                "total_products": len(self.products),
                "failed_urls": len(self.failed_urls),
                "extraction_timestamp": datetime.now().isoformat(),
                "input_csv": self.input_csv,
                "selected_countries": self.selected_countries
            },
            "products": self.products,
            "failed_urls": self.failed_urls if self.failed_urls else []
        }
        
        with open(filename, 'w', encoding='utf-8') as jsonfile:
            json.dump(json_data, jsonfile, indent=2, ensure_ascii=False)
        
        print(f" Saved {len(self.products)} detailed products to {filename}")


async def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Detailed Forest Market Product Crawler',
        epilog="""
Examples:
  # Crawl from CSV file
  %(prog)s --input ../fm_data/fm_url_20240129_143052.csv
  %(prog)s --input ../fm_data/fm_url_20240129_143052.csv --countries en-US en-SG
  %(prog)s --input ../fm_data/fm_url_20240129_143052.csv --countries en-US --max-products 10
  %(prog)s --input ../fm_data/fm_url_20240129_143052.csv --output products.json
  
  # Crawl single URL
  %(prog)s --url "https://www.forestmarket.net/en-US/product/ABC123"
  %(prog)s --url "https://www.forestmarket.net/product/XYZ789" --output single_product.json
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument('--input', help='Input CSV file with product URLs (supports both single-column and multi-location formats)')
    parser.add_argument('--url', help='Single product URL to crawl (alternative to --input)')
    parser.add_argument('--output', help='Output JSON filename (default: fm_data/json/fm_detail_{timestamp}.json)')
    parser.add_argument('--countries', nargs='+', 
                       choices=['en-US', 'en-SG', 'en-HK', 'en-KR', 'en-JP'],
                       help='Select specific countries from multi-location CSV (e.g., en-US en-SG). If not specified, uses all available countries.')
    parser.add_argument('--max-products', type=int, help='Maximum number of products to crawl')
    parser.add_argument('--start-index', type=int, default=0, help='Starting index for crawling')
    parser.add_argument('--concurrent', type=int, default=2, help='Number of concurrent workers (default: 2, max recommended: 3)')
    
    args = parser.parse_args()
    
    # Validate arguments
    if not args.input and not args.url:
        parser.error("Either --input (CSV file) or --url (single URL) must be provided")
    
    if args.input and args.url:
        parser.error("Cannot use both --input and --url at the same time. Choose one.")
    
    crawler = DetailedForestMarketCrawler(input_csv=args.input, selected_countries=args.countries)
    
    # Handle single URL vs CSV input
    if args.url:
        print("Single URL mode selected")
        products = [await crawler.crawl_single_url(args.url)]
        products = [p for p in products if p is not None]  # Filter out None results
    else:
        print("CSV input mode selected")
        products = await crawler.crawl_all_detailed_products(
            max_products=args.max_products,
            start_index=args.start_index,
            concurrent_limit=args.concurrent
        )
    
    if products:
        # Generate default filename if not provided
        if not args.output:
            # Create directory if it doesn't exist
            os.makedirs('fm_data/json', exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f'fm_data/json/fm_detail_{timestamp}.json'
        else:
            filename = args.output
            # Ensure directory exists for custom filename
            custom_dir = os.path.dirname(filename)
            if custom_dir and not os.path.exists(custom_dir):
                os.makedirs(custom_dir, exist_ok=True)
        
        # Save to JSON 
        crawler.save_to_json(filename)
        
        print(f"\n Successfully extracted detailed information for {len(products)} products!")
        
        print("\n Sample detailed product information:")
        for i, product in enumerate(products[:2]):
            print(f"\n📦 Product {i+1}:")
            for key, value in product.items():
                if value and key not in ['crawled_at', 'url']:
                    if isinstance(value, list):
                        print(f"  {key}: {', '.join(map(str, value[:3]))}{'...' if len(value) > 3 else ''}")
                    else:
                        display_value = str(value)[:100] + '...' if len(str(value)) > 100 else str(value)
                        print(f"  {key}: {display_value}")
    else:
        print(" No products found.")


if __name__ == "__main__":
    asyncio.run(main())