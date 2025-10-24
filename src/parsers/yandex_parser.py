import time
import json
import os
from urllib.parse import quote_plus, urlparse
import re
import requests
from fake_useragent import UserAgent
import random

from bs4 import BeautifulSoup

from .base_parser import BaseParser

class YandexParser(BaseParser):
    def __init__(self, company_name: str, website: str):
        super().__init__(company_name, website)
        self.base_url = "https://yandex.ru/maps/"
        self.search_base_url = "https://yandex.ru/maps/"
        self.search_query_template = "search/?text={query}"
        self.headers = self._get_default_headers()
        self.proxies = self._load_proxies()
        self.current_proxy = None

    def _get_default_headers(self) -> dict:
        ua = UserAgent()
        return {
            'User-Agent': ua.random,
            'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Referer': 'https://yandex.ru/maps/',
            'Upgrade-Insecure-Requests': '1',
            'DNT': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'same-origin',
            'Sec-Fetch-User': '?1',
        }

    def _load_proxies(self) -> list[str]:
        proxies_file = "proxies.txt"
        try:
            with open(proxies_file, "r") as f:
                proxies = [line.strip() for line in f if line.strip()]
                return proxies
        except FileNotFoundError:
            return []
        except Exception as e:
            return []

    def _get_proxy(self) -> dict | None:
        if self.proxies:
            proxy = random.choice(self.proxies)
            return {"http": f"http://{proxy}", "https": f"https://{proxy}"}
        else:
            return None

    def _get_html_requests(self, url: str, retries=3) -> str | None:
        for attempt in range(retries):
            proxy = self._get_proxy()
            headers = self._get_default_headers()

            try:
                response = requests.get(url, headers=headers, proxies=proxy, timeout=20)
                response.raise_for_status()

                if not response.text or "404" in response.text.lower() or "Page not found" in response.text:
                    continue

                if len(response.text) < 500:
                    continue

                return response.text

            except requests.exceptions.Timeout:
                pass
            except requests.exceptions.HTTPError as http_err:
                pass
            except requests.exceptions.RequestException as req_err:
                pass
            except Exception as e:
                pass

        return None

    def search_company_urls(self) -> list[str]:
        search_query_text = f"{self.company_name}"
        encoded_query = quote_plus(search_query_text)
        search_request_url = self.search_base_url + self.search_query_template.format(query=encoded_query)

        print(f"Ищу на Яндекс.Картах (requests): {search_request_url}")

        all_found_urls = set()

        html = self._get_html_requests(search_request_url)
        if not html:
            return []

        soup = BeautifulSoup(html, 'html.parser')

        org_snippets = soup.select('.search-business-snippet-view')

        if not org_snippets:
            for link_tag in soup.find_all('a', href=True):
                href = link_tag.get('href')
                if href and href.startswith('/maps/org/'):
                    full_url = "https://yandex.ru" + href
                    all_found_urls.add(full_url)
        else:
            for snippet in org_snippets:
                link_tag = snippet.select_one('.search-business-snippet-view__content .link-overlay[role=\'link\']')

                if link_tag:
                    href = link_tag.get('href')
                    if href and href.startswith('/maps/org/'):
                        full_url = "https://yandex.ru" + href
                        all_found_urls.add(full_url)

        filtered_card_urls = []
        for url in list(all_found_urls):
            normalized_href = urlparse(url).path

            if normalized_href.startswith('/maps/org/'):
                if not any(subpath in normalized_href for subpath in ['/reviews/', '/gallery/', '/photos/']) and normalized_href.rstrip('/') == normalized_href:
                    filtered_card_urls.append(url)

        unique_card_urls = list(set(filtered_card_urls))
        print(f"НАЙДЕНЫ ЧИСТЫЕ URL КАРТОЧЕК: {len(unique_card_urls)}.")

        return unique_card_urls

    def parse_card_data(self, card_url: str) -> dict:
        print(f"Парсинг данных с карточки: {card_url}")
        html = self._get_html_requests(card_url)
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
        card_data["total_reviews"] = 0
        card_data["answered_reviews"] = 0
        card_data["unanswered_reviews"] = 0
        card_data["response_time"] = "N/A"

        return card_data

    def analyze_cards(self) -> dict:
        print(f"Анализ карточек для '{self.company_name}'...")
        card_urls = self.search_company_urls()
        if not card_urls:
            return {"error": f"Карточки для '{self.company_name}' не найдены на Яндекс."}

        all_cards_data = []
        MAX_CARDS_TO_PARSE = 5

        for i, url in enumerate(card_urls):
            if i >= MAX_CARDS_TO_PARSE:
                break

            card_data = self.parse_card_data(url)
            if card_data:
                all_cards_data.append(card_data)

        if not all_cards_data:
            return {"error": f"Не найдено валидных карточек компании '{self.company_name}' на Яндекс."}

        return self.aggregate_data(all_cards_data)

    def aggregate_data(self, cards_data: list[dict]) -> dict:
        total_cards = len(cards_data)

        aggregated_result = {
            "platform": "Yandex Maps",
            "company_name": self.company_name,
            "website": self.website,
            "card_count": total_cards,
            "card_urls": [card.get("url") for card in cards_data],
            "average_rating": 0.0,
            "total_reviews": 0,
            "answered_reviews": 0,
            "unanswered_reviews": 0,
            "response_time": "N/A",
            "positive_reviews": 0,
            "negative_reviews": 0,
            "detailed_card_data": []
        }

        if not cards_data:
            return aggregated_result

        overall_rating_sum = sum(card.get("rating", 0.0) for card in cards_data if card.get("rating") is not None)
        aggregated_result["average_rating"] = round(overall_rating_sum / total_cards, 1) if total_cards > 0 else 0.0
        aggregated_result["total_reviews"] = sum(card.get("reviews_count", 0) for card in cards_data)
        aggregated_result["answered_reviews"] = sum(card.get("answered_reviews", 0) for card in cards_data)
        aggregated_result["unanswered_reviews"] = aggregated_result["total_reviews"] - aggregated_result["answered_reviews"]

        for card in cards_data:
            aggregated_result["detailed_card_data"].append({
                "url": card.get("url"),
                "rating": card.get("rating"),
                "reviews_count": card.get("reviews_count"),
                "address": card.get("address"),
                "working_hours": card.get("working_hours"),
                "reviews_stub_count": len(card.get("reviews", []))
            })

        return aggregated_result

    def get_website_domain(self, url: str) -> str | None:
        try:
            parsed_url = urlparse(url)
            domain = parsed_url.netloc
            if domain.startswith("www."):
                domain = domain[4:]
            return domain
        except Exception as e:
            return None