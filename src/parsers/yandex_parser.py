import time
import json
import os
from urllib.parse import quote_plus

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from .base_parser import BaseParser

class YandexParser(BaseParser):
    def __init__(self, company_name: str, website: str):
        super().__init__(company_name, website)
        self.base_url = "https://yandex.ru/maps/"
        self.search_url_template = self.base_url + "search/?text={query}"
        self.card_url_prefix = self.base_url + "org/"
        self.driver = None

    def _setup_driver(self):
        if self.driver:
            return

        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument(f"user-agent={self.headers['User-Agent']}")

        current_dir = os.path.dirname(__file__)
        driver_path = os.path.abspath(os.path.join(current_dir, "..", "..", "chromedriver.exe"))

        if not os.path.exists(driver_path):
            raise FileNotFoundError(f"ChromeDriver не найден по пути: {driver_path}")

        service = Service(executable_path=driver_path)
        self.driver = webdriver.Chrome(service=service, options=chrome_options)
        self.driver.implicitly_wait(10)

    def _get_html_selenium(self, url: str) -> str | None:
        if not self.driver:
            self._setup_driver()
            if not self.driver:
                return None

        try:
            self.driver.get(url)
            time.sleep(3)
            return self.driver.page_source
        except Exception as e:
            return None

    def search_company_urls(self) -> list[str]:
        self._setup_driver()
        if not self.driver:
            return []

        search_query = f"{self.company_name} {self.website}"
        encoded_query = quote_plus(search_query)
        search_request_url = self.search_url_template.format(query=encoded_query)

        html = self._get_html_selenium(search_request_url)
        if not html:
            return []

        print(html[:2000])

        soup = BeautifulSoup(html, 'html.parser')
        card_urls = []

        LINK_SELECTOR = 'a.card-title-view__title-link'

        for link_tag in soup.find_all('a', class_='card-title-view__title-link'):
            href = link_tag.get('href')

            if href and href.startswith('/maps/org/'):
                if href.startswith('/'):
                    full_url = "https://yandex.ru" + href
                else:
                    full_url = href

                card_urls.append(full_url)

        if not card_urls:
            for link_tag in soup.find_all('a', href=lambda h: h and h.startswith('/maps/org/')):
                href = link_tag.get('href')
                full_url = "https://yandex.ru" + href
                card_urls.append(full_url)

        unique_card_urls = list(set(card_urls))
        return unique_card_urls

    def parse_card_data(self, card_url: str) -> dict:
        html = self._get_html_selenium(card_url)
        if not html:
            return {}

        soup = BeautifulSoup(html, 'html.parser')
        card_data = {"url": card_url}
        card_data["rating"] = 0.0
        card_data["reviews_count"] = 0
        card_data["answered_reviews"] = 0
        card_data["unanswered_reviews"] = 0
        card_data["response_time"] = "N/A"
        card_data["reviews"] = []
        return card_data