import os
import time
import random
from typing import Dict, Any, List, Optional
from bs4 import BeautifulSoup
import requests
from notion_client import Client
from dotenv import load_dotenv
from urllib.parse import urljoin, urlparse, parse_qs, urlencode
from datetime import datetime

# Załaduj zmienne środowiskowe
print("Ładowanie zmiennych środowiskowych...")
load_dotenv()

# Konfiguracja
NOTION_API_KEY = os.getenv('NOTION_API_KEY')
NOTION_DATABASE_ID = os.getenv('NOTION_DATABASE_ID')
BASE_URL = "https://www.otodom.pl"
LISTINGS_URL = "https://www.otodom.pl/pl/wyniki/sprzedaz/mieszkanie/cala-polska"

# Sprawdź konfigurację
print(f"Sprawdzanie konfiguracji:")
print(f"NOTION_API_KEY {'jest ustawiony' if NOTION_API_KEY else 'NIE jest ustawiony'}")
print(f"NOTION_DATABASE_ID {'jest ustawiony' if NOTION_DATABASE_ID else 'NIE jest ustawiony'}")

if not NOTION_API_KEY or not NOTION_DATABASE_ID:
    raise ValueError("Brak wymaganych zmiennych środowiskowych. Sprawdź plik .env")

# Inicjalizacja klienta Notion
try:
    print("Inicjalizacja klienta Notion...")
    notion = Client(auth=NOTION_API_KEY)
    # Sprawdź połączenie z bazą danych
    notion.databases.retrieve(database_id=NOTION_DATABASE_ID)
    print("Połączenie z bazą Notion zostało ustanowione pomyślnie")
except Exception as e:
    print(f"Błąd podczas inicjalizacji klienta Notion: {str(e)}")
    raise

def get_current_date() -> str:
    """Zwraca aktualną datę w formacie ISO"""
    return datetime.now().date().isoformat()

def get_existing_ad_ids() -> set:
    """Pobiera listę istniejących ID ogłoszeń z bazy Notion"""
    try:
        print("Pobieranie istniejących ID z bazy Notion...")
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
        
        print(f"Pobrano {len(results)} istniejących ID z bazy")
        return set(results)
    except Exception as e:
        print(f"Błąd podczas pobierania istniejących ID: {str(e)}")
        raise

def is_valid_price(price: str) -> bool:
    """Sprawdza czy cena jest poprawna"""
    return bool(price and price.strip() and "zł" in price)

def get_headers() -> Dict[str, str]:
    """Zwraca nagłówki dla requestów"""
    return {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "pl-PL,pl;q=0.9,en-US;q=0.8,en;q=0.7",
    }

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
    element = soup.select_one(selector)
    if element:
        if attribute:
            return element.get(attribute, "").strip()
        return element.get_text().strip()
    return ""

def parse_listing_details(url: str) -> Optional[Dict[str, Any]]:
    """Parsuje szczegóły ogłoszenia"""
    try:
        response = requests.get(url, headers=get_headers())
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Ekstrakcja ID ogłoszenia najpierw
        ad_id = extract_text_from_element(soup, "p[data-sentry-element='DetailsProperty']")
        ad_id = ad_id.split(":")[-1].strip() if ad_id else ""
        
        # Sprawdź czy ID istnieje w cache
        if ad_id in existing_ad_ids:
            print(f"Ogłoszenie {ad_id} już istnieje w bazie. Pomijam.")
            return None
            
        # Ekstrakcja ceny
        price = extract_text_from_element(soup, "strong[data-cy='adPageHeaderPrice']")
        if not is_valid_price(price):
            print(f"Nieprawidłowa cena dla ogłoszenia {ad_id}. Pomijam.")
            return None
        
        # Ekstrakcja pozostałych danych
        title = extract_text_from_element(soup, "h1[data-cy='adPageAdTitle']")
        address = extract_text_from_element(soup, "a[href='#map']")
        
        # Ekstrakcja powierzchni, liczby pokoi i rynku
        area = ""
        rooms = ""
        market = ""
        
        details = soup.select("div[data-sentry-element='ItemGridContainer']")
        for detail in details:
            label = detail.select_one("p[data-sentry-element='Item']")
            value = detail.select_one("p.esen0m92:last-child")
            
            if label and value:
                label_text = label.get_text().strip()
                value_text = value.get_text().strip()
                
                if "Powierzchnia" in label_text:
                    area = value_text
                elif "Liczba pokoi" in label_text:
                    rooms = value_text
                elif "Rynek" in label_text:
                    market = value_text
        
        return {
            "title": title,
            "price": price,
            "address": address,
            "area": area,
            "rooms": rooms,
            "market": market,
            "ad_id": ad_id,
            "url": url
        }
    except Exception as e:
        print(f"Błąd podczas parsowania ogłoszenia {url}: {str(e)}")
        return None

def save_to_notion(listing_data: Dict[str, Any]) -> None:
    """Zapisuje dane ogłoszenia do bazy Notion"""
    try:
        print(f"\nPróba zapisania ogłoszenia {listing_data['ad_id']} do Notion...")
        print(f"Dane do zapisu: {listing_data}")
        
        notion.pages.create(
            parent={"database_id": NOTION_DATABASE_ID},
            properties={
                "Title": {"title": [{"text": {"content": listing_data["title"]}}]},
                "Price": {"rich_text": [{"text": {"content": listing_data["price"]}}]},
                "Address": {"rich_text": [{"text": {"content": listing_data["address"]}}]},
                "Area": {"rich_text": [{"text": {"content": listing_data["area"]}}]},
                "Rooms": {"rich_text": [{"text": {"content": listing_data["rooms"]}}]},
                "Market": {"rich_text": [{"text": {"content": listing_data["market"]}}]},
                "Ad ID": {"rich_text": [{"text": {"content": listing_data["ad_id"]}}]},
                "URL": {"url": listing_data["url"]},
                "Date": {"date": {"start": get_current_date()}}
            }
        )
        print(f"Pomyślnie zapisano ogłoszenie {listing_data['ad_id']} do Notion")
    except Exception as e:
        print(f"Błąd podczas zapisywania do Notion: {str(e)}")
        print(f"Szczegóły błędu: {e.__class__.__name__}")
        raise

def get_listing_links(page_url: str) -> List[str]:
    """Pobiera linki do ogłoszeń z danej strony"""
    try:
        response = requests.get(page_url, headers=get_headers())
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        links = []
        listing_cards = soup.select("a[data-cy='listing-item-link']")
        
        for card in listing_cards:
            href = card.get('href')
            if href:
                full_url = urljoin(BASE_URL, href)
                links.append(full_url)
        
        return links
    except Exception as e:
        print(f"Błąd podczas pobierania linków ze strony {page_url}: {str(e)}")
        return []

def scrape_listings():
    """Główna funkcja scrapująca"""
    global existing_ad_ids
    existing_ad_ids = get_existing_ad_ids()
    print(f"Znaleziono {len(existing_ad_ids)} istniejących ogłoszeń w bazie")
    
    page_number = 1
    total_listings = 0
    
    while True:
        current_page_url = get_next_page_url(LISTINGS_URL, page_number)
        print(f"\nPrzetwarzanie strony {page_number}: {current_page_url}")
        
        listing_links = get_listing_links(current_page_url)
        
        if not listing_links:
            print(f"Nie znaleziono więcej ogłoszeń na stronie {page_number}. Kończenie...")
            break
            
        for link in listing_links:
            print(f"\nPrzetwarzanie ogłoszenia: {link}")
            listing_data = parse_listing_details(link)
            
            if listing_data:
                save_to_notion(listing_data)
                total_listings += 1
            
            # Dodaj losowe opóźnienie między requestami
            time.sleep(random.uniform(2, 5))
        
        print(f"\nZakończono stronę {page_number}. Zapisano {total_listings} ogłoszeń.")
        page_number += 1
        
        # Dodaj opóźnienie między stronami
        time.sleep(random.uniform(3, 7))

if __name__ == "__main__":
    scrape_listings() 