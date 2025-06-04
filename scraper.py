import os
import time
import random
import logging
from typing import Dict, Any, List, Optional
from bs4 import BeautifulSoup
import requests
from dotenv import load_dotenv
from urllib.parse import urljoin, urlparse, parse_qs, urlencode
from datetime import datetime
from fake_useragent import UserAgent
import cloudscraper
import re
import pymysql
from concurrent.futures import ThreadPoolExecutor, as_completed

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
BASE_URL = "https://www.otodom.pl"
LISTINGS_URL = "https://www.otodom.pl/pl/wyniki/sprzedaz/mieszkanie/cala-polska"

# Konfiguracja bazy danych
DB_SERVERNAME = os.getenv('DB_SERVERNAME')
DB_USERNAME = os.getenv('DB_USERNAME')
DB_PASSWORD = os.getenv('DB_PASSWORD')
DB_NAME = os.getenv('DB_NAME')
DB_PORT = int(os.getenv('DB_PORT', 3306))

# Lista proxy - możesz dodać więcej
PROXY_LIST = [
    None,  # Bez proxy
    'http://proxy1.example.com:8080',  # Przykładowe proxy - zamień na działające
    'http://proxy2.example.com:8080',
]

# Inicjalizacja generatora User-Agent
ua = UserAgent()

# Sprawdzenie konfiguracji
#if not DB_SERVERNAME or not DB_USERNAME or not DB_PASSWORD or not DB_NAME:
   # logging.error("Błąd: Brak wymaganych zmiennych środowiskowych. Sprawdź plik .env")
    #raise ValueError("Brak wymaganych zmiennych środowiskowych")

#logging.info(f"DB_SERVERNAME length: {len(DB_SERVERNAME)}")
#logging.info(f"DB_USERNAME length: {len(DB_USERNAME)}")
#logging.info(f"DB_PASSWORD length: {len(DB_PASSWORD)}")
#logging.info(f"DB_NAME length: {len(DB_NAME)}")

# Inicjalizacja połączenia z bazą danych
try:
    db_conn = pymysql.connect(
        host=DB_SERVERNAME,
        user=DB_USERNAME,
        password=DB_PASSWORD,
        database=DB_NAME,
        port=DB_PORT,
        charset='utf8mb4',
        cursorclass=pymysql.cursors.DictCursor
    )
    logging.info('Połączenie z bazą danych zostało ustanowione pomyślnie')
except Exception as e:
    logging.error(f'Błąd podczas łączenia z bazą danych: {str(e)}')
    db_conn = None

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
            logging.error(f"❌ Nie udało się pobrać strony: {url}")
            return None
            
        logging.info(f"✅ Pobrano stronę: {url}")
        logging.info(f"Status code: {response.status_code}")
        logging.info(f"Content length: {len(response.text)}")
        
        soup = BeautifulSoup(response.text, 'html5lib')
        
        # Debug - zapisz HTML do pliku
        debug_file = 'debug_listing.html'
        with open(debug_file, 'w', encoding='utf-8') as f:
            f.write(response.text)
        logging.info(f"✅ Zapisano HTML do pliku {debug_file}")
            
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
                    "div[data-cy='adPageAdInfo'] div:-soup-contains('Powierzchnia')",
                    "div.css-1qzl8qx",
                    "div.css-1k13n9p"
                ],
                'value_selectors': [
                    "p[data-sentry-element='Item'].esen0m92.css-1airkmu + p.esen0m92.css-1airkmu",
                    "div.css-1wi2w6s",
                    "span.css-1wi2w6s",
                    "strong",
                    ".css-1wi2w6s",
                    ".css-1airkmu"
                ]
            },
            'rooms': {
                'containers': [
                    "div[data-sentry-element='ItemGridContainer'].css-1xw0jqp.esen0m91:-soup-contains('Liczba pokoi')",
                    "div[data-testid='ad.top-information.table'] div:-soup-contains('Liczba pokoi')",
                    "div.css-1k13n9p div:-soup-contains('Liczba pokoi')",
                    "div[data-cy='adPageAdInfo'] div:-soup-contains('Liczba pokoi')",
                    "div.css-1qzl8qx",
                    "div.css-1k13n9p"
                ],
                'value_selectors': [
                    "p[data-sentry-element='Item'].esen0m92.css-1airkmu + p.esen0m92.css-1airkmu",
                    "div.css-1wi2w6s",
                    "span.css-1wi2w6s",
                    "strong",
                    ".css-1wi2w6s",
                    ".css-1airkmu"
                ]
            },
            'market': {
                'containers': [
                    "div[data-sentry-element='ItemGridContainer'].css-1xw0jqp.esen0m91:-soup-contains('Rynek')",
                    "div[data-testid='ad.top-information.table'] div:-soup-contains('Rynek')",
                    "div.css-1k13n9p div:-soup-contains('Rynek')",
                    "div[data-cy='adPageAdInfo'] div:-soup-contains('Rynek')",
                    "div.css-1qzl8qx",
                    "div.css-1k13n9p"
                ],
                'value_selectors': [
                    "p[data-sentry-element='Item'].esen0m92.css-1airkmu + p.esen0m92.css-1airkmu",
                    "div.css-1wi2w6s",
                    "span.css-1wi2w6s",
                    "strong",
                    ".css-1wi2w6s",
                    ".css-1airkmu"
                ]
            }
        }

        # Najpierw próbujemy znaleźć wartości używając ogólnych selektorów
        for field, field_config in selectors.items():
            logging.info(f"\n🔍 Szukam {field}:")
            
            for container_selector in field_config['containers']:
                try:
                    containers = soup.select(container_selector)
                    logging.info(f"  Próba użycia selektora kontenera: {container_selector}")
                    logging.info(f"  Znaleziono {len(containers)} kontenerów")
                    
                    for container in containers:
                        if container:
                            container_text = clean_text(container.get_text())
                            logging.info(f"  ✓ Znaleziono kontener: {container_selector}")
                            logging.info(f"  Tekst kontenera: {container_text}")
                            
                            # Próbujemy znaleźć wartość bezpośrednio w kontenerze
                            if container_text:
                                if field == 'area':
                                    area_match = re.search(r'(\d+[.,]?\d*)\s*m[²2]', container_text)
                                    if area_match:
                                        area_value = float(area_match.group(1).replace(',', '.'))
                                        if area_value > 0:
                                            details[field] = f"{area_value:.1f} m²"
                                            logging.info(f"    ✓ Znaleziono powierzchnię: {details[field]}")
                                            break
                                elif field == 'rooms':
                                    rooms_match = re.search(r'(\d+)\s*(?:pok|pokoi|pokoje)?', container_text)
                                    if rooms_match:
                                        rooms_value = int(rooms_match.group(1))
                                        if 0 < rooms_value <= 10:
                                            details[field] = str(rooms_value)
                                            logging.info(f"    ✓ Znaleziono liczbę pokoi: {details[field]}")
                                            break
                                elif field == 'market':
                                    market_match = re.search(r'(wtórny|pierwotny)', container_text.lower())
                                    if market_match:
                                        details[field] = market_match.group(1)
                                        logging.info(f"    ✓ Znaleziono rynek: {details[field]}")
                                        break
                                    elif "deweloper" in container_text.lower():
                                        details[field] = "pierwotny"
                                        logging.info(f"    ✓ Znaleziono rynek (deweloper): {details[field]}")
                                        break
                            
                            # Jeśli nie znaleziono wartości bezpośrednio, próbujemy użyć selektorów wartości
                            for value_selector in field_config['value_selectors']:
                                try:
                                    value_elements = container.select(value_selector)
                                    logging.info(f"    Próba użycia selektora wartości: {value_selector}")
                                    logging.info(f"    Znaleziono {len(value_elements)} elementów")
                                    
                                    for value_element in value_elements:
                                        if value_element:
                                            value = clean_text(value_element.text)
                                            logging.info(f"    Znaleziono wartość: {value}")
                                            
                                            if field == 'area':
                                                area_match = re.search(r'(\d+[.,]?\d*)\s*m[²2]', value)
                                                if area_match:
                                                    area_value = float(area_match.group(1).replace(',', '.'))
                                                    if area_value > 0:
                                                        details[field] = f"{area_value:.1f} m²"
                                                        logging.info(f"    ✓ Znaleziono powierzchnię: {details[field]}")
                                                        break
                                            elif field == 'rooms':
                                                rooms_match = re.search(r'(\d+)\s*(?:pok|pokoi|pokoje)?', value)
                                                if rooms_match:
                                                    rooms_value = int(rooms_match.group(1))
                                                    if 0 < rooms_value <= 10:
                                                        details[field] = str(rooms_value)
                                                        logging.info(f"    ✓ Znaleziono liczbę pokoi: {details[field]}")
                                                        break
                                            elif field == 'market':
                                                market_match = re.search(r'(wtórny|pierwotny)', value.lower())
                                                if market_match:
                                                    details[field] = market_match.group(1)
                                                    logging.info(f"    ✓ Znaleziono rynek: {details[field]}")
                                                    break
                                                elif "deweloper" in value.lower():
                                                    details[field] = "pierwotny"
                                                    logging.info(f"    ✓ Znaleziono rynek (deweloper): {details[field]}")
                                                    break
                                except Exception as e:
                                    logging.debug(f"    ⚠ Błąd przy próbie użycia selektora {value_selector}: {str(e)}")
                                    continue
                        
                        if field in details:
                            break
                except Exception as e:
                    logging.debug(f"  ⚠ Błąd przy próbie użycia selektora kontenera {container_selector}: {str(e)}")
                    continue
                
                if field in details:
                    break

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
            try:
                element = soup.select_one(selector)
                if element:
                    address = clean_text(element.get_text(strip=True))
                    logging.info(f"Znaleziono adres używając selektora: {selector}")
                    logging.info(f"Adres: {address}")
                    if address and not address.startswith('.css'):
                        break
            except Exception as e:
                logging.debug(f"Błąd przy próbie użycia selektora adresu {selector}: {str(e)}")
                continue
        
        # Ekstrakcja tytułu
        title = ""
        title_selectors = [
            "h1.css-1wnihf5",
            "[data-cy='adPageAdTitle']",
            "h1[data-cy='adPageAdTitle']",
            "div.css-1wnihf5 h1"
        ]
        
        for selector in title_selectors:
            try:
                element = soup.select_one(selector)
                if element:
                    title = clean_text(element.get_text(strip=True))
                    logging.info(f"Znaleziono tytuł używając selektora: {selector}")
                    logging.info(f"Tytuł: {title}")
                    break
            except Exception as e:
                logging.debug(f"Błąd przy próbie użycia selektora tytułu {selector}: {str(e)}")
                continue
        
        # Ekstrakcja ceny
        price = ""
        price_selectors = [
            "strong.css-8qi9av",
            "[data-cy='adPageHeaderPrice']",
            "strong[data-cy='adPageHeaderPrice']",
            "div.css-8qi9av",
            "strong.css-t80apw",
            "[data-testid='ad-price-value']",
            "div.css-1vr19r7",
            "div[data-testid='ad.price-value']"
        ]
        
        for selector in price_selectors:
            try:
                elements = soup.select(selector)
                for element in elements:
                    if element:
                        price_text = clean_text(element.get_text(strip=True))
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
        
        # Ekstrakcja ID ogłoszenia
        ad_id = ""
        ad_id_selectors = [
            "[data-cy='adPageAdId']",
            "p[data-sentry-element='DetailsProperty']",
            "[data-testid='ad-id']",
            "div.css-1k13n9p"
        ]
        
        for selector in ad_id_selectors:
            try:
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
            except Exception as e:
                logging.debug(f"Błąd przy próbie użycia selektora ID {selector}: {str(e)}")
                continue
        
        if not ad_id:
            ad_id = url.split('/')[-1].split('.')[0]
            logging.info(f"Wyciągnięto ID z URL: {ad_id}")
        
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
            logging.info(f"{key}: {value or 'Brak danych'}")
        
        return listing_data
        
    except Exception as e:
        logging.error(f"❌ Błąd podczas parsowania ogłoszenia {url}: {str(e)}")
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

def create_table_if_not_exists():
    if db_conn is None:
        logging.error('Brak połączenia z bazą danych!')
        return
    try:
        with db_conn.cursor() as cursor:
            create_table_sql = '''
            CREATE TABLE IF NOT EXISTS listings (
                id INT AUTO_INCREMENT PRIMARY KEY,
                ad_id VARCHAR(255) UNIQUE,
                title TEXT,
                price VARCHAR(255),
                address TEXT,
                area VARCHAR(255),
                rooms VARCHAR(255),
                market VARCHAR(255),
                url TEXT,
                date DATE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            '''
            cursor.execute(create_table_sql)
        db_conn.commit()
        logging.info('Tabela listings sprawdzona/utworzona.')
    except Exception as e:
        import traceback
        logging.error(f"Błąd przy tworzeniu tabeli: {str(e)}")
        logging.error(traceback.format_exc())

def save_to_db(listing_data: dict) -> bool:
    try:
        conn = pymysql.connect(
            host=DB_SERVERNAME,
            user=DB_USERNAME,
            password=DB_PASSWORD,
            database=DB_NAME,
            port=DB_PORT,
            charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor
        )
        with conn.cursor() as cursor:
            insert_sql = '''
            INSERT INTO listings (ad_id, title, price, address, area, rooms, market, url, date)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                title=VALUES(title),
                price=VALUES(price),
                address=VALUES(address),
                area=VALUES(area),
                rooms=VALUES(rooms),
                market=VALUES(market),
                url=VALUES(url),
                date=VALUES(date)
            '''
            logging.info(f"Próba zapisu rekordu: {listing_data}")
            cursor.execute(insert_sql, (
                listing_data.get('ad_id', ''),
                listing_data.get('title', ''),
                listing_data.get('price', ''),
                listing_data.get('address', ''),
                listing_data.get('area', ''),
                listing_data.get('rooms', ''),
                listing_data.get('market', ''),
                listing_data.get('url', ''),
                datetime.now().date()
            ))
            conn.commit()
            logging.info(f"Zapisano {listing_data.get('ad_id', '')} do bazy danych")
            return True
    except Exception as e:
        import traceback
        logging.error(f"Błąd zapisu do bazy danych: {str(e)}")
        logging.error(traceback.format_exc())
        return False
    finally:
        try:
            conn.close()
        except:
            pass

def process_listing(link):
    listing_data = parse_listing_details(link)
    if listing_data:
        zapis_db = save_to_db(listing_data)
        if zapis_db:
            logging.info(f"Zapisano {listing_data['ad_id']} do bazy danych")
        else:
            logging.error(f"Błąd zapisu {listing_data['ad_id']} do bazy danych")

def scrape_listings():
    try:
        page_number = 1
        total_listings = 0
        max_pages = 100  # Limit stron do przeanalizowania
        max_workers = 4
        
        while page_number <= max_pages:
            current_page_url = get_next_page_url(LISTINGS_URL, page_number)
            logging.info(f"Strona {page_number}: {current_page_url}")
            listing_links = get_listing_links(current_page_url)
            if not listing_links:
                logging.info(f"Brak ogłoszeń na stronie {page_number}. Kończę...")
                break
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = [executor.submit(process_listing, link) for link in listing_links]
                for future in as_completed(futures):
                    pass  # Możesz dodać obsługę wyjątków jeśli chcesz
            total_listings += len(listing_links)
            logging.info(f"Zakończono stronę {page_number}. Łącznie zapisano {total_listings} ogłoszeń.")
            page_number += 1
            time.sleep(random.uniform(0.1, 0.3))
    except Exception as e:
        logging.error(f"Błąd podczas scrapowania: {str(e)}")
        raise

def test_db_connection():
    if db_conn is None:
        logging.error('Brak połączenia z bazą danych!')
        return False
    try:
        with db_conn.cursor() as cursor:
            cursor.execute('SELECT 1')
            result = cursor.fetchone()
            if result:
                logging.info('Test połączenia z bazą danych zakończony sukcesem.')
                return True
            else:
                logging.error('Brak odpowiedzi z bazy danych.')
                return False
    except Exception as e:
        logging.error(f'Błąd podczas testowania połączenia z bazą danych: {str(e)}')
        return False

if __name__ == "__main__":
    try:
        logging.info("Rozpoczynanie scrapera...")
        if not DB_SERVERNAME or not DB_USERNAME or not DB_PASSWORD or not DB_NAME:
            logging.error("Błąd: Brak wymaganych zmiennych środowiskowych. Sprawdź plik .env")
            raise ValueError("Brak wymaganych zmiennych środowiskowych")
            
        create_table_if_not_exists()
        scrape_listings()
        logging.info("Scraping zakończony pomyślnie")
        test_db_connection()
    except Exception as e:
        logging.error(f"Krytyczny błąd podczas działania scrapera: {str(e)}")
        raise 