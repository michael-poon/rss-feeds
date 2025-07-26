import logging
import os
import random
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from feedgen.feed import FeedGenerator

# 香港時區：UTC+8
hk_tz = timezone(timedelta(hours=8))

MAX_RETRIES = 5

load_dotenv()

# 讀取環境變數 DEBUG，如果無就預設為 False
DEBUG = os.getenv("DEBUG", "").lower() == "true"

# 設定 logging format 同 level
logging.basicConfig(
    level=logging.INFO if DEBUG else logging.WARNING,
    format='%(asctime)s - %(levelname)s - %(message)s',
    force=True  # Python 3.8+，確保唔會被其他 handler override
)


def parse_stock_list(env_var):
    raw = os.getenv(env_var, "")
    return [s.strip() for s in raw.split(",") if s.strip()]


def fetch_news(stock_code):
    # 🧩 擷取新聞資料
    url = f"https://www.aastocks.com/tc/stocks/analysis/stock-aafn/{stock_code}/0/hk-stock-news/1"
    headers = {"User-Agent": "Mozilla/5.0"}
    retries = 0

    while retries < MAX_RETRIES:
        try:
            resp = requests.get(url, headers=headers, timeout=10)
            resp.raise_for_status()  # 如果 status code >= 400 就 raise error
            logging.info(f"✅ 成功擷取 {stock_code} 的新聞")
            soup = BeautifulSoup(resp.text, "html.parser")

            content_div = soup.find(
                "div", class_="content", id="aafn-search-c1")
            news_blocks = content_div.find_all("div", attrs={"ref": True})

            news_list = []
            for block in news_blocks:
                title_tag = block.select_one(".newshead4 a")
                date_tag = block.select_one(".newstime4 .inline_block")
                summary_tag = block.select_one(".newscontent4")
                img_tag = block.select_one(".newsImage4a img")

                title = title_tag.text.strip() if title_tag else "（無標題）"
                link = title_tag["href"] if title_tag else "#"
                if not link.startswith("http"):
                    link = "https://www.aastocks.com" + link

                # 擷取時間（從 script 中抽出 dt）
                try:
                    script_text = date_tag.find("script").string
                    match = re.search(r"dt:'([\d/:\s]+)'", script_text)
                    raw_date = match.group(1) if match else None
                    dt = datetime.strptime(
                        raw_date, "%Y/%m/%d %H:%M").replace(tzinfo=hk_tz)
                    pub_date = format_datetime(dt)
                except:
                    pub_date = format_datetime(datetime.now())

                summary = summary_tag.text.strip() if summary_tag else title
                img_url = img_tag["src"] if img_tag and img_tag.has_attr(
                    "src") else None
                ref_id = block.get("ref")

                news_list.append({
                    "title": title,
                    "link": link,
                    "pubDate": pub_date,
                    "summary": summary,
                    "image": img_url,
                    "guid": ref_id
                })

            return news_list
        except requests.exceptions.RequestException as e:
            retries += 1
            logging.info(f"⚠️ 擷取 {stock_code} 失敗（第 {retries} 次），錯誤：{e}")
            time.sleep(2 ** retries)  # 指數式延遲：2s, 4s, 8s

    logging.error(f"❌ 最多重試 {MAX_RETRIES} 次，放棄 {stock_code}")
    return []


def generate_rss(all_news, output_filename="combined_stock_news.xml"):
    fg = FeedGenerator()
    fg.title("AASTOCKS 綜合股票新聞")
    fg.link(href="https://www.aastocks.com/tc/stocks/news/aafn")
    fg.description("綜合多隻股票的最新新聞 RSS Feed")
    fg.language("zh-HK")
    fg.lastBuildDate(datetime.now(hk_tz))

    for news in all_news:
        fe = fg.add_entry()
        fe.title(news["title"])
        fe.link(href=news["link"])
        fe.guid(news["guid"], permalink=False)
        fe.pubDate(datetime.strptime(
            news["pubDate"], "%a, %d %b %Y %H:%M:%S %z"))
        fe.description(news["summary"])
        if news["image"]:
            fe.enclosure(news["image"], 0, "image/jpeg")

    output_path = os.path.join(os.path.dirname(__file__), output_filename)
    fg.rss_file(output_path)
    logging.info(f"✅ RSS feed 已儲存：{output_filename}")


def process_feed(stock_list, output_filename):
    all_news = []
    for stock_code in stock_list:
        logging.info(f"📡 擷取 {stock_code} 的新聞中...")
        news = fetch_news(stock_code)
        all_news.extend(news)
        time.sleep(random.uniform(2, 5))  # 安全延遲
    generate_rss(all_news, output_filename)

# def read_stock_list(file_path):
#     with open(file_path, "r", encoding="utf-8") as f:
#         return [line.strip() for line in f if line.strip()]


def main():
    # 🧪 執行
    # if len(sys.argv) < 2:
    #     print("❌ 請提供股票清單 txt 檔案，例如：python gen_rss.py my_stocks.txt")
    #     return

    # file_path = sys.argv[1]
    # stock_list = read_stock_list(file_path)

    my_stocks = parse_stock_list("STOCK_LIST_MY")
    watchlist = parse_stock_list("STOCK_LIST_WATCH")

    process_feed(my_stocks, "stocks_rss.xml")
    process_feed(watchlist, "watch_rss.xml")


if __name__ == "__main__":
    main()
