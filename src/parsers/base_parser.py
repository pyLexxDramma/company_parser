import requests
from abc import ABC, abstractmethod
from urllib.parse import urlparse

class BaseParser(ABC):
    def __init__(self, company_name: str, website: str):
        self.company_name = company_name
        self.website = website
        self.base_url = ""
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }

    @abstractmethod
    def search_company_urls(self) -> list[str]:
        pass

    @abstractmethod
    def parse_card_data(self, card_url: str) -> dict:
        pass

    def get_html(self, url: str) -> str | None:
        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()
            return response.text
        except requests.exceptions.RequestException as e:
            print(f"Ошибка при запросе к {url}: {e}")
            return None

    def get_website_domain(self, url: str) -> str:
        try:
            parsed_url = urlparse(url)
            return parsed_url.netloc
        except Exception as e:
            print(f"Ошибка при парсинге домена из {url}: {e}")
            return ""

    def analyze_cards(self) -> dict:
        card_urls = self.search_company_urls()
        if not card_urls:
            return {"error": f"Карточки для компании '{self.company_name}' не найдены на {self.__class__.__name__}"}

        all_cards_data = []
        valid_cards_count = 0
        for url in card_urls:
            if self.get_website_domain(url) == self.get_website_domain(self.website):
                card_data = self.parse_card_data(url)
                if card_data:
                    all_cards_data.append(card_data)
                    valid_cards_count += 1
            else:
                print(f"Пропуск URL: {url} - домен не совпадает с {self.website}")

        if not all_cards_data:
            return {"error": f"Не найдено валидных карточек компании '{self.company_name}' с совпадающим сайтом на {self.__class__.__name__}"}

        return self.aggregate_data(all_cards_data)

    def aggregate_data(self, cards_data: list[dict]) -> dict:
        total_cards = len(cards_data)
        return {
            "company_name": self.company_name,
            "platform": self.__class__.__name__.replace("Parser", ""),
            "card_count": total_cards,
            "overall_rating": 0.0,
            "total_reviews": 0,
            "answered_reviews": 0,
            "unanswered_reviews": 0,
            "negative_reviews": 0,
            "positive_reviews": 0,
            "average_response_time": "N/A",
            "cards_details": cards_data
        }