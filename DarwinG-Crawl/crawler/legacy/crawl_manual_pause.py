import asyncio
import csv
import re
from playwright.async_api import async_playwright
from urllib.parse import urljoin, urlparse
import logging
from datetime import datetime

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ForestMarketScraper:
    def __init__(self, headless=True):
        """Initialize the scraper with Playwright"""
        self.base_url = "https://www.forestmarket.net/"
        self.product_links = set()  # Use set to avoid duplicates
        self.headless = headless
        self.page = None
        self.browser = None
        
    async def init_browser(self):
        """Initialize browser and page"""
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=self.headless,
            args=[
                '--no-sandbox',
                '--disable-dev-shm-usage',
                '--disable-gpu',
                '--window-size=1920,1080',
                '--disable-web-security',
                '--disable-features=VizDisplayCompositor',
                '--ignore-certificate-errors',
                '--ignore-ssl-errors',
                '--ignore-certificate-errors-spki-list',
                '--ignore-certificate-errors-ssl',
                '--allow-running-insecure-content',
                '--disable-extensions',
                '--no-first-run',
                '--disable-default-apps',
                '--disable-background-timer-throttling',
                '--disable-backgrounding-occluded-windows',
                '--disable-renderer-backgrounding'
            ]
        )
        
        # Create context with user agent
        # context = await self.browser.new_context(
        #     user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        #     viewport={'width': 1920, 'height': 1080}
        # )
        # context = await self.browser.new_context(
        #     locale="en-US",                            # sets Accept-Language for HTML requests
        #     timezone_id="America/New_York",             # optional, for JS-based date/time logic
        #     extra_http_headers={"Accept-Language": "en-US,en;q=0.9"}
        # )

        context = await self.browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            locale="en-US",
            extra_http_headers={
                "Accept-Language": "en-US,en;q=0.9",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Encoding": "gzip, deflate, br",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1"
            }
        )
        
        
        self.page = await context.new_page()
        
        # Intercept and block redirects to locale-specific URLs
        await self.page.route("**/en-SG/**", lambda route: route.abort())
        await self.page.route("**/en-US/**", lambda route: route.abort())
        await self.page.route("**/en-GB/**", lambda route: route.abort())
        
        # Set longer timeout for slow loading
        self.page.set_default_timeout(300000)
        
    async def navigate_to_base_url(self):
        """Navigate to the base URL and wait for manual region change"""
        logger.info(f"Navigating to {self.base_url}")
        
        try:
            await self.page.goto(self.base_url, wait_until='networkidle', timeout=300_000)
            await asyncio.sleep(2)
            
            current_url = self.page.url
            logger.info(f"Page loaded at: {current_url}")
            
            # Pause for manual intervention
            print("\n" + "="*60)
            print("MANUAL INTERVENTION REQUIRED")
            print("="*60)
            print(f"Browser is now open at: {current_url}")
            print("Please manually change the region to US in the browser")
            print("Press Enter when you're ready to continue scraping...")
            print("="*60)
            
            # Wait for user input
            input()
            
            # Get the current URL after manual changes
            current_url = self.page.url
            logger.info(f"Continuing with URL: {current_url}")
            
        except Exception as e:
            logger.error(f"Error navigating to base URL: {e}")
            raise
        
    async def find_product_links(self):
        """Find all product links on the current page"""
        try:
            current_count = len(self.product_links)
            
            # Wait for page to be fully loaded
            await self.page.wait_for_load_state('networkidle')
            
            # Get all links on the page
            links = await self.page.query_selector_all('a[href]')
            
            for link in links:
                try:
                    href = await link.get_attribute('href')
                    if href:
                        # Convert relative URLs to absolute URLs
                        if href.startswith('/'):
                            href = urljoin(self.base_url, href)
                        elif not href.startswith('http'):
                            continue
                            
                        if self.is_valid_product_link(href):
                            self.product_links.add(href)
                except Exception:
                    continue
            
            new_count = len(self.product_links)
            logger.info(f"Found {new_count - current_count} new product links (Total: {new_count})")
            
        except Exception as e:
            logger.error(f"Error finding product links: {e}")
    
    def is_valid_product_link(self, url):
        """Check if a URL is likely a product link"""
        if not url or not url.startswith(self.base_url):
            return False
            
        # Skip common non-product pages
        skip_patterns = [
            '/category', '/categories', '/search', '/login', '/register', '/cart', '/checkout',
            '/about', '/contact', '/privacy', '/terms', '/faq', '/help',
            '/blog', '/news', '/support', '/account', '/profile', '/user',
            '/admin', '/api/', '/static/', '/assets/',
            '.jpg', '.png', '.gif', '.pdf', '.css', '.js', '.ico',
            '#', 'javascript:', 'mailto:', 'tel:', '/en-SG'
        ]
        
        url_lower = url.lower()
        for pattern in skip_patterns:
            if pattern in url_lower:
                return False
                
        # Look for product indicators
        product_indicators = [
            '/product', '/item', '/p/', '/goods', '/shop/', '/store/'
        ]
        
        for indicator in product_indicators:
            if indicator in url_lower:
                return True
                
        # Check if it looks like a product detail page
        parsed = urlparse(url)
        path_parts = [part for part in parsed.path.strip('/').split('/') if part]
        
        # Skip if it's clearly a category or listing page
        if any(part in ['category', 'categories', 'page', 'tag', 'tags'] for part in path_parts):
            return False
            
        # If the URL has parameters that might indicate a product
        if parsed.query and any(param in parsed.query.lower() for param in ['id=', 'product=', 'item=']):
            return True
            
        # If it's a path with what looks like a product identifier
        if len(path_parts) >= 1:
            last_part = path_parts[-1]
            # Check if last part looks like a product slug or ID
            if re.match(r'^[a-zA-Z0-9-_]+$', last_part) and len(last_part) > 2:
                return True
                
        return False
    
    async def click_view_more(self):
        """Click the 'View More' button if it exists"""
        try:
            # First try the exact button selector you provided
            view_more_selector = 'button.rounded-full.bg-green-500:has-text("View More")'
            
            # Wait for the button to be visible
            await self.page.wait_for_selector(view_more_selector, timeout=5000)
            
            # Check if button is enabled and visible
            button = await self.page.query_selector(view_more_selector)
            if button:
                is_enabled = await button.is_enabled()
                is_visible = await button.is_visible()
                
                if is_enabled and is_visible:
                    # Scroll to button
                    await button.scroll_into_view_if_needed()
                    await asyncio.sleep(1)
                    
                    # Click the button
                    await button.click()
                    logger.info("Clicked 'View More' button")
                    
                    # Wait for content to load
                    await asyncio.sleep(3)
                    await self.page.wait_for_load_state('networkidle')
                    return True
                else:
                    logger.info("'View More' button found but not clickable")
                    return False
            
        except Exception:
            # Try alternative selectors
            alternative_selectors = [
                'button:has-text("View More")',
                'button:has-text("Load More")',
                'button:has-text("Show More")',
                'a:has-text("View More")',
                '[data-testid*="load-more"]',
                '[data-testid*="view-more"]',
                '.load-more',
                '.view-more'
            ]
            
            for selector in alternative_selectors:
                try:
                    await self.page.wait_for_selector(selector, timeout=2000)
                    button = await self.page.query_selector(selector)
                    
                    if button and await button.is_enabled() and await button.is_visible():
                        await button.scroll_into_view_if_needed()
                        await asyncio.sleep(1)
                        await button.click()
                        logger.info(f"Clicked alternative 'View More' button: {selector}")
                        await asyncio.sleep(3)
                        await self.page.wait_for_load_state('networkidle')
                        return True
                        
                except Exception:
                    continue
                    
        logger.info("No clickable 'View More' button found")
        return False
    
    async def scrape_all_products(self, max_clicks=50):
        """Scrape all products by repeatedly clicking 'View More'"""
        await self.init_browser()
        
        try:
            await self.navigate_to_base_url()
            
            # Initial scan for products
            await self.find_product_links()
            
            clicks = 0
            consecutive_no_change = 0
            previous_count = 0
            
            while clicks < max_clicks and consecutive_no_change < 3:
                logger.info(f"Attempt {clicks + 1} to click 'View More'")
                
                if not await self.click_view_more():
                    logger.info("No more 'View More' buttons found. Scraping complete.")
                    break
                
                # Scan for new products after clicking
                await self.find_product_links()
                
                current_count = len(self.product_links)
                if current_count == previous_count:
                    consecutive_no_change += 1
                    logger.info(f"No new products found. Consecutive no-change count: {consecutive_no_change}")
                else:
                    consecutive_no_change = 0
                    
                previous_count = current_count
                clicks += 1
                
                # Small delay between clicks
                await asyncio.sleep(2)
            
            logger.info(f"Scraping completed. Total product links found: {len(self.product_links)}")
            
        except Exception as e:
            logger.error(f"Error during scraping: {e}")
        finally:
            await self.cleanup()
            
    async def cleanup(self):
        """Clean up browser resources"""
        if self.browser:
            await self.browser.close()
        if hasattr(self, 'playwright'):
            await self.playwright.stop()
    
    def save_to_csv(self, filename=None):
        """Save product links to CSV file"""
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"forest_market_products_{timestamp}.csv"
        
        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(['Product URL'])  # Header
            
            for link in sorted(self.product_links):
                writer.writerow([link])
        
        logger.info(f"Saved {len(self.product_links)} product links to {filename}")
        return filename

async def main():
    """Main function to run the scraper"""
    scraper = ForestMarketScraper(headless=False)  # Set to True for headless mode
    
    try:
        await scraper.scrape_all_products(max_clicks=50)
        filename = scraper.save_to_csv()
        print(f"Scraping completed! Results saved to {filename}")
        print(f"Total products found: {len(scraper.product_links)}")
        
        # Print first few links as preview
        if scraper.product_links:
            print("\nFirst 5 product links:")
            for i, link in enumerate(sorted(scraper.product_links)[:5]):
                print(f"{i+1}. {link}")
                
    except Exception as e:
        logger.error(f"Scraping failed: {e}")

if __name__ == "__main__":
    asyncio.run(main())

# Installation requirements:
# pip install playwright
# playwright install chromium