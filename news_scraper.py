# news_scraper.py (純淨版)

import yfinance as yf
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# 智慧關鍵字生成函式
def get_search_keyword_from_ticker(ticker: str) -> str:
    ticker_upper = ticker.upper()
    special_cases = {"TSM": "台積電", "AVGO": "博通", "UMC": "聯電"}
    if ticker_upper in special_cases:
        return special_cases[ticker_upper]
    try:
        info = yf.Ticker(ticker_upper).info
        name = info.get('longName')
        if name:
            for suffix in [" Corporation", " Inc.", ", Inc.", " Incorporated", " Ltd.", " Platforms", " Co."]:
                if name.endswith(suffix):
                    name = name[:-len(suffix)]
            return name
        return ticker_upper
    except:
        return ticker_upper

def scrape_news_headlines(ticker: str, max_articles: int = 5):
    """
    接收一個股票代碼，自動用公司名或特殊對應名搜尋 Yahoo 新聞標題和連結。
    """
    search_keyword = get_search_keyword_from_ticker(ticker)
    print(f"啟動 Yahoo 新聞爬蟲，搜尋關鍵字: '{search_keyword}' (原始: '{ticker}')")
    url = f'https://tw.news.search.yahoo.com/search?p={search_keyword}'

    options = uc.ChromeOptions()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-gpu')

    driver = None
    try:
        driver = uc.Chrome(options=options, use_subprocess=True)
        driver.get(url)

        wait = WebDriverWait(driver, 15)
        selector = 'h4.s-title a'
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))

        news_elements = driver.find_elements(By.CSS_SELECTOR, selector)

        article_links = []
        for element in news_elements[:max_articles]:
            title = element.text.strip()
            href = element.get_attribute('href')
            if title and href:
                article_links.append((title, href))

        if not article_links:
            print("在 Yahoo 新聞找不到相關標題。")
            return None

        print(f"成功爬取 {len(article_links)} 則新聞標題。")
        return article_links

    except Exception as e:
        print(f"爬取 Yahoo 新聞時發生錯誤: {e}")
        return None
    finally:
        if driver:
            driver.quit()