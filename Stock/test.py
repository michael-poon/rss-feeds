from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()))
driver.get("https://www.aastocks.com/tc/stocks/analysis/stock-aafn/00001/0/hk-stock-news/1")

input("請按 Enter 關閉瀏覽器...")
driver.quit()
