import requests
from bs4 import BeautifulSoup
import logging, os
import json, csv
from dataclasses import dataclass, field, fields, asdict
from urllib.parse import urlencode
from concurrent.futures import ThreadPoolExecutor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

API_KEY = "YOUR-SUPER-SECRET-API-KEY"


@dataclass
class ProductData:
    name: str = ""
    title: str = ""
    url: str = "",
    is_ad: bool = False,
    pricing_unit: str = "",
    price: float = None,
    real_price: float = None,
    rating: float = None

    def __post_init__(self):
        self.check_string_fields()
        
    def check_string_fields(self):
        for field in fields(self):
            # Check string fields
            if isinstance(getattr(self, field.name), str):
                # If empty set default text
                if getattr(self, field.name) == '':
                    setattr(self, field.name, f"No {field.name}")
                    continue
                # Strip any trailing spaces, etc.
                value = getattr(self, field.name)
                setattr(self, field.name, value.strip())


class DataPipeline:
    
    def __init__(self, csv_filename='', storage_queue_limit=50):
        self.names_seen = []
        self.storage_queue = []
        self.storage_queue_limit = storage_queue_limit
        self.csv_filename = csv_filename
        self.csv_file_open = False
    
    def save_to_csv(self):
        self.csv_file_open = True
        data_to_save = []
        data_to_save.extend(self.storage_queue)
        self.storage_queue.clear()
        if not data_to_save:
            return

        keys = [field.name for field in fields(data_to_save[0])]
        file_exists = os.path.isfile(self.csv_filename) and os.path.getsize(self.csv_filename) > 0
        with open(self.csv_filename, mode='a', newline='', encoding='utf-8') as output_file:
            writer = csv.DictWriter(output_file, fieldnames=keys)

            if not file_exists:
                writer.writeheader()

            for item in data_to_save:
                writer.writerow(asdict(item))

        self.csv_file_open = False
                    
    def is_duplicate(self, input_data):
        if input_data.name in self.names_seen:
            logger.warning(f"Duplicate item found: {input_data.name}. Item dropped.")
            return True
        self.names_seen.append(input_data.name)
        return False
            
    def add_data(self, scraped_data):
        if self.is_duplicate(scraped_data) == False:
            self.storage_queue.append(scraped_data)
            if len(self.storage_queue) >= self.storage_queue_limit and self.csv_file_open == False:
                self.save_to_csv()
                       
    def close_pipeline(self):
        if self.csv_file_open:
            time.sleep(3)
        if len(self.storage_queue) > 0:
            self.save_to_csv()


def search_products(product_name: str, page_number=1, location="us", retries=3, data_pipeline=None):
    tries = 0
    success = False

    while tries < retries and not success:
        try:
            url = f"https://www.amazon.com/s?k={product_name}&page={page_number}"
            print(url)
            resp = requests.get(url)

            if resp.status_code == 200:
                logger.info("Successfully fetched page")

                soup = BeautifulSoup(resp.text, "html.parser")

                
                bad_divs = soup.find_all("div", class_="AdHolder")


                for bad_div in bad_divs:
                    bad_div.decompose()

                divs = soup.find_all("div")

                last_title = ""
                for div in divs:
                    parsable = True if div is not None else False 
                    h2 = div.find("h2")
                    if h2 and h2.text.strip() and h2.text.strip() and parsable:
                        title = h2.text.strip()
                        a = h2.find("a")
                        product_url = a.get("href") if a else ""
                        ad_status = False
                        if "sspa" in product_url:
                            ad_status = True
                        asin = div.get("data-asin")
                        symbol_element = div.find("span", class_="a-price-symbol")
                        symbol_presence = symbol_element.text if symbol_element else None
                        if symbol_presence is not None:
                            pricing_unit = symbol_presence
                            prices = div.find_all("span", class_="a-offscreen")

                            rating_element = div.find("span", class_="a-icon-alt")
                            rating_present = rating_element.text[0:3] if rating_element else "0.0"
                            print(rating_present)
                            print(title)
                            rating = float(rating_present)

                            price_present = prices[0].text.replace(pricing_unit, "").replace(",", "") if prices else "0.0"
                            price = float(price_present) if price_present else 0.0

                            real_price = float(prices[1].text.replace(pricing_unit, "").replace(",", "")) if len(prices) > 1 else price
                        

                        if symbol_presence and rating_present and price_present:
                            product = ProductData(
                                name=asin,
                                title=title,
                                url=product_url,
                                is_ad=ad_status,
                                pricing_unit=pricing_unit,
                                price=price,
                                real_price=real_price,
                                rating=rating
                            )

                            data_pipeline.add_data(product)
                        

                        last_title = title
                    else:
                        continue
                success = True

            else:
        
                raise Exception(f"Failed to scrape the page {page_number}, Status Code {resp.status_code}, tries left: {retries-tries}")
    
        except Exception as e:
            logger.warning(f"Failed to scrape page, {e}")
            tries += 1
    
        
    if not success:
        logger.warning(f"Failed to scrape page, retries exceeded: {retries}")


    print(f"Exited scrape_products for :{product_name}")

def threaded_search(product_name, pages, max_workers=5, location="us", retries=3):
    search_pipeline = DataPipeline(csv_filename=f"{product_name}.csv")

    pages = list(range(1, pages+1))

    with ThreadPoolExecutor(max_workers=max_workers) as executor:                
        executor.map(
            search_products,
            [product_name] * len(pages),
            pages,
            [location] * len(pages),
            [retries] * len(pages),
            [search_pipeline] * len(pages)
            )

    search_pipeline.close_pipeline()



if __name__ == "__main__":

    PRODUCTS = ["phone"]
    MAX_RETRIES = 2
    PAGES = 5
    MAX_THREADS = 3
    LOCATION = "us"

    for product in PRODUCTS:
        threaded_search(product, PAGES, max_workers=MAX_THREADS, retries=MAX_RETRIES, location=LOCATION)