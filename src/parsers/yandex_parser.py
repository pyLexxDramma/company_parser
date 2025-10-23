import time
import json
import os
from urllib.parse import quote_plus, urlparse
import re

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from .base_parser import BaseParser


class YandexParser(BaseParser):
    def __init__(self, company_name: str, website: str):
        super().__init__(company_name, website)
        self.base_url = "https://yandex.ru/maps/"
        self.search_base_url = "https://yandex.ru/maps/"
        self.search_query_template = "search/?text={query}"
        self.driver = None
        self.headers = self._get_default_headers()

    def _get_default_headers(self) -> dict:
        return {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7'
        }

    def _setup_driver(self):
        if self.driver:
            return

        chrome_options = Options()
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument(f"user-agent={self.headers['User-Agent']}")

        try:
            current_dir = os.path.dirname(__file__)
            project_root = os.path.abspath(os.path.join(current_dir, "..", ".."))
            driver_path = os.path.join(project_root, "chromedriver.exe")

            if not os.path.exists(driver_path):
                raise FileNotFoundError(f"ChromeDriver не найден по пути: {driver_path}")

            service = Service(executable_path=driver_path)
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            self.driver.implicitly_wait(10)
        except FileNotFoundError as fnf_error:
            self.driver = None
        except Exception as e:
            self.driver = None

    def _get_html_selenium(self, url: str) -> str | None:
        if not self.driver:
            self._setup_driver()
            if not self.driver:
                return None

        try:
            self.driver.get(url)
            time.sleep(2)
            if "404" in self.driver.title.lower():
                return None
            return self.driver.page_source
        except Exception as e:
            return None

    def search_company_urls(self) -> list[str]:
        self._setup_driver()
        if not self.driver:
            return []

        search_request_url = "https://yandex.ru/maps/44/izhevsk/chain/vkusvill/22308299491/?ll=53.206896%2C56.853244&sll=53.206896%2C56.852677&sspn=0.123253%2C0.049284&z=12.97"

        html = self._get_html_selenium(search_request_url)
        if not html:
            return []

        soup = BeautifulSoup(html, 'html.parser')
        card_urls = []

        LINK_SELECTOR = '.search-business-snippet-view__content .link-overlay[role=\'link\']'

        for link_tag in soup.select(LINK_SELECTOR):
            href = link_tag.get('href')
            if href and href.startswith('/maps/org/'):
                full_url = "https://yandex.ru" + href
                card_urls.append(full_url)

        if not card_urls:
            for link_tag in soup.find_all('a', href=lambda h: h and h.startswith('/maps/org/')):
                href = link_tag.get('href')
                full_url = "https://yandex.ru" + href
                card_urls.append(full_url)

        unique_card_urls = list(set(card_urls))
        return unique_card_urls

    def parse_card_data(self, card_url: str) -> dict:
        print(f"Парсинг данных с карточки: {card_url}")
        html = self._get_html_selenium(card_url)
        if not html:
            return {}

        soup = BeautifulSoup(html, 'html.parser')
        card_data = {"url": card_url}

        card_data["company_name"] = self.company_name
        card_data["rating"] = 0.0
        card_data["reviews_count"] = 0
        card_data["address"] = "N/A"
        card_data["working_hours"] = "N/A"
        card_data["reviews"] = []

        return card_data

    def analyze_cards(self) -> dict:
        print(f"Анализ карточек для '{self.company_name}'...")
        card_urls = self.search_company_urls()
        if not card_urls:
            if self.driver: self.driver.quit()
            return {"error": f"Карточки для '{self.company_name}' не найдены на YandexParser"}

        all_cards_data = []
        for url in card_urls:
            card_data = self.parse_card_data(url)
            if card_data:
                all_cards_data.append(card_data)

        if self.driver:
            self.driver.quit()

        if not all_cards_data:
            return {"error": f"Не найдено валидных карточек компании '{self.company_name}' на Яндекс."}

        return {
            "found_cards_count": len(all_cards_data),
            "card_urls": card_urls,
            "all_cards_data_stub": all_cards_data
        }

    def get_website_domain(self, url: str) -> str | None:
        try:
            parsed_url = urlparse(url)
            domain = parsed_url.netloc
            if domain.startswith("www."):
                domain = domain[4:]
            return domain
        except Exception as e:
            return None