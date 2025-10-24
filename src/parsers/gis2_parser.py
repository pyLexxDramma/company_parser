from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from datetime import datetime, timedelta
import time
import re
import os
from urllib.parse import urljoin

from .base_parser import BaseParser


class GIS2Parser(BaseParser):
    def __init__(self, driver: WebDriver, company_name: str, company_site: str, proxies=None):
        super().__init__(driver, company_name, company_site, proxies)
        self.base_url = "https://2gis.ru"
        self.driver.execute_cdp_cmd('Network.setUserAgentOverride', {"userAgent": self.headers['User-Agent']})

    def search_company_urls(self) -> list[str]:
        search_query = self.company_name.replace(" ", "+")
        search_url = f"{self.base_url}/search/{search_query}"

        urls = []
        try:
            self.driver.get(search_url)
            wait = WebDriverWait(self.driver, 50)

            results_container_locator = (By.CSS_SELECTOR, "._1kf6gff")
            card_item_locator = (By.CSS_SELECTOR, "._zjunba")
            link_locator_to_try = (By.CSS_SELECTOR, "a._1rehek")

            results_container = wait.until(EC.presence_of_element_located(results_container_locator))

            card_elements = results_container.find_elements(By.CSS_SELECTOR, card_item_locator[1])

            for i, card_element in enumerate(card_elements):
                card_url_relative = None
                card_url_absolute = None

                if card_element.tag_name == 'a':
                    card_url_relative = card_element.get_attribute("href")
                else:
                    try:
                        link_element = card_element.find_element(*link_locator_to_try)
                        card_url_relative = link_element.get_attribute("href")
                    except Exception as e_inner_link:
                        pass

                if card_url_relative:
                    card_url_absolute = urljoin(self.base_url, card_url_relative)

                    if "firms" in card_url_absolute and self.base_url in card_url_absolute:
                        urls.append(card_url_absolute)

        except Exception as e:
            return []

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
            wait = WebDriverWait(self.driver, 40)

            rating_locator = (By.CSS_SELECTOR, "span[data-testid='rating-value']")
            reviews_link_locator = (By.CSS_SELECTOR, "a[data-testid='reviews-link']")
            reviews_section_locator = (By.CSS_SELECTOR, "section[data-id='reviews']")
            review_item_locator = (By.CSS_SELECTOR, "div.review-item")
            review_rating_locator = (By.CSS_SELECTOR, "span.star-rating")
            review_text_locator = (By.CSS_SELECTOR, "div.review-text")
            review_date_locator = (By.CSS_SELECTOR, "span.review-date")
            response_block_locator = (By.CSS_SELECTOR, "div.response-block")
            response_text_locator = (By.CSS_SELECTOR, "div.response-text")
            response_date_locator = (By.CSS_SELECTOR, "span.response-date")

            rating_element = wait.until(EC.visibility_of_element_located(rating_locator))
            card_data["rating"] = float(rating_element.text.replace(",", "."))

            reviews_link_element = wait.until(EC.visibility_of_element_located(reviews_link_locator))
            reviews_text = reviews_link_element.text
            match_reviews = re.search(r'(\d+)', reviews_text)
            if match_reviews:
                card_data["total_reviews"] = int(match_reviews.group(1))
            else:
                card_data["total_reviews"] = 0

            try:
                reviews_section = wait.until(EC.presence_of_element_located(reviews_section_locator))
            except Exception as e:
                return card_data

            review_elements = reviews_section.find_elements(*review_item_locator)

            response_times_seconds = []

            for i, review_element in enumerate(review_elements):
                review_detail = {}

                try:
                    rating_sub_element = review_element.find_element(*review_rating_locator)
                    rating_val = rating_sub_element.get_attribute("aria-label") or rating_sub_element.get_attribute(
                        "data-rating")
                    if rating_val:
                        match_rating = re.search(r'(\d+(\.\d+)?)', rating_val)
                        if match_rating:
                            review_detail["rating"] = float(match_rating.group(1))
                except Exception as e:
                    review_detail["rating"] = None

                try:
                    text_sub_element = review_element.find_element(*review_text_locator)
                    review_detail["text"] = text_sub_element.text
                except Exception as e:
                    review_detail["text"] = ""

                try:
                    date_sub_element = review_element.find_element(*review_date_locator)
                    review_date_str = date_sub_element.text
                    review_detail["date"] = self._parse_date(review_date_str)
                except Exception as e:
                    review_detail["date"] = None

                try:
                    response_block = review_element.find_element(*response_block_locator)
                    response_text_element = response_block.find_element(*response_text_locator)
                    response_text = response_text_element.text
                    response_date_element = response_block.find_element(*response_date_locator)
                    response_date_str = response_date_element.text
                    response_date = self._parse_date(response_date_str)
                    review_detail["response"] = {"text": response_text, "date": response_date}
                    card_data["answered_reviews"] += 1

                    if review_detail["date"] and response_date:
                        time_diff = response_date - review_detail["date"]
                        response_times_seconds.append(time_diff.total_seconds())

                except Exception as e:
                    review_detail["response"] = None
                    card_data["unanswered_reviews"] += 1

                card_data["reviews"].append(review_detail)

                if review_detail.get("rating") is not None:
                    if review_detail["rating"] <= 3.0:
                        card_data["negative_reviews"] += 1
                    else:
                        card_data["positive_reviews"] += 1

            if response_times_seconds:
                card_data["avg_response_time_seconds"] = sum(response_times_seconds) / len(response_times_seconds)

        except Exception as e:
            return None

        return card_data

    def _scroll_to_load_more_elements(self, wait: WebDriverWait):
        last_height = self.driver.execute_script("return document.body.scrollHeight")
        scroll_pause_time = 3
        max_scrolls = 15

        for _ in range(max_scrolls):
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(scroll_pause_time)
            new_height = self.driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                break
            last_height = new_height