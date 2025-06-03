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
import re

# Konfiguracja logowania
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('scraper.log', encoding='utf-8'),
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

def clean_text(text: str) -> str:
    """Czyści tekst z niepotrzebnych elementów"""
    # Usuń style CSS
    text = re.sub(r'\.css-[a-zA-Z0-9]+\{[^}]+\}', '', text)
    # Usuń niepotrzebne białe znaki
    text = ' '.join(text.split())
    return text.strip()

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
            
        logging.info(f"Parsowanie ogłoszenia z URL: {url}")

        # Ekstrakcja szczegółów - nowe podejście
        details = {}
        
        # Selektory dla różnych elementów
        selectors = {
            'area': {
                'containers': [
                    "div[data-sentry-element='ItemGridContainer'].css-1xw0jqp.esen0m91:-soup-contains('Powierzchnia')",
                    "div[data-testid='ad.top-information.table'] div:-soup-contains('Powierzchnia')",
                    "div.css-1k13n9p div:-soup-contains('Powierzchnia')",
                    "div[data-cy='adPageAdInfo'] div:-soup-contains('Powierzchnia')"
                ],
                'value_selectors': [
                    "p[data-sentry-element='Item'].esen0m92.css-1airkmu + p.esen0m92.css-1airkmu",
                    "p.esen0m92.css-1airkmu:last-child",
                    "p.css-1airkmu:last-child",
                    "div.css-1wi2w6s",
                    "span.css-1wi2w6s",
                    "strong"
                ]
            },
            'rooms': {
                'containers': [
                    "div[data-sentry-element='ItemGridContainer'].css-1xw0jqp.esen0m91:-soup-contains('Liczba pokoi')",
                    "div[data-testid='ad.top-information.table'] div:-soup-contains('Liczba pokoi')",
                    "div.css-1k13n9p div:-soup-contains('Liczba pokoi')",
                    "div[data-cy='adPageAdInfo'] div:-soup-contains('Liczba pokoi')"
                ],
                'value_selectors': [
                    "p[data-sentry-element='Item'].esen0m92.css-1airkmu + p.esen0m92.css-1airkmu",
                    "p.esen0m92.css-1airkmu:last-child",
                    "p.css-1airkmu:last-child",
                    "div.css-1wi2w6s",
                    "span.css-1wi2w6s",
                    "strong"
                ]
            },
            'market': {
                'containers': [
                    "div[data-sentry-element='ItemGridContainer'].css-1xw0jqp.esen0m91:-soup-contains('Rynek')",
                    "div[data-testid='ad.top-information.table'] div:-soup-contains('Rynek')",
                    "div.css-1k13n9p div:-soup-contains('Rynek')",
                    "div[data-cy='adPageAdInfo'] div:-soup-contains('Rynek')"
                ],
                'value_selectors': [
                    "p[data-sentry-element='Item'].esen0m92.css-1airkmu + p.esen0m92.css-1airkmu",
                    "p.esen0m92.css-1airkmu:last-child",
                    "p.css-1airkmu:last-child",
                    "div.css-1wi2w6s",
                    "span.css-1wi2w6s",
                    "strong"
                ]
            }
        }

        # Najpierw próbujemy znaleźć wartości używając ogólnych selektorów
        for field, field_config in selectors.items():
            if field not in details or not details[field]:
                for container_selector in field_config['containers']:
                    try:
                        containers = soup.select(container_selector)
                        for container in containers:
                            if container:
                                container_text = clean_text(container.get_text())
                                logging.info(f"Znaleziono kontener dla {field}: {container_selector}")
                                logging.info(f"Tekst kontenera: {container_text}")
                                
                                # Próbujemy znaleźć wartość bezpośrednio w kontenerze
                                if container_text:
                                    if field == 'area':
                                        area_match = re.search(r'(\d+[.,]?\d*)\s*m[²2]', container_text)
                                        if area_match:
                                            area_value = float(area_match.group(1).replace(',', '.'))
                                            if area_value > 0:
                                                details[field] = f"{area_value:.1f} m²"
                                                logging.info(f"Znaleziono powierzchnię: {details[field]}")
                                                break
                                    elif field == 'rooms':
                                        rooms_match = re.search(r'(\d+)\s*(?:pok|pokoi|pokoje)?', container_text)
                                        if rooms_match:
                                            rooms_value = int(rooms_match.group(1))
                                            if 0 < rooms_value <= 10:
                                                details[field] = str(rooms_value)
                                                logging.info(f"Znaleziono liczbę pokoi: {details[field]}")
                                                break
                                    elif field == 'market':
                                        market_match = re.search(r'(wtórny|pierwotny)', container_text.lower())
                                        if market_match:
                                            details[field] = market_match.group(1)
                                            logging.info(f"Znaleziono rynek: {details[field]}")
                                            break
                                        elif "deweloper" in container_text.lower():
                                            details[field] = "pierwotny"
                                            logging.info(f"Znaleziono rynek (deweloper): {details[field]}")
                                            break
                                
                                # Jeśli nie znaleziono wartości bezpośrednio, próbujemy użyć selektorów wartości
                                for value_selector in field_config['value_selectors']:
                                    try:
                                        value_elements = container.select(value_selector)
                                        for value_element in value_elements:
                                            if value_element:
                                                value = clean_text(value_element.text)
                                                logging.info(f"Znaleziono wartość dla {field}: {value}")
                                                
                                                if field == 'area':
                                                    area_match = re.search(r'(\d+[.,]?\d*)\s*m[²2]', value)
                                                    if area_match:
                                                        area_value = float(area_match.group(1).replace(',', '.'))
                                                        if area_value > 0:
                                                            details[field] = f"{area_value:.1f} m²"
                                                            break
                                                elif field == 'rooms':
                                                    rooms_match = re.search(r'(\d+)\s*(?:pok|pokoi|pokoje)?', value)
                                                    if rooms_match:
                                                        rooms_value = int(rooms_match.group(1))
                                                        if 0 < rooms_value <= 10:
                                                            details[field] = str(rooms_value)
                                                            logging.info(f"Znaleziono liczbę pokoi: {details[field]}")
                                                            break
                                                elif field == 'market':
                                                    market_match = re.search(r'(wtórny|pierwotny)', value.lower())
                                                    if market_match:
                                                        details[field] = market_match.group(1)
                                                        break
                                                    elif "deweloper" in value.lower():
                                                        details[field] = "pierwotny"
                                                        break
                                    except Exception as e:
                                        logging.debug(f"Błąd przy próbie użycia selektora {value_selector}: {str(e)}")
                                        continue
                            
                            if field in details:
                                break
                    except Exception as e:
                        logging.debug(f"Błąd przy próbie użycia selektora kontenera {container_selector}: {str(e)}")
                        continue
                    
                    if field in details:
                        break

        # 2. Próba: Szukanie w opisie ogłoszenia
        description = ""
        desc_selectors = [
            "div[data-cy='adPageDescription']",
            "div[data-testid='ad.description']"
        ]
        
        for selector in desc_selectors:
            desc_elem = soup.select_one(selector)
            if desc_elem:
                description = clean_text(desc_elem.get_text(strip=True)).lower()
                break

        if description:
            # Szukaj powierzchni w opisie
            if not details.get("area"):
                area_matches = re.finditer(r'(\d+(?:[,.]\d+)?)\s*m[²2]', description)
                for match in area_matches:
                    area = match.group(0)
                    if float(re.sub(r'[^\d.,]', '', area).replace(',', '.')) > 10:  # Sprawdź czy powierzchnia jest sensowna
                        details["area"] = area
                        logging.info(f"Znaleziono powierzchnię w opisie: {area}")
                        break

            # Szukaj liczby pokoi w opisie
            if not details.get("rooms"):
                rooms_matches = re.finditer(r'(\d+)[\s-]?(?:pok|pokoj|pokoje|pokoi)', description)
                for match in rooms_matches:
                    rooms = match.group(1)
                    if 1 <= int(rooms) <= 10:  # Sprawdź czy liczba pokoi jest sensowna
                        details["rooms"] = f"{rooms} pokoje"
                        logging.info(f"Znaleziono liczbę pokoi w opisie: {rooms}")
                        break

        # 3. Próba: Szukanie w tytule
        title = ""
        title_selectors = [
            "h1.css-1wnihf5",
            "[data-cy='adPageAdTitle']",
            "h1[data-cy='adPageAdTitle']",
            "div.css-1wnihf5 h1"
        ]
        
        for selector in title_selectors:
            element = soup.select_one(selector)
            if element:
                title = clean_text(element.get_text(strip=True))
                logging.info(f"Znaleziono tytuł używając selektora: {selector}")
                logging.info(f"Tytuł: {title}")
                break

        if title:
            # Szukaj powierzchni w tytule
            if not details.get("area"):
                area_match = re.search(r'(\d+(?:[,.]\d+)?)\s*m[²2]', title.lower())
                if area_match:
                    details["area"] = area_match.group(0)
                    logging.info(f"Znaleziono powierzchnię w tytule: {details['area']}")

            # Szukaj liczby pokoi w tytule
            if not details.get("rooms"):
                rooms_match = re.search(r'(\d+)\s*(?:pok|pokoi|pokoje)', title.lower())
                if rooms_match:
                    rooms = rooms_match.group(1)
                    if 1 <= int(rooms) <= 10:
                        details["rooms"] = f"{rooms} pokoje"
                        logging.info(f"Znaleziono liczbę pokoi w tytule: {details['rooms']}")

        # Ekstrakcja ID ogłoszenia
        ad_id = ""
        ad_id_selectors = [
            "[data-cy='adPageAdId']",
            "p[data-sentry-element='DetailsProperty']",
            "[data-testid='ad-id']",
            "div.css-1k13n9p"
        ]
        
        for selector in ad_id_selectors:
            element = soup.select_one(selector)
            if element:
                logging.info(f"Znaleziono element ID używając selektora: {selector}")
                text = element.get_text(strip=True)
                if ":" in text:
                    ad_id = text.split(":")[-1].strip()
                else:
                    ad_id = text.strip()
                if ad_id:
                    break
        
        if not ad_id:
            # Próbuj wyciągnąć ID z URL
            ad_id = url.split('/')[-1].split('.')[0]
            logging.info(f"Wyciągnięto ID z URL: {ad_id}")
        
        if ad_id in existing_ad_ids:
            logging.info(f"Ogłoszenie {ad_id} już istnieje w bazie. Pomijam.")
            return None
            
        # Ekstrakcja ceny
        price = ""
        price_selectors = [
            "strong.css-8qi9av",
            "[data-cy='adPageHeaderPrice']",
            "strong[data-cy='adPageHeaderPrice']",
            "div.css-8qi9av",
            "strong.css-t80apw",  # Nowy selektor
            "[data-testid='ad-price-value']",  # Nowy selektor
            "div.css-1vr19r7",  # Nowy selektor
            "div[data-testid='ad.price-value']"  # Nowy selektor
        ]
        
        for selector in price_selectors:
            try:
                elements = soup.select(selector)
                for element in elements:
                    if element:
                        price_text = clean_text(element.get_text(strip=True))
                        # Usuń tekst "od" z ceny
                        price_text = re.sub(r'^od\s+', '', price_text, flags=re.IGNORECASE)
                        logging.info(f"Znaleziono potencjalną cenę: {price_text}")
                        
                        if is_valid_price(price_text):
                            price = price_text
                            logging.info(f"Zaakceptowano cenę: {price}")
                            break
                if price:
                    break
            except Exception as e:
                logging.debug(f"Błąd przy próbie użycia selektora ceny {selector}: {str(e)}")
                continue
        
        if not is_valid_price(price):
            logging.info(f"Nieprawidłowa cena dla ogłoszenia {ad_id}. Pomijam.")
            return None
        
        # Ekstrakcja adresu
        address = ""
        address_selectors = [
            "a.css-1k13n9p",
            "[data-cy='adPageHeaderLocation']",
            "a[href='#map']",
            "div[data-testid='location-name']",
            "div.css-1k13n9p",
            "span.css-17o5lya",
            "[aria-label='Adres']"
        ]
        
        for selector in address_selectors:
            element = soup.select_one(selector)
            if element:
                address = clean_text(element.get_text(strip=True))
                logging.info(f"Znaleziono adres używając selektora: {selector}")
                logging.info(f"Adres: {address}")
                if address and not address.startswith('.css'):
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
        logging.info("Sparsowane dane ogłoszenia:")
        for key, value in listing_data.items():
            logging.info(f"{key}: {value}")
        
        return listing_data
        
    except Exception as e:
        logging.error(f"Błąd podczas parsowania ogłoszenia {url}: {str(e)}")
        import traceback
        logging.error(f"Traceback: {traceback.format_exc()}")
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

def test_selectors_on_page(soup: BeautifulSoup) -> Dict[str, str]:
    """Testuje selektory na stronie ogłoszenia i zwraca znalezione dane"""
    results = {}
    
    # Selektory dla różnych elementów
    selectors = {
        'area': {
            'containers': [
                "div:-soup-contains('Powierzchnia') + div",
                "div:-soup-contains('powierzchnia') + div",
                "div[data-testid='ad.top-information.table'] div:-soup-contains('Powierzchnia') + div",
                "div.css-1k13n9p div:-soup-contains('Powierzchnia') + div",
                "[data-testid='ad-info'] div:-soup-contains('Powierzchnia')",
                "div[data-cy='adPageAdInfo'] div:-soup-contains('Powierzchnia')",
                "div.css-1qzl8qx",  # Nowy selektor dla rynku pierwotnego
                "div.css-1k13n9p"   # Nowy selektor dla rynku pierwotnego
            ],
            'value_selectors': [
                "p.esen0m92.css-1airkmu:last-child",
                "div.css-1wi2w6s",
                "span.css-1wi2w6s",
                "strong",
                ".css-1wi2w6s",
                ".css-1airkmu",
                "div[data-testid='ad-info'] div:-soup-contains('Powierzchnia')",
                "div.css-1qzl8qx"  # Nowy selektor dla rynku pierwotnego
            ]
        },
        'rooms': {
            'containers': [
                "div:-soup-contains('Liczba pokoi') + div",
                "div:-soup-contains('pokoje') + div",
                "div[data-testid='ad.top-information.table'] div:-soup-contains('Liczba pokoi') + div",
                "div.css-1k13n9p div:-soup-contains('Liczba pokoi') + div",
                "[data-testid='ad-info'] div:-soup-contains('Liczba pokoi')",
                "div[data-cy='adPageAdInfo'] div:-soup-contains('Liczba pokoi')",
                "div.css-1qzl8qx",  # Nowy selektor dla rynku pierwotnego
                "div.css-1k13n9p"   # Nowy selektor dla rynku pierwotnego
            ],
            'value_selectors': [
                "p.esen0m92.css-1airkmu:last-child",
                "div.css-1wi2w6s",
                "span.css-1wi2w6s",
                "strong",
                ".css-1wi2w6s",
                ".css-1airkmu",
                "div[data-testid='ad-info'] div:-soup-contains('Liczba pokoi')",
                "div.css-1qzl8qx"  # Nowy selektor dla rynku pierwotnego
            ]
        },
        'market': {
            'containers': [
                "div:-soup-contains('Rynek') + div",
                "div:-soup-contains('Typ rynku') + div",
                "div[data-testid='ad.top-information.table'] div:-soup-contains('Rynek') + div",
                "div.css-1k13n9p div:-soup-contains('Rynek') + div",
                "[data-testid='ad-info'] div:-soup-contains('Rynek')",
                "div[data-cy='adPageAdInfo'] div:-soup-contains('Rynek')",
                "div.css-1qzl8qx",  # Nowy selektor dla rynku pierwotnego
                "div.css-1k13n9p"   # Nowy selektor dla rynku pierwotnego
            ],
            'value_selectors': [
                "p.esen0m92.css-1airkmu:last-child",
                "div.css-1wi2w6s",
                "span.css-1wi2w6s",
                "strong",
                ".css-1wi2w6s",
                ".css-1airkmu",
                "div[data-testid='ad-info'] div:-soup-contains('Rynek')",
                "div.css-1qzl8qx"  # Nowy selektor dla rynku pierwotnego
            ]
        }
    }
    
    for field, field_selectors in selectors.items():
        logging.info(f"\n🔍 Szukam {field}:")
        
        for container_selector in field_selectors['containers']:
            try:
                container = soup.select_one(container_selector)
                if container:
                    logging.info(f"  ✓ Znaleziono kontener: {container_selector}")
                    
                    for value_selector in field_selectors['value_selectors']:
                        try:
                            # Próbujemy znaleźć wartość względem kontenera
                            value_element = container.select_one(value_selector)
                            
                            if value_element:
                                value = clean_text(value_element.text)
                                logging.info(f"    ✓ Znaleziono wartość: {value} (selektor: {value_selector})")
                                
                                # Walidacja i formatowanie wartości
                                if field == 'area' and 'm²' in value:
                                    area_value = float(re.search(r'(\d+[.,]?\d*)', value.replace(',', '.')).group(1))
                                    if area_value > 0:
                                        results[field] = f"{area_value:.1f} m²"
                                        break
                                elif field == 'rooms' and any(char.isdigit() for char in value):
                                    rooms_value = int(re.search(r'(\d+)', value).group(1))
                                    if rooms_value > 0:
                                        results[field] = str(rooms_value)
                                        break
                                elif field == 'market':
                                    results[field] = value
                                    break
                            
                        except Exception as e:
                            logging.debug(f"    ⚠ Błąd przy próbie użycia selektora {value_selector}: {str(e)}")
                            continue
                    
                    if field in results:
                        break
                        
            except Exception as e:
                logging.debug(f"  ⚠ Błąd przy próbie użycia selektora kontenera {container_selector}: {str(e)}")
                continue
        
        if field not in results:
            logging.warning(f"❌ Nie udało się znaleźć {field}")
        else:
            logging.info(f"✅ Znaleziono {field}: {results[field]}")
    
    return results

def test_url_scraping(url: str) -> None:
    """Testuje scrapowanie danych z podanego URL"""
    logging.info(f"\n{'='*80}\nTestuję scrapowanie URL: {url}\n{'='*80}")
    
    try:
        # Inicjalizacja zmiennej existing_ad_ids jako pustego zbioru dla testów
        global existing_ad_ids
        existing_ad_ids = set()
        
        # Pobierz stronę
        response = make_request(url)
        if not response:
            logging.error("❌ Nie udało się pobrać strony!")
            return
            
        logging.info("✅ Strona pobrana pomyślnie")
            
        # Parsuj HTML
        soup = BeautifulSoup(response.text, 'html5lib')
        
        # Zapisz HTML do pliku (do debugowania)
        with open('debug_test.html', 'w', encoding='utf-8') as f:
            f.write(response.text)
        logging.info("✅ Zapisano HTML do pliku debug_test.html")
        
        # Testuj parsowanie danych
        listing_data = parse_listing_details(url)
        
        if listing_data:
            logging.info("\n📊 Podsumowanie wyników parsowania:")
            logging.info("-" * 40)
            for field, value in listing_data.items():
                if value:
                    logging.info(f"✅ {field}: {value}")
                else:
                    logging.info(f"❌ {field}: Brak danych")
            logging.info("-" * 40)
        else:
            logging.error("❌ Nie udało się sparsować danych z ogłoszenia!")
            
    except Exception as e:
        logging.error(f"❌ Błąd podczas testowania URL: {str(e)}")
        import traceback
        logging.error(f"Szczegóły błędu:\n{traceback.format_exc()}")

if __name__ == "__main__":
    try:
        logging.info("Rozpoczynanie scrapera...")
        if not NOTION_API_KEY or not NOTION_DATABASE_ID:
            logging.error("Błąd: Brak wymaganych zmiennych środowiskowych. Sprawdź plik .env")
            raise ValueError("Brak wymaganych zmiennych środowiskowych")
            
        scrape_listings()
        logging.info("Scraping zakończony pomyślnie")
    except Exception as e:
        logging.error(f"Krytyczny błąd podczas działania scrapera: {str(e)}")
        raise 