from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from datetime import datetime, timedelta
import time
import re

from .base_parser import BaseParser


class GIS2Parser(BaseParser):
    def __init__(self, driver: WebDriver, company_name: str, company_site: str, proxies=None):
        super().__init__(driver, company_name, company_site, proxies)
        self.base_url = "https://2gis.ru"

    def search_company_urls(self) -> list[str]:
        search_query = self.company_name.replace(" ", "+")
        search_url = f"{self.base_url}/search/{search_query}"

        urls = []
        try:
            self.driver.get(search_url)
            wait = WebDriverWait(self.driver, 20)

            results_container_locator = (By.CSS_SELECTOR, "div[data-id='results_list']")
            wait.until(EC.presence_of_element_located(results_container_locator))

            card_item_locator = (By.CSS_SELECTOR, "div.result-item")
            card_elements = self.driver.find_elements(*card_item_locator)

            if not card_elements:
                card_item_locator = (By.CSS_SELECTOR, "a[data-testid='card-link']")
                card_elements = self.driver.find_elements(*card_item_locator)

            for card_element in card_elements:
                try:
                    link_element = card_element.find_element(By.CSS_SELECTOR, "a.directory-list-item-link")
                    card_url = link_element.get_attribute("href")

                    if card_url and "firms" in card_url:
                        urls.append(card_url)
                except:
                    continue

        except Exception as e:
            print(f"Ошибка при поиске URL карточек 2ГИС для '{self.company_name}': {e}")

        return list(set(urls))

    def parse_card_details(self, card_url: str) -> dict | None:
        card_data = {
            "url": card_url,
            "rating": None,
            "total_reviews": 0,
            "answered_reviews": 0,
            "unanswered_reviews": 0,
            "avg_response_time_seconds": None,
            "negative_reviews": 0,
            "positive_reviews": 0,
            "reviews": []
        }

        try:
            self.driver.get(card_url)
            wait = WebDriverWait(self.driver, 20)

            rating_locator = (By.CSS_SELECTOR, "span[data-testid='rating-value']")
            rating_element = wait.until(EC.visibility_of_element_located(rating_locator))
            card_data["rating"] = float(rating_element.text.replace(",", "."))

            reviews_link_locator = (By.CSS_SELECTOR, "a[data-testid='reviews-link']")
            reviews_link_element = wait.until(EC.visibility_of_element_located(reviews_link_locator))
            reviews_text = reviews_link_element.text
            match = re.search(r'\d+', reviews_text)
            if match:
                card_data["total_reviews"] = int(match.group(0))
            else:
                card_data["total_reviews"] = 0

            reviews_section_locator = (By.CSS_SELECTOR, "section[data-id='reviews']")
            try:
                reviews_section = wait.until(EC.presence_of_element_located(reviews_section_locator))
            except:
                return card_data

            review_elements = reviews_section.find_elements(By.CSS_SELECTOR, "div.review-item")

            response_times_seconds = []

            for review_element in review_elements:
                review_detail = {}

                try:
                    review_rating_locator = (By.CSS_SELECTOR, "span.star-rating")
                    review_rating_element = review_element.find_element(*review_rating_locator)
                    rating_val = review_rating_element.get_attribute(
                        "aria-label") or review_rating_element.get_attribute("data-rating")
                    if rating_val:
                        match_rating = re.search(r'\d+(\.\d+)?', rating_val)
                        if match_rating:
                            review_detail["rating"] = float(match_rating.group(0))
                except:
                    review_detail["rating"] = None

                try:
                    review_text_locator = (By.CSS_SELECTOR, "div.review-text")
                    review_text_element = review_element.find_element(*review_text_locator)
                    review_detail["text"] = review_text_element.text
                except:
                    review_detail["text"] = ""

                try:
                    review_date_locator = (By.CSS_SELECTOR, "span.review-date")
                    review_date_element = review_element.find_element(*review_date_locator)
                    review_date_str = review_date_element.text
                    review_detail["date"] = self._parse_date(review_date_str)
                except:
                    review_detail["date"] = None

                try:
                    response_block_locator = (By.CSS_SELECTOR, "div.response-block")
                    response_element = review_element.find_element(*response_block_locator)

                    response_text_locator = (By.CSS_SELECTOR, "div.response-text")
                    response_text_element = response_element.find_element(*response_text_locator)
                    response_text = response_text_element.text

                    response_date_locator = (By.CSS_SELECTOR, "span.response-date")
                    response_date_element = response_element.find_element(*response_date_locator)
                    response_date_str = response_date_element.text
                    response_date = self._parse_date(response_date_str)

                    review_detail["response"] = {
                        "text": response_text,
                        "date": response_date
                    }
                    card_data["answered_reviews"] += 1

                    if review_detail["date"] and response_date:
                        time_diff = response_date - review_detail["date"]
                        response_times_seconds.append(time_diff.total_seconds())

                except:
                    review_detail["response"] = None
                    card_data["unanswered_reviews"] += 1

                card_data["reviews"].append(review_detail)

                if review_detail.get("rating") is not None:
                    if review_detail["rating"] <= 3.0:
                        card_data["negative_reviews"] += 1
                    else:
                        card_data["positive_reviews"] += 1

        except Exception as e:
            print(f"Ошибка при парсинге деталей карточки {card_url}: {e}")
            return None

        return card_data

    def _scroll_to_load_more_elements(self, wait: WebDriverWait):
        last_height = self.driver.execute_script("return document.body.scrollHeight")
        while True:
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(3)
            new_height = self.driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                break
            last_height = new_height
            print("Scrolling down...")