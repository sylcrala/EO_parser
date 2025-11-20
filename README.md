# Scraper and Searchable database for Executive Orders

The goal of this project is to create a simple webscraper and database viewer for all present executive orders listed on whitehouse.gov. I wanted a way to filter and keyword search every EO in bulk, so I figured it would be a good side-project!


If anyone else could use something like this too, please feel free to use it however you deem fit!


### Installation
I recommend setting up a virtual environment to store the libraries needed for use, as it's cleaner than bloating up the main Python installation (if i'm not mistaken). To install the required libraries, please run the following commands within the .venv (or use them within your main Python install if preferred)
```
pip install -r requirements.txt
```
After installing the required libraries needed, you need to run a secondary command to install the browser that Playwright uses for scraping (we use playwright over requests because I was seeing some issues during the requests setup - likely bot detection)
```
playwright install chromium
```


### First launch
Prior to your first launch, 

On your first launch, you'll be faced with an empty table, a search bar, and some buttons. 

To begin the scraping process and populate the table, click the "Run Scraper" button in the top-right corner, and give it some time to go through the process (watch the launch terminal to see the scraping process in action). The GUI will stop responding during the scraping process, but this is okay (it's working in the background)!


### License
Feel free to use, modify, distribute, etc, this script however you deem fit! It's licensed under the MIT license so there's no restrictions!


### Support
If you enjoyed this project and want to support development of other similar projects, please consider sponsoring the project or checking out my other work! 


--


made with love by sylcrala <3