import sys
import os
import json

current_dir = os.path.dirname(__file__)
src_path = os.path.abspath(os.path.join(current_dir, 'src'))

if src_path not in sys.path:
    sys.path.insert(0, src_path)

from parsers.yandex_parser import YandexParser

def main():
    print("--- Запуск парсера ---")

    company_name = "ВкусВилл"
    website = "vkusvill.ru"

    print(f"Поиск компании: {company_name} ({website})")

    yandex_parser = YandexParser(company_name, website)

    analysis_results = yandex_parser.analyze_cards()

    print("\n--- Результаты анализа поиска ---")
    print(json.dumps(analysis_results, indent=4, ensure_ascii=False))

if __name__ == "__main__":
    main()