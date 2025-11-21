"""
A script meant to scrape all executive orders directly from the white house website, and then parse them into an easily searchable dataframe
"""
__version__ = "1.0.1"
__author__ = "sylcrala"


from playwright.async_api import async_playwright
from playwright_stealth import Stealth
import sqlite3
import random
import asyncio
import datetime
import signal
import sys
from os import mkdir
from pathlib import Path
from bs4 import BeautifulSoup
from PySide6.QtCore import Qt
from PySide6.QtGui import QPalette, QColor
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
    QScrollArea,
    QDialog,
    QStyledItemDelegate
)

##*-*## Configuration settings ##*-*##
config = {

    # Database configuration
    "database_dir": "./data/",
    "database_file": "storage.db",

    # Scraper configuration
    "playwright_tmp_dir": "./tmp/playwright_profile",

    # Debug mode enables the chromium browser window to be visible during scraping
    "debug_mode": False,

    # Safety delays add random delays between requests to avoid bot detection and rate limiting
    "safety_delays": False
}





##*-*## Database classes & methods ##*-*##
class Database:
    def __init__(self):
        """Initializes the SQLite database and creates the executive_orders table"""
        self.db_dir = config["database_dir"]
        self.raw_eo_data = None
        self.added_eos = 0
        Path(self.db_dir).mkdir(parents=True, exist_ok=True)
        self.db_path = f"{self.db_dir}{config['database_file']}"
        self.con = sqlite3.connect(self.db_path, check_same_thread=False)
        try:
            self.con.execute("CREATE TABLE executive_orders(id INTEGER PRIMARY KEY, title TEXT, date TEXT, content TEXT, url TEXT)")
        except sqlite3.OperationalError:
            pass  # Table already exists

    def store_eo(self, eo_data):
        """Used for storing data within the database"""
        if self.search_by_title(eo_data["title"]) or self.search_by_url(eo_data["url"]) or self.check_exists(eo_data["url"]):
            print(f"EO titled '{eo_data['title']}' already exists in the database. Skipping entry.")
            return  # Skip adding duplicate entry based on title

        cursor = self.con.execute("SELECT MAX(id) FROM executive_orders")
        max_id = cursor.fetchone()[0]
        eo_id = (max_id + 1) if max_id is not None else 1
        title = eo_data["title"]
        date = eo_data["date"]
        content = eo_data["content"]
        url = eo_data["url"]

        self.con.execute("""
            INSERT INTO executive_orders VALUES
                        (?, ?, ?, ?, ?)
        """, (eo_id, title, date, content, url))

        self.added_eos += 1
        self.con.commit() # commit the new entry to the database

    def full_database(self):
        """Prints out the stored executive orders"""
        cursor = self.con.execute("SELECT * FROM executive_orders")
        rows = cursor.fetchall()
        return rows

    def search_by_id(self, eo_id):
        """Searches the SQLite database for an entry matching the given id"""
        cursor = self.con.execute(f"SELECT * FROM executive_orders WHERE id=?", (eo_id,))
        result = cursor.fetchone()
        if result:
            return result
        return None
    
    def search_by_title(self, title):
        """Searches the SQLite database for an entry matching the given title"""
        cursor = self.con.execute(f"SELECT * FROM executive_orders WHERE title=?", (title,))
        result = cursor.fetchone()
        if result:
            return result
        return None
    
    def search_by_url(self, url):
        """Searches the SQLite database for an entry matching the given url"""
        cursor = self.con.execute(f"SELECT * FROM executive_orders WHERE url=?", (url,))
        result = cursor.fetchone()
        if result:
            return result
        return None
    
    def get_raw_data_from_title(self, title):
        """Retrieves the raw executive order data based on the given title"""
        for entry in self.raw_eo_data:
            if entry["title"] == title:
                return entry
        return None
    
    def get_formatted_data_from_id(self, eo_id):
        """Retrieves the formatted executive order data based on the given id"""
        cursor = self.con.execute(f"SELECT * FROM executive_orders WHERE id=?", (eo_id,))
        result = cursor.fetchone()
        if result:
            eo_data = {
                "id": result[0],
                "title": result[1],
                "date": result[2],
                "content": result[3],
                "url": result[4]
            }
            return eo_data
        return None

    def check_exists(self, url):
        """Checks if an entry exists within the database based on the given url"""
        if self.search_by_url(url) is not None:
            return True
        return False

    def close(self):
        """Closes the database connection"""
        if self.con:
            self.con.close()


##*-*## GUI classes & methods ##*-*##
class NoElidingDelegate(QStyledItemDelegate):
    """Custom delegate to prevent text eliding in table cells"""
    def paint(self, painter, option, index):
        option.textElideMode = Qt.ElideNone
        super().paint(painter, option, index)


class Viewer(QMainWindow):
    def __init__(self, database):
        super().__init__()
        self.database = database
        self.scraper = None
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
        self.search_input.setPlaceholderText("Enter search criteria...")
        self.search_button = QPushButton("Search")
        self.search_button.clicked.connect(self.perform_search)
        self.search_input.returnPressed.connect(self.perform_search)

        self.clear_button = QPushButton("Clear search results")
        self.clear_button.clicked.connect(self.clear_results)

        self.run_scraper_button = QPushButton("Run Scraper")
        self.run_scraper_button.clicked.connect(self.run_scraper)

        self.top_bar.addWidget(self.search_input, stretch=4)
        self.top_bar.addWidget(self.search_button, stretch=1)
        self.top_bar.addWidget(self.clear_button, stretch=1)
        self.top_bar.addWidget(self.run_scraper_button, stretch=1)
        self.foundation_layout.addLayout(self.top_bar)

        # table for displaying results
        self.results_table = QTableWidget() # table with brief results listed, clicking on a row shows full EO details below

        self.results_table.setColumnCount(3) # id, title, date
        self.results_table.setHorizontalHeaderLabels(["ID", "Title", "Date"])
        self.results_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.results_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.results_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.results_table.setWordWrap(True)
        self.results_table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.results_table.verticalHeader().setVisible(False)
        self.results_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.results_table.setSelectionMode(QTableWidget.SingleSelection)
        self.results_table.setItemDelegate(NoElidingDelegate())  # using custom delegate to manually disable text elision (titles would always show as "..." instead of the actual text)
        self.results_table.cellDoubleClicked.connect(lambda row, col: self.show_details(self.results_table.item(row, 0).text()))
        self.results_table.setSortingEnabled(True)
        #self.results_table.sortItems(2, Qt.DateFormat)

        self.foundation_layout.addWidget(self.results_table)
        self.populate_table()
        self.show()


    def run_scraper(self):
        """Launches the scraper to update the database with new executive orders"""
        try:
            self.scraper = Scraper()
            self.scraper.database = self.database

            scraped_eos = self.scraper.eo_data
            self.database.raw_eo_data = scraped_eos

            for eo in scraped_eos:
                self.database.store_eo(eo)

            QMessageBox.information(self, "Scraper Finished", 
                f"The scraper has finished running. Added {self.database.added_eos} new executive orders to the database.")
            self.database.added_eos = 0  # reset counter
            self.populate_table()
        except Exception as e:
            QMessageBox.critical(self, "Scraper Error", f"An error occurred while running the scraper: {e}")

    def clear_results(self):
        """Clears the results table and repopulates it with all executive orders"""
        self.results_table.setRowCount(0)
        self.search_input.clear()
        self.populate_table()

    def populate_table(self):
        """Populates the results table with all executive orders from the database"""
        rows = self.database.full_database()
        if not rows:
            self.results_table.setRowCount(0)
            return
        
        self.results_table.setRowCount(len(rows))
        for row_idx, row_data in enumerate(rows):
            entry_id = row_data[0]
            title = row_data[1]
            title = title.strip()
            date = row_data[2]
            self.results_table.setItem(row_idx, 0, QTableWidgetItem(str(entry_id)))
            self.results_table.setItem(row_idx, 1, QTableWidgetItem(str(title)))
            self.results_table.setItem(row_idx, 2, QTableWidgetItem(str(date)))

    def show_details(self, eo_id):
        """Shows detailed information about a selected executive order"""
        eo = self.database.get_formatted_data_from_id(eo_id)
        if eo:
            detail_window = DetailViewer(self, eo)
            detail_window.exec()
        else:
            QMessageBox.warning(self, "Not Found", f"No executive order found with ID: {eo_id}")

    def perform_search(self):
        """Executes a requested search using the data within the search bar"""
        criteria = f"%{self.search_input.text()}%"
        cursor = self.database.con.execute(f"SELECT id, title, date FROM executive_orders WHERE id LIKE ? OR title LIKE ? OR date LIKE ? OR content LIKE ? OR url LIKE ?",
                                           (criteria, criteria, criteria, criteria, criteria))
        rows = cursor.fetchall()
        self.results_table.setRowCount(len(rows))
        for row_idx, row_data in enumerate(rows):
            entry_id = row_data[0]
            title = row_data[1]
            title = title.strip()
            date = row_data[2]
            self.results_table.setItem(row_idx, 0, QTableWidgetItem(str(entry_id)))
            self.results_table.setItem(row_idx, 1, QTableWidgetItem(str(title)))
            self.results_table.setItem(row_idx, 2, QTableWidgetItem(str(date)))

class DetailViewer(QDialog):
    def __init__(self, parent,eo_data):
        super().__init__(parent)
        self.eo_id = eo_data["id"]
        self.eo_title = eo_data["title"]
        self.eo_date = eo_data["date"]
        self.eo_content = eo_data["content"]
        self.eo_url = eo_data["url"]

        self.setWindowTitle(f"{self.eo_title} - Detailed View")
        self.setGeometry(150, 150, 600, 400)
        
        self.setLayout(QVBoxLayout())

        self.title_label = QLabel(f"<b>Title:</b> {self.eo_title}")
        self.date_label = QLabel(f"<b>Date:</b> {self.eo_date}")
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
    def __init__(self):
        self.debug = config["debug_mode"]
        self.safety_delays = config["safety_delays"]

        self.foundation_url = "https://www.whitehouse.gov/presidential-actions/executive-orders/"
        self.selected_url = None 
        self.eo_links = []
        self.eo_data = []

        self.database = None # placeholder for database link

        if self.debug:
            signal.signal(signal.SIGINT, self.signal_handler)
            signal.signal(signal.SIGTERM, self.signal_handler)

        try:
            asyncio.run(self.launch_scraper())
        except Exception as e:
            print("An error occurred while scraping EO links: ", e)
            import traceback
            traceback.print_exc()

    def signal_handler(self, signum, frame):
        print(f"\n!!! Received signal {signum} from external source !!!")
        print(f"Frame: {frame}")
        sys.exit(1)

        
    async def launch_scraper(self):
        """Launches a playwright browser instance for scraping"""
        async with Stealth().use_async(async_playwright()) as p:
            context = await p.chromium.launch_persistent_context(
                user_data_dir = config["playwright_tmp_dir"],
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
            raw_date = soup.find("time").text
            date = self.convert_date(raw_date)
            raw_content = [p.text for p in soup.find_all("p")]
            content = "\n".join(raw_content)

            soup.decompose()  
            print(f"Scraped data for {url}: Title: {title}, Date: {date}")  
            
            self.eo_data.append({
                "id": None,
                "title": title,
                "date": date,
                "content": content,
                "url": url
            })

        except Exception as e:
            print(f"An error occurred while scraping data for {url}: {e}")
            self.eo_data.append({
                "id": None,
                "title": "N/A",
                "date": "N/A",
                "content": "N/A",
                "url": url
            })

    def convert_date(self, raw_date):
        """
        Converts a raw date string into YYYY-MM-DD format
        """
        try:
            raw_date.strip()
            date_obj = datetime.datetime.strptime(raw_date, "%B %d, %Y")
            formatted_date = date_obj.strftime("%Y-%m-%d")
            return formatted_date
        except ValueError:
            return raw_date  # return as-is if parsing fails

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
    try:
        database = Database()
        app = QApplication(sys.argv)
        app.setStyle("Fusion")

        # setting app color scheme
        palette = QPalette()
        palette.setColor(QPalette.Window, QColor(43, 43, 43))
        palette.setColor(QPalette.WindowText, QColor(224, 224, 224))
        palette.setColor(QPalette.Base, QColor(60, 60, 60))
        palette.setColor(QPalette.AlternateBase, QColor(43, 43, 43))
        palette.setColor(QPalette.ToolTipBase, QColor(224, 224, 224))
        palette.setColor(QPalette.ToolTipText, QColor(224, 224, 224))
        palette.setColor(QPalette.PlaceholderText, QColor(168, 160, 180))
        palette.setColor(QPalette.Text, QColor(224, 224, 224))
        palette.setColor(QPalette.Button, QColor(50, 50, 60))  
        palette.setColor(QPalette.ButtonText, QColor(224, 224, 224))
        palette.setColor(QPalette.Highlight, QColor(147, 51, 234)) 
        palette.setColor(QPalette.HighlightedText, QColor(255, 255, 255))
        palette.setColor(QPalette.Link, QColor(168, 85, 247))  
        palette.setColor(QPalette.LinkVisited, QColor(96, 165, 250))  
        app.setPalette(palette)

        viewer = Viewer(database)
        app.exec()
    except KeyboardInterrupt:
        print("\n\nShutdown requested - KeyboardInterrupt detected\n")
        print("Closing database connection...")
        database.close()
        print("Database cleaned up, exiting now...")
        sys.exit()

    except Exception as e:
        print("An error occurred in the main application: ", e)
        database.close()
        sys.exit()

    finally:
        if database:
            print("Closing database connection...")
            database.close()
            print("Database cleaned up, exiting now...")
            sys.exit()

if __name__ == "__main__":
    main()