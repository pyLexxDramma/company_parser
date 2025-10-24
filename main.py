from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from src.parsers.gis2_parser import GIS2Parser
import time
import os


def load_proxies(filepath="proxies.txt"):
    proxies = []
    if not os.path.exists(filepath):
        print(f"Proxy file not found: {filepath}")
        return proxies
    try:
        with open(filepath, "r") as f:
            for line in f:
                proxy = line.strip()
                if proxy:
                    proxies.append(proxy)
    except Exception as e:
        print(f"Error loading proxies from {filepath}: {e}")
    return proxies


def setup_driver():
    options = webdriver.ChromeOptions()
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')

    proxies = load_proxies()
    if proxies:
        proxy = proxies[0]
        options.add_argument(f'--proxy-server={proxy}')
        print(f"Using proxy: {proxy}")

    script_dir = os.path.dirname(__file__)
    driver_path = os.path.join(script_dir, 'chromedriver.exe')

    if not os.path.exists(driver_path):
        raise FileNotFoundError(
            f"ChromeDriver not found at {driver_path}. Please ensure it's in the project root or specify the correct path.")

    service = Service(executable_path=driver_path)
    driver = webdriver.Chrome(service=service, options=options)
    return driver


def main():
    company_name_input = "ООО Ромашка"
    company_site_input = "example.com"
    email_input = "test@example.com"

    driver = None
    try:
        driver = setup_driver()

        print("\n--- Starting 2GIS Parsing ---")
        gis_parser = GIS2Parser(driver=driver, company_name=company_name_input, company_site=company_site_input)

        report_data_gis = gis_parser.analyze_platform_data()
        print(f" 2GIS Parsing finished. Data received: {report_data_gis}")

    except FileNotFoundError as fnf_error:
        print(f"Configuration error: {fnf_error}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
    finally:
        if driver:
            print("\n--- Quitting driver ---")
            driver.quit()


if __name__ == "__main__":
    main()