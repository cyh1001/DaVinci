from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig
import csv

async def main():

    res = []

    base_browser = BrowserConfig(
    browser_type="chromium",
    headless=False,
    text_mode=True,
    viewport_width=1920,
    viewport_height=1080,
    cookies=[
        {
            "name": "NEXT_LOCALE",
            "value": "en-US",
            "domain": "www.forestmarket.net",
            "path": "/",
        }
    ]
    )

    run_cfg = CrawlerRunConfig(
            wait_until="networkidle",
            wait_for="a[href]",
            js_code=[
                """
                await new Promise(r=>setTimeout(r,2000));
                
                for(let i=0;i<15;i++){ 
                    let viewMoreButton = null;
                    const buttons = document.querySelectorAll('button');
                    
                    for(let btn of buttons) {
                        const text = (btn.innerText || btn.textContent || '').trim().toLowerCase();
                        if(text === 'view more') {
                            viewMoreButton = btn;
                            break;
                        }
                    }
                    
                    if(viewMoreButton && !viewMoreButton.disabled) {
                        const rect = viewMoreButton.getBoundingClientRect();
                        if(rect.width > 0 && rect.height > 0) {
                            viewMoreButton.click();
                            await new Promise(r=>setTimeout(r,2000));
                        }
                    }
                    
                    window.scrollBy(0, window.innerHeight);
                    await new Promise(r=>setTimeout(r,2000));
                }
                """
            ],
            simulate_user=True,
            magic=True,
            page_timeout=300_000,
            wait_for_timeout=300_000,
        )

    async with AsyncWebCrawler(config=base_browser) as crawler:
        result = await crawler.arun("https://www.forestmarket.net/", config=run_cfg)
        
        if result.success:
            internal_links = result.links.get("internal", [])
            external_links = result.links.get("external", [])
            print(f"\nFound {len(internal_links)} internal links.")
            print(f"Found {len(external_links)} external links.")
            print(f"Found {len(result.media)} media items.")

            for ex_link in external_links:
                print(ex_link["href"])

            if internal_links:  
                for link in internal_links:
                    url = link["href"]
                    if "product" in url:
                        res.append(url)

            with open("forestmarket_dull_product_links.csv", "w", newline="", encoding="utf-8") as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(["product_url"])
                for url in res:
                    writer.writerow([url])
            print(f"Saved {len(res)} product links to forestmarket_product_links.csv")
        
        else:
            print("Crawl failed:", result.error_message)

# To run the async function
import asyncio
asyncio.run(main())