import os
import time
import random
import logging
from typing import Dict, Any, List, Optional
from bs4 import BeautifulSoup
import requests
from notion_client import Client
from dotenv import load_dotenv
from urllib.parse import urljoin, urlparse, parse_qs, urlencode
from datetime import datetime
from fake_useragent import UserAgent
import cloudscraper

# Konfiguracja logowania
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('scraper.log'),
        logging.StreamHandler()
    ]
)

# Załaduj zmienne środowiskowe
load_dotenv()

# Konfiguracja
NOTION_API_KEY = os.getenv('NOTION_API_KEY')
NOTION_DATABASE_ID = os.getenv('NOTION_DATABASE_ID')
BASE_URL = "https://www.otodom.pl"
LISTINGS_URL = "https://www.otodom.pl/pl/wyniki/sprzedaz/mieszkanie/cala-polska"

# Lista proxy - możesz dodać więcej
PROXY_LIST = [
    None,  # Bez proxy
    'http://proxy1.example.com:8080',  # Przykładowe proxy - zamień na działające
    'http://proxy2.example.com:8080',
]

# Inicjalizacja generatora User-Agent
ua = UserAgent()

# Sprawdzenie konfiguracji
if not NOTION_API_KEY:
    logging.error("NOTION_API_KEY nie jest ustawiony!")
    raise ValueError("NOTION_API_KEY nie jest ustawiony!")

if not NOTION_DATABASE_ID:
    logging.error("NOTION_DATABASE_ID nie jest ustawiony!")
    raise ValueError("NOTION_DATABASE_ID nie jest ustawiony!")

logging.info(f"NOTION_API_KEY length: {len(NOTION_API_KEY)}")
logging.info(f"NOTION_DATABASE_ID length: {len(NOTION_DATABASE_ID)}")

# Inicjalizacja klienta Notion
try:
    notion = Client(auth=NOTION_API_KEY)
    # Test połączenia
    notion.databases.retrieve(NOTION_DATABASE_ID)
    logging.info("Połączenie z Notion zostało ustanowione pomyślnie")
except Exception as e:
    logging.error(f"Błąd podczas inicjalizacji klienta Notion: {str(e)}")
    raise

def get_existing_ad_ids() -> set:
    """Pobiera listę istniejących ID ogłoszeń z bazy Notion"""
    try:
        results = []
        has_more = True
        start_cursor = None
        
        while has_more:
            response = notion.databases.query(
                database_id=NOTION_DATABASE_ID,
                start_cursor=start_cursor,
                page_size=100
            )
            
            for page in response["results"]:
                ad_id = page["properties"]["Ad ID"]["rich_text"]
                if ad_id:
                    results.append(ad_id[0]["text"]["content"])
            
            has_more = response["has_more"]
            if has_more:
                start_cursor = response["next_cursor"]
        
        logging.info(f"Pobrano {len(results)} istniejących ID z bazy Notion")
        return set(results)
    except Exception as e:
        logging.error(f"Błąd podczas pobierania istniejących ID: {str(e)}")
        raise

def is_valid_price(price: str) -> bool:
    """Sprawdza czy cena jest poprawna"""
    return bool(price and price.strip() and "zł" in price)

def get_random_proxy() -> Optional[Dict[str, str]]:
    """Zwraca losowe proxy z listy"""
    proxy = random.choice(PROXY_LIST)
    return {'http': proxy, 'https': proxy} if proxy else None

def get_headers() -> Dict[str, str]:
    """Zwraca nagłówki dla requestów z losowym User-Agent"""
    return {
        "User-Agent": ua.random,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "pl-PL,pl;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "DNT": "1",
        "Sec-Ch-Ua": '"Not_A Brand";v="8", "Chromium";v="120"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": '"Windows"',
        "Referer": "https://www.otodom.pl/"
    }

def create_scraper_session() -> cloudscraper.CloudScraper:
    """Tworzy nową sesję CloudScraper z losowymi parametrami"""
    return cloudscraper.create_scraper(
        browser={
            'browser': random.choice(['chrome', 'firefox']),
            'platform': 'windows',
            'mobile': False
        },
        debug=True
    )

def make_request(url: str, max_retries: int = 3, retry_delay: int = 5) -> Optional[requests.Response]:
    """Wykonuje request z obsługą błędów i ponownych prób"""
    scraper = create_scraper_session()
    
    for attempt in range(max_retries):
        try:
            # Dodaj losowe opóźnienie przed requestem
            time.sleep(random.uniform(2, 5))
            
            headers = get_headers()
            response = scraper.get(
                url,
                headers=headers,
                timeout=30,
                allow_redirects=True
            )
            
            if response.status_code == 403:
                logging.warning(f"Dostęp zabroniony (403) - próba {attempt + 1}/{max_retries}")
                # Zwiększ opóźnienie przy kolejnych próbach
                time.sleep(retry_delay * (attempt + 2))
                # Stwórz nową sesję
                scraper = create_scraper_session()
                continue
            
            response.raise_for_status()
            return response
            
        except Exception as e:
            logging.error(f"Błąd podczas wykonywania requestu (próba {attempt + 1}/{max_retries}): {str(e)}")
            if attempt < max_retries - 1:
                time.sleep(retry_delay * (attempt + 2))
                # Stwórz nową sesję przy błędzie
                scraper = create_scraper_session()
            else:
                logging.error(f"Nie udało się pobrać strony po {max_retries} próbach")
                return None
    
    return None

def get_next_page_url(current_url: str, page_number: int) -> str:
    """Generuje URL dla następnej strony"""
    parsed_url = urlparse(current_url)
    query_params = parse_qs(parsed_url.query)
    query_params['page'] = [str(page_number)]
    query_params['viewType'] = ['listing']
    
    new_query = urlencode(query_params, doseq=True)
    return f"{parsed_url.scheme}://{parsed_url.netloc}{parsed_url.path}?{new_query}"

def extract_text_from_element(soup: BeautifulSoup, selector: str, attribute: str = None) -> str:
    """Ekstrahuje tekst z elementu HTML"""
    try:
        element = soup.select_one(selector)
        if element:
            if attribute:
                return element.get(attribute, "").strip()
            # Usuń wszystkie style inline i klasy CSS
            for tag in element.find_all(True):
                tag.attrs = {}  # Usuń wszystkie atrybuty
            return element.get_text(separator=' ', strip=True)
        return ""
    except Exception as e:
        logging.error(f"Błąd podczas ekstrakcji tekstu: {str(e)}")
        return ""

def parse_listing_details(url: str) -> Optional[Dict[str, Any]]:
    """Parsuje szczegóły ogłoszenia"""
    try:
        response = make_request(url)
        if not response:
            return None
            
        soup = BeautifulSoup(response.text, 'html5lib')
        
        # Debug - zapisz HTML do pliku
        with open('debug_listing.html', 'w', encoding='utf-8') as f:
            f.write(response.text)
        
        # Ekstrakcja ID ogłoszenia
        ad_id = ""
        ad_id_selectors = [
            "[data-cy='adPageAdId']",
            "p[data-sentry-element='DetailsProperty']",
            "[data-testid='ad-id']"
        ]
        
        for selector in ad_id_selectors:
            ad_id = extract_text_from_element(soup, selector)
            if ad_id:
                ad_id = ad_id.split(":")[-1].strip()
                break
        
        if not ad_id:
            # Próbuj wyciągnąć ID z URL
            ad_id = url.split('/')[-1].split('.')[0]
        
        if ad_id in existing_ad_ids:
            logging.info(f"Ogłoszenie {ad_id} już istnieje w bazie. Pomijam.")
            return None
        
        # Ekstrakcja tytułu
        title_selectors = [
            "[data-cy='adPageAdTitle']",
            "h1[data-cy='adPageAdTitle']",
            "h1.css-1wnihf5",
            ".css-1wnihf5"
        ]
        
        title = ""
        for selector in title_selectors:
            title = extract_text_from_element(soup, selector)
            if title:
                break
        
        # Ekstrakcja ceny
        price_selectors = [
            "[data-cy='adPageHeaderPrice']",
            "strong[data-cy='adPageHeaderPrice']",
            ".css-8qi9av"
        ]
        
        price = ""
        for selector in price_selectors:
            price = extract_text_from_element(soup, selector)
            if is_valid_price(price):
                break
        
        if not is_valid_price(price):
            logging.info(f"Nieprawidłowa cena dla ogłoszenia {ad_id}. Pomijam.")
            return None
        
        # Ekstrakcja adresu
        address_selectors = [
            "[aria-label='Adres']",
            "[data-cy='adPageHeaderLocation']",
            "a[href='#map']",
            "div[data-testid='location-name']",
            ".css-1k13n9p"
        ]
        
        address = ""
        for selector in address_selectors:
            address = extract_text_from_element(soup, selector)
            if address and not address.startswith('.css'):
                break
        
        # Ekstrakcja szczegółów
        details = {}
        detail_selectors = [
            "div[data-cy='adPageAdditionalDetails'] div[data-testid='ad.top-information.table']",
            "div[data-testid='ad-details-table']",
            "div[data-sentry-element='ItemGridContainer']"
        ]
        
        for selector in detail_selectors:
            detail_items = soup.select(selector)
            if detail_items:
                for item in detail_items:
                    label_elem = item.select_one("div:first-child, span:first-child")
                    value_elem = item.select_one("div:last-child, span:last-child")
                    
                    if label_elem and value_elem:
                        label = label_elem.get_text(strip=True)
                        value = value_elem.get_text(strip=True)
                        
                        if any(keyword in label for keyword in ["Powierzchnia", "powierzchnia"]):
                            details["area"] = value
                        elif any(keyword in label for keyword in ["Liczba pokoi", "pokoje"]):
                            details["rooms"] = value
                        elif any(keyword in label for keyword in ["Rynek", "rynek"]):
                            details["market"] = value
                
                if details:  # Jeśli znaleźliśmy jakieś szczegóły, przerwij pętlę
                    break
        
        # Przygotuj dane do zapisania
        listing_data = {
            "title": title or "",
            "price": price or "",
            "address": address or "",
            "area": details.get("area", ""),
            "rooms": details.get("rooms", ""),
            "market": details.get("market", ""),
            "ad_id": ad_id,
            "url": url
        }
        
        # Debug log
        logging.info(f"Sparsowane dane ogłoszenia {ad_id}:")
        for key, value in listing_data.items():
            logging.info(f"{key}: {value}")
        
        return listing_data
        
    except Exception as e:
        logging.error(f"Błąd podczas parsowania ogłoszenia {url}: {str(e)}")
        return None

def get_current_date() -> str:
    """Zwraca aktualną datę w formacie ISO"""
    return datetime.now().date().isoformat()

def get_listing_links(page_url: str) -> List[str]:
    """Pobiera linki do ogłoszeń z danej strony"""
    try:
        response = make_request(page_url)
        if not response:
            logging.error(f"Nie udało się pobrać strony: {page_url}")
            return []
            
        soup = BeautifulSoup(response.text, 'html5lib')
        
        # Debug - zapisz HTML do pliku
        with open('debug_page.html', 'w', encoding='utf-8') as f:
            f.write(response.text)
        
        links = []
        # Próbuj różne selektory
        selectors = [
            "a[data-cy='listing-item-link']",
            "a[href*='/oferta/']",
            "article a[href*='/oferta/']",
            ".css-1tiwk2i a",
            "[data-cy='listing-item-link']",
            ".offer-item",
            ".css-14cy79a",
            "a[data-cy='listing-item-link']",
            "a[href*='/pl/oferta/']"
        ]
        
        for selector in selectors:
            listing_cards = soup.select(selector)
            if listing_cards:
                logging.info(f"Znaleziono {len(listing_cards)} elementów używając selektora: {selector}")
                for card in listing_cards:
                    href = card.get('href')
                    if href:
                        if not href.startswith('http'):
                            href = urljoin(BASE_URL, href)
                        if '/oferta/' in href and href not in links:
                            links.append(href)
                if links:
                    break
        
        if not links:
            logging.warning("Nie znaleziono żadnych linków do ogłoszeń")
            logging.debug(f"HTML strony zapisano do debug_page.html")
        else:
            logging.info(f"Znaleziono {len(links)} unikalnych linków do ogłoszeń")
            
        return links
    except Exception as e:
        logging.error(f"Błąd podczas pobierania linków ze strony {page_url}: {str(e)}")
        return []

def save_to_notion(listing_data: Dict[str, Any]) -> None:
    """Zapisuje dane ogłoszenia do bazy Notion"""
    try:
        logging.info(f"Próba zapisania ogłoszenia {listing_data['ad_id']} do Notion")
        logging.info("Dane do zapisania:")
        for key, value in listing_data.items():
            logging.info(f"{key}: {value}")

        # Sprawdź czy wszystkie wymagane pola są obecne
        required_fields = ["title", "price", "address", "area", "rooms", "market", "ad_id", "url"]
        missing_fields = [field for field in required_fields if not listing_data.get(field)]
        
        if missing_fields:
            logging.warning(f"Brakujące pola: {', '.join(missing_fields)}")
            
        # Przygotuj dane w formacie Notion API
        properties = {
            "Title": {
                "title": [
                    {
                        "text": {
                            "content": listing_data.get("title", "Brak tytułu")
                        }
                    }
                ]
            },
            "Price": {
                "rich_text": [
                    {
                        "text": {
                            "content": listing_data.get("price", "")
                        }
                    }
                ]
            },
            "Address": {
                "rich_text": [
                    {
                        "text": {
                            "content": listing_data.get("address", "")
                        }
                    }
                ]
            },
            "Area": {
                "rich_text": [
                    {
                        "text": {
                            "content": listing_data.get("area", "")
                        }
                    }
                ]
            },
            "Rooms": {
                "rich_text": [
                    {
                        "text": {
                            "content": listing_data.get("rooms", "")
                        }
                    }
                ]
            },
            "Market": {
                "rich_text": [
                    {
                        "text": {
                            "content": listing_data.get("market", "")
                        }
                    }
                ]
            },
            "Ad ID": {
                "rich_text": [
                    {
                        "text": {
                            "content": listing_data.get("ad_id", "")
                        }
                    }
                ]
            },
            "URL": {
                "url": listing_data.get("url", "")
            },
            "Date": {
                "date": {
                    "start": get_current_date()
                }
            }
        }

        # Zapisz do Notion
        try:
            response = notion.pages.create(
                parent={"database_id": NOTION_DATABASE_ID},
                properties=properties
            )
            logging.info(f"Pomyślnie zapisano ogłoszenie {listing_data['ad_id']} do Notion")
            logging.debug(f"Odpowiedź z Notion API: {response}")
            return True
        except Exception as notion_error:
            logging.error(f"Błąd podczas zapisywania do Notion API: {str(notion_error)}")
            if hasattr(notion_error, 'response'):
                logging.error(f"Szczegóły błędu: {notion_error.response.text}")
            return False
            
    except Exception as e:
        logging.error(f"Błąd podczas przygotowywania danych do zapisu: {str(e)}")
        return False

def scrape_listings():
    """Główna funkcja scrapująca"""
    try:
        global existing_ad_ids
        existing_ad_ids = get_existing_ad_ids()
        logging.info(f"Znaleziono {len(existing_ad_ids)} istniejących ogłoszeń w bazie")
        
        page_number = 1
        total_listings = 0
        max_pages = 100  # Limit stron do przeanalizowania
        
        while page_number <= max_pages:
            current_page_url = get_next_page_url(LISTINGS_URL, page_number)
            logging.info(f"\nPrzetwarzanie strony {page_number}: {current_page_url}")
            
            listing_links = get_listing_links(current_page_url)
            
            if not listing_links:
                logging.info(f"Nie znaleziono więcej ogłoszeń na stronie {page_number}. Kończenie...")
                break
                
            for link in listing_links:
                logging.info(f"\nPrzetwarzanie ogłoszenia: {link}")
                listing_data = parse_listing_details(link)
                
                if listing_data:
                    if save_to_notion(listing_data):
                        total_listings += 1
                        logging.info(f"Pomyślnie zapisano ogłoszenie {listing_data['ad_id']}")
                    else:
                        logging.error(f"Nie udało się zapisać ogłoszenia {listing_data['ad_id']}")
                
                time.sleep(random.uniform(2, 5))
            
            logging.info(f"\nZakończono stronę {page_number}. Zapisano {total_listings} ogłoszeń.")
            page_number += 1
            time.sleep(random.uniform(3, 7))
            
    except Exception as e:
        logging.error(f"Błąd podczas scrapowania: {str(e)}")
        raise

if __name__ == "__main__":
    try:
        logging.info("Rozpoczynanie scrapera...")
        if not NOTION_API_KEY or not NOTION_DATABASE_ID:
            logging.error("Błąd: Brak wymaganych zmiennych środowiskowych. Sprawdź plik .env")
            raise ValueError("Brak wymaganych zmiennych środowiskowych")
        scrape_listings()
        logging.info("Scraper zakończył działanie pomyślnie")
    except Exception as e:
        logging.error(f"Krytyczny błąd podczas działania scrapera: {str(e)}")
        raise 