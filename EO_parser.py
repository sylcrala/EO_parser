"""
A script meant to scrape all executive orders directly from the white house website, and then parse them into an easily searchable dataframe
"""
from playwright.async_api import async_playwright
from playwright_stealth import Stealth
import time
import random
import asyncio
import signal
import sys
from bs4 import BeautifulSoup

class Scraper:
    def __init__(self):
        self.debug = True

        self.foundation_url = "https://www.whitehouse.gov/presidential-actions/executive-orders/"
        self.selected_url = None 
        self.eo_links = []
        self.eo_data = []

        if self.debug:
            signal.signal(signal.SIGINT, self.signal_handler)
            signal.signal(signal.SIGTERM, self.signal_handler)

        try:
            asyncio.run(self.launch_scraper())
        except KeyboardInterrupt:
            print("\n!!! KeyboardInterrupt caught in main !!!")
            self.save_progress()
        except Exception as e:
            print("An error occurred while scraping EO links: ", e)
            import traceback
            traceback.print_exc()
            self.save_progress()

    def signal_handler(self, signum, frame):
        print(f"\n!!! Received signal {signum} from external source !!!")
        print(f"Frame: {frame}")
        self.save_progress()
        sys.exit(1)

    def save_progress(self):
        print(f"Saving progress: {len(self.eo_data)} EOs scraped so far")
        # Add file saving here later if needed

    async def launch_scraper(self):
        """Launches a playwright browser instance for scraping"""
        async with Stealth().use_async(async_playwright()) as p:
            context = await p.chromium.launch_persistent_context(
                user_data_dir = "./tmp/playwright_profile",
                headless=False if self.debug else True,  
                args = [
                    '--disable-blink-features=AutomationControlled',
                    '--disable-dev-shm-usage',
                    '--no-sandbox',
                    '--disable-web-security',
                    '--disable-features=VizDisplayCompositor',
                    '--disable-features=IsolateOrigins,site-per-process',
                    '--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36'
                ],
                viewport={"width": 1280, "height": 800},
                ignore_https_errors=True
            )

            page = context.pages[0]

            # Block tracking requests to avoid detection
            await page.route('**/*analytics*', lambda route: route.abort())
            await page.route('**/*gtm*', lambda route: route.abort())
            await page.route('**/*google*', lambda route: route.abort())

            try:
                await self.scrape_eo_links(page)
            except Exception as e:
                print("An error occurred while scraping EO links: ", e)
                import traceback
                traceback.print_exc()
                print("Succesfully scraped data: ", len(self.eo_data))

            await context.close()
        
        self.print_eo_data()
        print("Total EO links scraped: ", len(self.eo_links))

    async def scrape_eo_links(self, page):
        """
        Scrapes all executive order links from the white house website
        """
        self.selected_url = self.foundation_url # select foundation url
        current_page = 1
        total_pages = 1 # initialize total pages to 1, will be updated after

        while current_page <= total_pages:
            if current_page > total_pages:
                break

            if current_page > 1:
                page_delay = random.randint(3, 7)
                await asyncio.sleep(page_delay)  # Sleep to avoid overwhelming the server

            try:
                print(f"Scraping page {current_page} of {total_pages}...")
                # navigate to page
                await page.goto(self.selected_url, wait_until="domcontentloaded", timeout=10000)

                # wait for content to load
                await page.wait_for_selector("div.wp-block-query", timeout=10000)
                content = await page.content()

                soup = BeautifulSoup(content, "html.parser")
            except Exception as e:
                print(f"An error occurred while scraping page {current_page}: {e}")
                current_page += 1
                continue

            # assign total pages
            if current_page == 1:
                pagination_div = soup.find("div", class_="wp-block-query-pagination-numbers")
                if pagination_div:
                    final_page = pagination_div.find_all("a", "page-numbers")[-1]
                    total_pages = int(final_page.text)
                    
            found_links = []
            for div in soup.find_all("div", "wp-block-query is-layout-flow wp-block-query-is-layout-flow"):  # find the div containing the list of executive orders
                for item in div.find_all("li"):
                    potential_links = [a for a in item.find_all("a") if a.get("href")]
                    for link in potential_links:
                        if link.get("href") == self.foundation_url or link.get("href") == "https://www.whitehouse.gov/presidential-actions/":
                            continue # skip the foundation url and general presidential actions url
                        if link.get("href") in self.eo_links:
                            continue # skip duplicates
                        link = link.get("href")
                        found_links.append(link)
                        self.eo_links.append(link)

            soup.decompose()  

            # process individual EO links to pull and populate data
            for i, url in enumerate(found_links, 1):
                try:
                    print(f"Processing EO {i} on page {current_page}: {url}")
                    await self.get_eo_data(page, url)
                except Exception as e:
                    print(f"An error occurred while processing EO {i} on page {current_page}: {e}")
                    continue

            # move to the next page
            current_page += 1
            self.selected_url = f"{self.foundation_url}page/{current_page}/"


    async def get_eo_data(self, page, url):
        """
        Scrapes the executive order data from a given url
        """
        try:
            await asyncio.sleep(2)

            # navigate to EO page
            await page.goto(url, wait_until="domcontentloaded", timeout=10000)

            # wait for content to load
            await page.wait_for_selector("h1.wp-block-whitehouse-topper__headline", timeout=10000)
            
            # get content and create soup
            content = await page.content()
            soup = BeautifulSoup(content, "html.parser")

            title = soup.find("h1", class_="wp-block-whitehouse-topper__headline").text
            date = soup.find("time").text
            raw_content = [p.text for p in soup.find_all("p")]
            content = "\n".join(raw_content)

            soup.decompose()  
            print(f"Scraped data for {url}: Title: {title}, Date: {date}")  
            
            self.eo_data.append({
                "title": title,
                "date": date,
                "content": content,
                "url": url
            })
        except Exception as e:
            print(f"An error occurred while scraping data for {url}: {e}")
            self.eo_data.append({
                "title": "N/A",
                "date": "N/A",
                "content": "N/A",
                "url": url
            })

    def print_eo_data(self):
        """
        Prints the stored executive order data
        """
        for eo in self.eo_data:
            print("\nTitle: ", eo["title"])
            print("Date: ", eo["date"])
            print("Content: ", eo["content"])
            print("URL: ", eo["url"])


if __name__ == "__main__":
    Scraper()
