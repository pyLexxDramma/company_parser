from selenium.webdriver.remote.webdriver import WebDriver
from abc import ABC, abstractmethod
from urllib.parse import urlparse
from datetime import datetime, timedelta


class BaseParser(ABC):
    def __init__(self, driver: WebDriver, company_name: str, company_site: str, proxies=None):
        self.driver = driver
        self.proxies = proxies
        self.company_name = company_name
        self.company_site = company_site
        self.base_url = ""
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }

    def _get_html_content(self) -> str | None:
        try:
            return self.driver.page_source
        except Exception as e:
            print(f"Ошибка при получении HTML: {e}")
            return None

    def get_website_domain(self, url: str) -> str:
        try:
            parsed_url = urlparse(url)
            domain_parts = parsed_url.netloc.split('.')
            if len(domain_parts) > 2:
                return '.'.join(domain_parts[-2:])
            return parsed_url.netloc
        except Exception as e:
            print(f"Ошибка при парсинге домена из {url}: {e}")
            return ""

    def _parse_date(self, date_str: str) -> datetime | None:
        try:
            date_str = date_str.lower().strip()
            now = datetime.now()

            if "час назад" in date_str:
                hours = int(date_str.split()[0])
                return now - timedelta(hours=hours)
            elif "дня назад" in date_str or "дней назад" in date_str:
                days = int(date_str.split()[0])
                return now - timedelta(days=days)
            elif "минут назад" in date_str:
                minutes = int(date_str.split()[0])
                return now - timedelta(minutes=minutes)
            elif "сегодня" in date_str:
                time_part = date_str.replace("сегодня", "").strip()
                if time_part and ":" in time_part:
                    return datetime.combine(now.date(), datetime.strptime(time_part, "%H:%M").time())
                return now.replace(hour=0, minute=0, second=0, microsecond=0)

            parts = date_str.split()
            day = None
            month = None
            year = now.year

            if len(parts) >= 2:
                try:
                    day = int(parts[0])
                    month_name = parts[1]

                    month_map = {
                        "января": 1, "февраля": 2, "марта": 3, "апреля": 4,
                        "мая": 5, "июня": 6, "июля": 7, "августа": 8,
                        "сентября": 9, "октября": 10, "ноября": 11, "декабря": 12
                    }
                    month = month_map.get(month_name)

                    if len(parts) == 3:
                        year = int(parts[2])

                    if day and month:
                        return datetime(year, month, day)
                except ValueError:
                    pass

            if "." in date_str:
                date_parts = date_str.split('.')
                if len(date_parts) == 3:
                    return datetime.strptime(date_str, "%d.%m.%Y")
                elif len(date_parts) == 2:
                    return datetime.strptime(date_str, "%d.%m").replace(year=now.year)

            return None

        except Exception as e:
            print(f"Не удалось разобрать дату: '{date_str}'. Ошибка: {e}")
            return None

    @abstractmethod
    def search_company_urls(self) -> list[str]:
        pass

    @abstractmethod
    def parse_card_details(self, card_url: str) -> dict | None:
        pass

    def analyze_platform_data(self) -> dict:
        card_urls = self.search_company_urls()

        if not card_urls:
            return {
                "error": f"Карточки для компании '{self.company_name}' не найдены на {self.__class__.__name__.replace('Parser', '')}"
            }

        all_cards_data = []
        valid_cards_count = 0
        for url in card_urls:
            card_domain = self.get_website_domain(url)
            company_domain = self.get_website_domain(self.company_site)

            if card_domain.endswith(company_domain) or company_domain.endswith(card_domain):
                card_data = self.parse_card_details(url)
                if card_data:
                    all_cards_data.append(card_data)
                    valid_cards_count += 1
            else:
                print(
                    f"Skipping URL: {url} - domain mismatch. Card domain: '{card_domain}', Company domain: '{company_domain}'")

        if not all_cards_data:
            return {
                "error": f"Не найдено валидных карточек компании '{self.company_name}' с совпадающим сайтом ({self.company_site}) на {self.__class__.__name__.replace('Parser', '')}"
            }

        return self.aggregate_platform_data(all_cards_data)

    def aggregate_platform_data(self, cards_data: list[dict]) -> dict:
        total_cards = len(cards_data)

        summary = {
            "platform": self.__class__.__name__.replace("Parser", ""),
            "card_count": total_cards,
            "overall_rating": 0.0,
            "total_reviews_count": 0,
            "answered_reviews_count": 0,
            "unanswered_reviews_count": 0,
            "negative_reviews_count": 0,
            "positive_reviews_count": 0,
            "avg_response_time_days": None,
            "cards_details": cards_data
        }

        total_rating_sum = 0
        total_reviews = 0
        total_answered = 0
        total_unanswered = 0
        all_response_times_seconds = []
        total_negative = 0
        total_positive = 0

        for card in cards_data:
            if card.get("rating") is not None:
                total_rating_sum += card["rating"]
            total_reviews += card.get("total_reviews", 0)
            total_answered += card.get("answered_reviews", 0)
            total_unanswered += card.get("unanswered_reviews", 0)

            if card.get("avg_response_time_seconds") is not None:
                all_response_times_seconds.append(card["avg_response_time_seconds"])

            total_negative += card.get("negative_reviews", 0)
            total_positive += card.get("positive_reviews", 0)

        if total_cards > 0:
            summary["overall_rating"] = round(total_rating_sum / total_cards, 2)

        if all_response_times_seconds:
            avg_seconds = sum(all_response_times_seconds) / len(all_response_times_seconds)
            summary["avg_response_time_days"] = round(avg_seconds / (60 * 60 * 24), 2)

        summary["total_reviews_count"] = total_reviews
        summary["answered_reviews_count"] = total_answered
        summary["unanswered_reviews_count"] = total_unanswered
        summary["negative_reviews_count"] = total_negative
        summary["positive_reviews_count"] = total_positive

        return summary