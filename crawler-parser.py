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



def search_products(product_name: str, retries=3):
    tries = 0
    success = False

    while tries < retries and not success:
        try:
            url = f"https://www.amazon.com/s?k={product_name}"
            resp = requests.get(url)

            if resp.status_code == 200:
                logger.info("Successfully fetched page")

                soup = BeautifulSoup(resp.text, "html.parser")

                divs = soup.find_all("div")

                last_title = ""
                for div in divs:
                    parsable = True if div is not None else False 
                    h2 = div.find("h2")
                    if h2 and h2.text.strip() and h2.text.strip() != last_title and parsable:
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
                            rating = float(rating_present)

                            price_present = prices[0].text.replace(pricing_unit, "").replace(",", "") if prices else "0.0"
                            price = float(price_present) if price_present else 0.0

                            real_price = float(prices[1].text.replace(pricing_unit, "").replace(",", "")) if len(prices) > 1 else price
                        

                        if symbol_presence and rating_present and price_present:
                            product = {
                                "name": asin,
                                "title": title,
                                "url": product_url,
                                "is_ad": ad_status,
                                "pricing_unit": pricing_unit,
                                "price": price,
                                "real_price": real_price,
                                "rating": rating
                            }

                            print(product)
                        

                        last_title = title
                    else:
                        continue
                success = True

            else:
        
                raise Exception(f"Failed to scrape the page, Status Code {resp.status_code}, tries left: {retries-tries}")
    
        except Exception as e:
            logger.warning(f"Failed to scrape page, {e}")
            tries += 1
        
    if not success:
        logger.warning(f"Failed to scrape page, retries exceeded: {retries}")


    print(f"Exited scrape_products for :{product_name}")




if __name__ == "__main__":

    PRODUCTS = ["phone"]
    MAX_RETRIES = 2


    for product in PRODUCTS:
        search_products(product, retries=MAX_RETRIES) 

    



