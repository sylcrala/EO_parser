"""
A script meant to scrape all executive orders directly from the white house website, and then parse them into an easily searchable dataframe
"""
from playwright.async_api import async_playwright
from playwright_stealth import Stealth
import sqlite3
import random
import asyncio
import signal
import sys
from os import mkdir
from pathlib import Path
from bs4 import BeautifulSoup
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QTextEdit,
    QLineEdit,
    QLabel,
    QMessageBox,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QScrollArea
)




##*-*## Database classes & methods ##*-*##
class Database:
    def __init__(self):
        """Initializes the SQLite database and creates the executive_orders table"""
        self.db_path = "./data/storage.db"
        self.raw_eo_data = None
        self.added_eos = 0
        Path("./data").mkdir(parents=True, exist_ok=True)

        self.con = sqlite3.connect(self.db_path)
        try:
            self.con.execute("CREATE TABLE executive_orders(id INTEGER PRIMARY KEY, title TEXT, date TEXT, content TEXT, url TEXT)")
        except sqlite3.OperationalError:
            pass  # Table already exists

    def store_eo(self, eo_data):
        """Used for storing data within the database"""
        if self.search_by_title(eo_data["title"]):
            print(f"EO titled '{eo_data['title']}' already exists in the database. Skipping entry.")
            return  # Skip adding duplicate entry based on title

        id = len(self.raw_eo_data) - self.added_eos
        title = eo_data["title"]
        date = eo_data["date"]
        content = eo_data["content"]
        url = eo_data["url"]

        self.con.execute("""
            INSERT INTO executive_orders VALUES
                        (?, ?, ?, ?, ?)
        """, (id, title, date, content, url))

        self.added_eos += 1
        self.con.commit() # commit the new entry to the database

    def view_database(self):
        """Prints out the stored executive orders"""
        cursor = self.con.execute("SELECT * FROM executive_orders")
        for row in cursor:
            id = row[0]
            title = row[1]
            date = row[2]
            content = row[3]
            url = row[4]
            print(f"\nID: {id}\nTitle: {title}\nDate: {date}\nContent: {content}\nURL: {url}\n\n")

    def search_by_id(self, id):
        """Searches the SQLite database for an entry matching the given id"""
        cursor = self.con.execute(f"SELECT * FROM executive_orders WHERE id={id}")
        result = cursor.fetchone()
        return result
    
    def search_by_title(self, title):
        """Searches the SQLite database for an entry matching the given title"""
        cursor = self.con.execute(f"SELECT * FROM executive_orders WHERE title='{title}'")
        result = cursor.fetchone()
        return result


class Viewer(QMainWindow):
    def __init__(self, database):
        self.database = database
        self.setWindowTitle("Executive Orders Database Viewer")
        self.setGeometry(100, 100, 800, 600)

        # setup foundation
        self.foundation_widget = QWidget()
        self.foundation_layout = QVBoxLayout()
        self.foundation_widget.setLayout(self.foundation_layout)
        self.setCentralWidget(self.foundation_widget)

        # top bar for search and actions
        self.top_bar = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Enter criteria...")
        self.search_button = QPushButton("Search")
        self.search_button.clicked.connect(self.perform_search)

        self.top_bar.addWidget(self.search_input, stretch=4)
        self.top_bar.addWidget(self.search_button, stretch=1)
        self.foundation_layout.addLayout(self.top_bar)

        # table for displaying results
        self.results_table = QTableWidget() # table with brief results listed, clicking on a row shows full EO details below

        self.results_table.setColumnCount(3) # id, title, date
        self.results_table.setHorizontalHeaderLabels(["ID", "Title", "Date"])
        self.results_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.results_table.cellDoubleClicked.connect(lambda row, col: self.show_details(self.results_table.item(row, 0).text()))

        self.foundation_layout.addWidget(self.results_table)
        self.populate_table()

        self.show()

    def populate_table(self):
        """Populates the results table with all executive orders from the database"""
        cursor = self.database.con.execute("SELECT id, title, date FROM executive_orders")
        rows = cursor.fetchall()
        self.results_table.setRowCount(len(rows))
        for row_idx, row_data in enumerate(rows):
            for col_idx, item in enumerate(row_data):
                self.results_table.setItem(row_idx, col_idx, QTableWidgetItem(str(item)))

    def show_details(self, id):
        """Shows detailed information about a selected executive order"""
        eo = self.database.search_by_id(id)
        if eo:
            detail_window = DetailViewer(eo)
            detail_window.show()
        else:
            QMessageBox.warning(self, "Not Found", f"No executive order found with ID: {id}")

    def perform_search(self):
        """Executes a requested search using the data within the search bar"""
        criteria = self.search_input.text()
        cursor = self.database.con.execute(f"SELECT id, title, date FROM executive_orders WHERE title LIKE '%{criteria}%' OR date LIKE '%{criteria}%' OR content LIKE '%{criteria}%' OR url LIKE '%{criteria}%' OR id LIKE '%{criteria}%'")
        rows = cursor.fetchall()
        self.results_table.setRowCount(len(rows))
        for row_idx, row_data in enumerate(rows):
            for col_idx, item in enumerate(row_data):
                self.results_table.setItem(row_idx, col_idx, QTableWidgetItem(str(item)))

class DetailViewer(QWidget):
    def __init__(self, eo_data):
        super().__init__() # show as a new window
        self.eo_id = eo_data["id"]
        self.eo_title = eo_data["title"]
        self.eo_date = eo_data["date"]
        self.eo_content = eo_data["content"]
        self.eo_url = eo_data["url"]

        self.setWindowTitle(f"{self.eo_title} - Detailed View")
        self.setGeometry(150, 150, 600, 400)
        
        self.setLayout(QVBoxLayout())

        self.title_label = QLabel(f"<b>Title:</b> {self.eo_title}")
        self.date_label = QLabel(f"<b>Date published/listed:</b> {self.eo_date}")
        self.url_label = QLabel(f"<b>URL:</b> {self.eo_url}")
        self.content_area = QScrollArea()
        self.content_area.setWidgetResizable(True)
        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout()
        self.content_widget.setLayout(self.content_layout)
        self.content_area.setWidget(self.content_widget)
        self.content_header = QLabel("<b>Contents:</b>")
        self.content_text = QTextEdit()
        self.content_text.setReadOnly(True)
        self.content_text.setText(self.eo_content)
        self.content_layout.addWidget(self.content_header)
        self.content_layout.addWidget(self.content_text)

        self.layout().addWidget(self.title_label)
        self.layout().addWidget(self.date_label)
        self.layout().addWidget(self.url_label)
        self.layout().addWidget(self.content_area)


##*-*## Scraping classes & methods ##*-*##
class Scraper:
    def __init__(self, debug=False, safety_delays=True):
        self.debug = debug
        self.safety_delays = safety_delays

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
        
        #self.print_eo_data()
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

            if current_page > 1 and self.safety_delays:
                page_delay = random.randint(2, 5)
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
            if self.safety_delays:
                await asyncio.sleep(1)

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




##*-*## Main execution ##*-*##
def main():
    print("Welcome! The script will now begin scraping executive orders from the White House website; then will launch a GUI viewer that allows you to filter and search the scraped data!")

    scraper = Scraper(debug=True, safety_delays=True)
    database = Database()
    scraped_eos = scraper.eo_data
    database.raw_eo_data = scraped_eos
    for eo in scraped_eos:
        database.store_eo(eo)

    app = QApplication(sys.argv)
    viewer = Viewer(database)
    app.exec()


if __name__ == "__main__":
    main()