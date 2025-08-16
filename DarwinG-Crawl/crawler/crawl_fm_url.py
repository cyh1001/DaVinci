from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig
import csv
import asyncio
import argparse
import re
from datetime import datetime
from urllib.parse import urlparse
import logging
import os

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ForestMarketMultiLocationCrawler:
    def __init__(self):
        """Initialize the multi-location Forest Market URL crawler"""
        self.base_url = "https://www.forestmarket.net"
        
        # Available locations/regions (only the 5 supported countries)
        self.available_locations = {
            'en-US': '/en-US',     # United States
            'en-SG': '/en-SG',     # Singapore  
            'en-HK': '/en-HK',     # Hong Kong
            'en-KR': '/en-KR',     # South Korea
            'en-JP': '/en-JP',     # Japan
        }
        
        # Country name mapping for user-friendly input
        self.country_name_mapping = {
            # Full country names
            'united states': 'en-US',
            'usa': 'en-US',
            'us': 'en-US',
            'america': 'en-US',
            'singapore': 'en-SG',
            'hong kong': 'en-HK',
            'hongkong': 'en-HK',
            'hk': 'en-HK',
            'south korea': 'en-KR',
            'korea': 'en-KR',
            'south': 'en-KR',
            'japan': 'en-JP',
            'jp': 'en-JP',
            # Locale codes (case insensitive)
            'en-us': 'en-US',
            'en-sg': 'en-SG', 
            'en-hk': 'en-HK',
            'en-kr': 'en-KR',
            'en-jp': 'en-JP',
        }
        
        # Store results: {product_id: {location: url}}
        self.product_data = {}
        self.failed_locations = []
        
    def get_view_more_js(self):
        """JavaScript code to handle 'View More' button clicking"""
        return """
        console.log("Starting View More automation...");
        
        // Wait for initial page load
        await new Promise(r=>setTimeout(r,3000));
        
        for(let i=0; i<20; i++) { 
            let viewMoreButton = null;
            const buttons = document.querySelectorAll('button');
            
            // Find View More button
            for(let btn of buttons) {
                const text = (btn.innerText || btn.textContent || '').trim().toLowerCase();
                if(text === 'view more' || text === 'load more' || text === 'show more') {
                    viewMoreButton = btn;
                    break;
                }
            }
            
            // Click button if found and enabled
            if(viewMoreButton && !viewMoreButton.disabled) {
                const rect = viewMoreButton.getBoundingClientRect();
                if(rect.width > 0 && rect.height > 0) {
                    console.log(`Clicking View More button (iteration ${i+1})`);
                    viewMoreButton.scrollIntoView({ behavior: 'smooth', block: 'center' });
                    await new Promise(r=>setTimeout(r,1000));
                    viewMoreButton.click();
                    await new Promise(r=>setTimeout(r,3000));
                } else {
                    console.log(`View More button found but not clickable (iteration ${i+1})`);
                    break;
                }
            } else {
                console.log(`No View More button found (iteration ${i+1})`);
                break;
            }
            
            // Scroll to load more content
            window.scrollBy(0, window.innerHeight);
            await new Promise(r=>setTimeout(r,2000));
        }
        
        console.log("View More automation completed");
        """
    
    def parse_location_input(self, location_inputs):
        """Parse and validate location inputs from user"""
        if not location_inputs:
            # If no input, return all countries
            return list(self.available_locations.keys())
        
        parsed_locations = []
        
        for location_input in location_inputs:
            location_key = location_input.lower().strip()
            
            # Try to find the location in mapping
            if location_key in self.country_name_mapping:
                locale_code = self.country_name_mapping[location_key]
                if locale_code not in parsed_locations:
                    parsed_locations.append(locale_code)
            else:
                logger.warning(f"⚠️ Unknown location: '{location_input}'. Use --list-locations to see available options.")
        
        return parsed_locations
    
    def extract_product_id(self, url):
        """Extract unique product ID from URL"""
        # Pattern: /product/PRODUCT_ID or /en-XX/product/PRODUCT_ID
        match = re.search(r'/product/([^/?#]+)', url)
        if match:
            return match.group(1)
        return None
    
    def is_valid_product_url(self, url):
        """Check if URL is a valid product URL"""
        if not url or not isinstance(url, str):
            return False
            
        # Must contain 'product' and be from forestmarket.net
        if 'product' not in url.lower():
            return False
            
        # Parse URL to check domain
        try:
            parsed = urlparse(url)
            if 'forestmarket.net' not in parsed.netloc:
                return False
        except:
            return False
            
        # Should have a product ID
        product_id = self.extract_product_id(url)
        return product_id is not None
    
    async def crawl_location(self, location_key, location_path):
        """Crawl a specific location for product URLs"""
        logger.info(f"🌍 Crawling location: {location_key}")
        
        # Construct URL for this location
        if location_path:
            target_url = f"{self.base_url}{location_path}"
            locale_value = location_key
        else:
            target_url = self.base_url
            locale_value = "en-US"  # Default locale
        
        # Browser configuration with location-specific settings
        browser_config = BrowserConfig(
            browser_type="chromium",
            headless=True,  # Set to False for debugging
            text_mode=True,
            viewport_width=1920,
            viewport_height=1080,
            cookies=[
                {
                    "name": "NEXT_LOCALE",
                    "value": locale_value,
                    "domain": "www.forestmarket.net",
                    "path": "/",
                }
            ]
        )
        
        # Crawler configuration
        run_cfg = CrawlerRunConfig(
            wait_until="networkidle",
            wait_for="a[href]",
            js_code=[self.get_view_more_js()],
            simulate_user=True,
            magic=True,
            page_timeout=300_000,
            wait_for_timeout=300_000,
        )
        
        product_urls = []
        
        try:
            async with AsyncWebCrawler(config=browser_config) as crawler:
                logger.info(f"📄 Loading page: {target_url}")
                result = await crawler.arun(target_url, config=run_cfg)
                
                if result.success:
                    internal_links = result.links.get("internal", [])
                    logger.info(f"🔗 Found {len(internal_links)} internal links for {location_key}")
                    
                    # Extract product URLs
                    for link in internal_links:
                        url = link.get("href", "")
                        if self.is_valid_product_url(url):
                            product_urls.append(url)
                    
                    # Remove duplicates while preserving order
                    unique_urls = []
                    seen = set()
                    for url in product_urls:
                        product_id = self.extract_product_id(url)
                        if product_id and product_id not in seen:
                            unique_urls.append(url)
                            seen.add(product_id)
                    
                    logger.info(f"✅ Found {len(unique_urls)} unique product URLs for {location_key}")
                    
                    # Store results
                    for url in unique_urls:
                        product_id = self.extract_product_id(url)
                        if product_id:
                            if product_id not in self.product_data:
                                self.product_data[product_id] = {}
                            self.product_data[product_id][location_key] = url
                    
                    return unique_urls
                    
                else:
                    logger.error(f"❌ Failed to crawl {location_key}: {result.error_message}")
                    self.failed_locations.append({"location": location_key, "error": result.error_message})
                    
        except Exception as e:
            logger.error(f"❌ Error crawling {location_key}: {e}")
            self.failed_locations.append({"location": location_key, "error": str(e)})
        
        return []
    
    async def crawl_multiple_locations(self, selected_locations=None):
        """Crawl multiple locations"""
        # Parse and validate location inputs
        valid_locations = self.parse_location_input(selected_locations)
        
        if not valid_locations:
            logger.error("❌ No valid locations selected")
            return
        
        logger.info(f"🚀 Starting crawl for locations: {', '.join(valid_locations)}")
        
        # Crawl each location sequentially (to be respectful to the server)
        for location_key in valid_locations:
            location_path = self.available_locations[location_key]
            await self.crawl_location(location_key, location_path)
            
            # Rate limiting between locations
            if location_key != valid_locations[-1]:  # Don't wait after the last one
                logger.info("⏳ Waiting 5 seconds before next location...")
                await asyncio.sleep(5)
        
        logger.info(f"🎉 Crawling completed! Found {len(self.product_data)} unique products")
        logger.info(f"📊 Failed locations: {len(self.failed_locations)}")
    
    def save_to_csv(self, filename=None, selected_locations=None):
        """Save results to CSV with regions as columns and product IDs as rows"""
        if not filename:
            # Create default directory if it doesn't exist
            default_dir = "../fm_data"
            os.makedirs(default_dir, exist_ok=True)
            
            # Create filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = os.path.join(default_dir, f"fm_url_{timestamp}.csv")
        else:
            # Ensure directory exists for custom filename
            custom_dir = os.path.dirname(filename)
            if custom_dir and not os.path.exists(custom_dir):
                os.makedirs(custom_dir, exist_ok=True)
        
        if not self.product_data:
            logger.warning("No product data to save")
            return filename
        
        # Determine which locations to include in output
        if selected_locations:
            output_locations = [loc for loc in selected_locations if loc in self.available_locations]
        else:
            # Get all locations that have at least one product
            output_locations = set()
            for product_data in self.product_data.values():
                output_locations.update(product_data.keys())
            output_locations = sorted(list(output_locations))
        
        # Create CSV with product IDs as rows and regions as columns
        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            # Header row: Product ID, then each region
            fieldnames = ['product_id'] + output_locations
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            
            # Data rows
            for product_id in sorted(self.product_data.keys()):
                row = {'product_id': product_id}
                for location in output_locations:
                    url = self.product_data[product_id].get(location, '')
                    row[location] = url
                writer.writerow(row)
        
        # Save failed locations if any
        if self.failed_locations:
            # Ensure failed file goes to same directory as main file
            if filename.startswith('../fm_data/'):
                failed_filename = filename.replace('.csv', '_failed_locations.csv')
            else:
                # Handle custom filename paths
                base_name = os.path.splitext(filename)[0]
                failed_filename = f"{base_name}_failed_locations.csv"
                
            with open(failed_filename, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=['location', 'error'])
                writer.writeheader()
                writer.writerows(self.failed_locations)
            logger.info(f"💾 Saved {len(self.failed_locations)} failed locations to {failed_filename}")
        
        logger.info(f"💾 Saved {len(self.product_data)} products across {len(output_locations)} locations to {filename}")
        return filename
    
    def print_summary(self):
        """Print a summary of the crawled data"""
        if not self.product_data:
            print("❌ No product data found")
            return
        
        print(f"\n📊 CRAWL SUMMARY")
        print(f"=" * 50)
        print(f"🔢 Total unique products: {len(self.product_data)}")
        
        # Count products per location
        location_counts = {}
        for product_data in self.product_data.values():
            for location in product_data.keys():
                location_counts[location] = location_counts.get(location, 0) + 1
        
        print(f"🌍 Products per location:")
        for location in sorted(location_counts.keys()):
            count = location_counts[location]
            print(f"   {location}: {count} products")
        
        # Show sample data
        print(f"\n🔍 Sample products:")
        for i, (product_id, locations) in enumerate(list(self.product_data.items())[:3]):
            print(f"   Product {i+1}: {product_id}")
            for loc, url in locations.items():
                print(f"     {loc}: {url}")
        
        if len(self.product_data) > 3:
            print(f"   ... and {len(self.product_data) - 3} more products")


def main():
    """Main function with command line arguments"""
    parser = argparse.ArgumentParser(
        description='Forest Market Multi-Location URL Crawler',
        epilog="""
Examples:
  %(prog)s                                    # Crawl all countries → ../fm_data/fm_url_YYYYMMDD_HHMMSS.csv
  %(prog)s --locations "United States" Japan  # Crawl US and Japan → ../fm_data/fm_url_YYYYMMDD_HHMMSS.csv
  %(prog)s --locations us singapore          # Crawl US and Singapore → ../fm_data/fm_url_YYYYMMDD_HHMMSS.csv
  %(prog)s --locations en-US en-SG           # Crawl US and Singapore (locale codes) → ../fm_data/fm_url_YYYYMMDD_HHMMSS.csv
  %(prog)s --output my_products.csv          # Custom output filename
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument('--locations', nargs='+', 
                       help='List of countries/locations to crawl. Accepts country names (e.g., "United States", "Japan") or locale codes (e.g., "en-US", "en-JP"). If not specified, crawls all countries.')
    parser.add_argument('--output', help='Output CSV filename (default: ../fm_data/fm_url_YYYYMMDD_HHMMSS.csv)')
    parser.add_argument('--list-locations', action='store_true', help='List available locations and exit')
    
    args = parser.parse_args()
    
    crawler = ForestMarketMultiLocationCrawler()
    
    # List available locations
    if args.list_locations:
        print("🌍 Available locations:")
        print("\nCountry Names (case insensitive):")
        country_examples = [
            ("United States", ["United States", "USA", "US", "America"]),
            ("Singapore", ["Singapore"]),
            ("Hong Kong", ["Hong Kong", "HongKong", "HK"]),
            ("South Korea", ["South Korea", "Korea"]), 
            ("Japan", ["Japan", "JP"])
        ]
        
        for country, examples in country_examples:
            locale_code = crawler.country_name_mapping[examples[0].lower()]
            url = f"https://www.forestmarket.net{crawler.available_locations[locale_code]}"
            print(f"   {country} ({locale_code}): {url}")
            print(f"     Input examples: {', '.join(examples)}")
            print()
        
        print("Locale Codes:")
        for locale_code, path in crawler.available_locations.items():
            url = f"https://www.forestmarket.net{path}"
            print(f"   {locale_code}: {url}")
        return
    
    # Run the crawler
    async def run_crawler():
        try:
            await crawler.crawl_multiple_locations(args.locations)
            
            if crawler.product_data:
                filename = crawler.save_to_csv(args.output, args.locations)
                crawler.print_summary()
                print(f"\n💾 Results saved to: {filename}")
            else:
                print("❌ No products found across all locations")
                
        except Exception as e:
            logger.error(f"Crawling failed: {e}")
    
    # Run the async crawler
    asyncio.run(run_crawler())


if __name__ == "__main__":
    main()