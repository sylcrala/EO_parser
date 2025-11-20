# Executive Order Searcher
*Making it easy to search executive orders in bulk*

The goal of this project is to create a simple webscraper and database viewer for all present executive orders listed on whitehouse.gov. I wanted a way to filter and keyword search every EO for keywords or phrases, and I figured it would be a good side-project!



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

Check settings.py and customize any setting if needed or wanted (change database path, name, enable/disable debug mode, enable/disable safety timers)


### Troubleshooting
If the scraping process is randomly stopping in the middle of the process, try enabing the safety_timers if it's disabled. If it's already enabled and you still see the issue, try customizing the assigned user-agent within Scraper.launch_scraper() and see if that helps! If the issue persists please submit an Issue ticket so I can look into it!


### License
Feel free to use, modify, distribute, etc, this script however you deem fit! It's licensed under the MIT license so there's no restrictions!


### Support
Thank you so much for checking out my project!!

If you enjoy my work and want to support development of this or other projects, please consider sponsoring the project or checking out my other work! Also, if you have an idea or request for a new feature, please reach out to me directly or submit an Issue ticket with one of the following labels: "question" or "enhancement"!


--


made with love by sylcrala <3
