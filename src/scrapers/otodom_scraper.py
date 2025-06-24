#!/usr/bin/env python3
"""
SCRAPER OTODOM.PL
Scraper dla portalu Otodom.pl z pełną obsługą Selenium
Zaktualizowany do nowej struktury bazy danych
"""
import logging
import sys
import os
import re
from typing import List, Dict, Optional, Callable
import json
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import time
import random

# Dodaj główny katalog do ścieżki
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from utils import get_soup, random_delay, clean_text, extract_price

# Import geocodingu 
try:
    from src.geocoding.geocoder import geocode_address_improved, build_simple_search_query
    GEOCODING_AVAILABLE = True
except ImportError as e:
    logger.warning(f"⚠️ Geocoding niedostępny: {e}")
    GEOCODING_AVAILABLE = False

# Konfiguracja logowania z obsługą wielowątkowości
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s - [%(threadName)s] - %(message)s'
)
logger = logging.getLogger(__name__)

# Thread-safe licznik dla postępu
_progress_lock = threading.Lock()
_progress_counter = {"current": 0, "total": 0}

DEFAULT_BASE_URL = "https://www.otodom.pl/pl/wyniki/sprzedaz/mieszkanie/cala-polska"

def scrape_listing_details_thread_safe(listing_data: Dict, enable_geocoding: bool = False) -> Dict:
    """
    Thread-safe wrapper dla scrapowania szczegółów pojedynczego ogłoszenia
    
    Args:
        listing_data: Podstawowe dane ogłoszenia z URL
        enable_geocoding: Czy pobierać współrzędne geograficzne
    
    Returns:
        Dict: Ogłoszenie z pobranymi szczegółami
    """
    try:
        # Dodaj random delay żeby nie przeciążać serwera
        time.sleep(random.uniform(0.5, 2.0))
        
        url = listing_data.get("url")
        if not url:
            return listing_data
            
        # Pobierz szczegóły
        detailed_data = scrape_individual_listing(url)
        
        # Połącz z podstawowymi danymi
        if detailed_data:
            listing_data.update(detailed_data)
        
        # GEOCODING: Pobierz współrzędne jeśli włączone
        if enable_geocoding and GEOCODING_AVAILABLE:
            try:
                # Zbuduj zapytanie geocodingu z dostępnych danych
                address_data = {
                    'city': listing_data.get('city'),
                    'district': listing_data.get('district'), 
                    'street_name': listing_data.get('street'),
                    'address_raw': listing_data.get('address_raw')
                }
                
                geocoding_query = build_simple_search_query(address_data)
                
                if geocoding_query and geocoding_query != "Polska":
                    coordinates = geocode_address_improved(geocoding_query)
                    if coordinates:
                        latitude, longitude = coordinates
                        listing_data['latitude'] = latitude
                        listing_data['longitude'] = longitude
                        logger.debug(f"✅ Geocoding: {latitude:.6f}, {longitude:.6f}")
                    else:
                        logger.debug(f"⚠️ Brak współrzędnych dla: {geocoding_query}")
                        
                # Dodaj opóźnienie dla geocodingu
                time.sleep(1.0)
                        
            except Exception as e:
                logger.error(f"❌ Błąd geocodingu: {e}")
            
        # Thread-safe update licznika postępu
        with _progress_lock:
            _progress_counter["current"] += 1
            current = _progress_counter["current"]
            total = _progress_counter["total"]
            if current % 5 == 0 or current == total:  # Log co 5 ogłoszeń lub na końcu
                logger.info(f"🔍 Postęp szczegółów: {current}/{total} ({current/total*100:.1f}%)")
        
        return listing_data
        
    except Exception as e:
        logger.error(f"❌ Błąd w wątku dla {listing_data.get('url', 'unknown')}: {e}")
        return listing_data

def extract_numeric_value(text: str) -> float:
    """Wydobywa wartość numeryczną z tekstu"""
    if not text:
        return None
    
    # Znajdź pierwszą liczbę w tekście
    match = re.search(r'(\d+(?:[,.])\d+|\d+)', text.replace(' ', ''))
    if match:
        value_str = match.group(1).replace(',', '.')
        try:
            return float(value_str)
        except ValueError:
            pass
    return None

def extract_boolean_features(text: str) -> Dict[str, bool]:
    """Wydobywa cechy boolean z tekstu (balkon, garaż, ogród, winda)"""
    text_lower = text.lower()
    
    return {
        "has_balcony": any(word in text_lower for word in ['balkon', 'taras', 'loggia']),
        "has_garage": any(word in text_lower for word in ['garaż', 'parking', 'miejsce parkingowe']),
        "has_garden": any(word in text_lower for word in ['ogród', 'ogródek', 'działka']),
        "has_elevator": any(word in text_lower for word in ['winda', 'elevator', 'ascensor'])
    }

def determine_market_type(text: str, url: str) -> str:
    """Określa typ rynku (pierwotny/wtórny) na podstawie tekstu i URL"""
    text_lower = text.lower()
    url_lower = url.lower()
    
    # Słowa kluczowe dla rynku pierwotnego
    primary_keywords = [
        'nowe', 'nowy', 'deweloper', 'inwestycja', 'przedsprzedaż', 
        'nowa inwestycja', 'od developera', 'stan deweloperski',
        'pierwszy właściciel', 'pierwotny'
    ]
    
    # Słowa kluczowe dla rynku wtórnego
    secondary_keywords = [
        'wtórny', 'używane', 'do remontu', 'po remoncie',
        'mieszkanie własnościowe', 'z drugiej ręki'
    ]
    
    # Sprawdź rynek pierwotny
    if any(keyword in text_lower for keyword in primary_keywords):
        return 'pierwotny'
    
    # Sprawdź rynek wtórny
    if any(keyword in text_lower for keyword in secondary_keywords):
        return 'wtórny'
    
    # Domyślnie przyjmij rynek wtórny (częściej występuje)
    return 'wtórny'

def get_otodom_listings(base_url: str = DEFAULT_BASE_URL,
                        max_pages: Optional[int] = 0,
                        scrape_details: bool = True,
                        batch_size: int = 100,
                        batch_callback: Optional[Callable[[List[Dict]], None]] = None,
                        resume: bool = False,
                        max_workers: int = 4,
                        enable_geocoding: bool = True) -> List[Dict]:
    """
    Pobiera ogłoszenia z Otodom.pl z opcjonalnym scrapingiem szczegółów
    
    Args:
        base_url: Podstawowy URL do strony wyników
        max_pages: (opcjonalnie) maksymalna liczba stron do przeskanowania. 
                   Jeśli None lub <=0, scraper będzie przechodził kolejne strony 
                   aż do wykrycia ostatniej (brak ogłoszeń lub brak przycisku "Następna strona").
        scrape_details: Czy wchodzić w szczegóły każdego ogłoszenia
        batch_size: Rozmiar batcha do zapisu do bazy
        batch_callback: Funkcja do zapisu batcha do bazy
        resume: Czy kontynuować od ostatniego punktu zapisu (domyślnie wyłączone)
        max_workers: Liczba wątków do wielowątkowego scrapowania szczegółów (domyślnie 4)
        enable_geocoding: Czy pobierać współrzędne geograficzne podczas scrapowania (domyślnie False)
    
    Returns:
        List[Dict]: Lista ogłoszeń
    """
    listings = []
    
    # Plik z checkpointami (np. ~/.otodom_progress.json)
    progress_file = Path.home() / ".otodom_progress.json"
    if resume and progress_file.exists():
        try:
            progress_data = json.loads(progress_file.read_text(encoding="utf-8"))
        except Exception:
            progress_data = {}
    else:
        progress_data = {}

    progress_key = base_url
    start_page = int(progress_data.get(progress_key, 1))

    page = start_page
    while True:
        # Sprawdź limit jeśli podano dodatnią liczbę stron
        if max_pages is not None and max_pages > 0 and page > max_pages:
            logger.info("🏁 Osiągnięto maksymalną liczbę stron określoną przez użytkownika")
            break
        
        try:
            # Konstruuj URL z parametrami
            if page == 1:
                url = f"{base_url}?viewType=listing"
            else:
                url = f"{base_url}?viewType=listing&page={page}"
                
            logger.info(f"🏠 Scrapuję Otodom.pl - strona {page}")
            logger.info(f"🔗 URL: {url}")
            
            # Używamy Selenium dla Otodom
            soup = get_soup(url, use_selenium=True)
            
            # Selektory dla kontenerów ogłoszeń
            offers = (soup.select("[data-cy='listing-item']") or 
                     soup.select("article.css-136g1q2") or 
                     soup.select("article") or
                     soup.select(".listing-item"))
            
            # POPRAWIONA LOGIKA WYKRYWANIA KOŃCA STRON
            if not offers:
                logger.warning(f"⚠️ Nie znaleziono ogłoszeń na stronie {page}")
                
                # Sprawdź czy strona załadowała się prawidłowo
                if "otodom" not in soup.get_text().lower():
                    logger.error("❌ Strona nie załadowała się prawidłowo - próbuję ponownie")
                    # Dodaj krótkie opóźnienie i spróbuj ponownie
                    time.sleep(5)
                    continue
                
                # Sprawdź czy jest informacja o końcu wyników
                page_text = soup.get_text().lower()
                end_indicators = [
                    "brak wyników",
                    "nie znaleziono", 
                    "koniec wyników",
                    "strona nie istnieje",
                    "404",
                    "błąd"
                ]
                
                if any(indicator in page_text for indicator in end_indicators):
                    logger.info(f"🏁 Wykryto koniec wyników na stronie {page}")
                    break
                
                # Sprawdź czy istnieją przyciski nawigacji
                pagination_elements = soup.select("nav, .pagination, [data-cy*='pagination'], a[title*='następna'], a[title*='dalej']")
                
                if not pagination_elements:
                    logger.info(f"🏁 Brak elementów paginacji na stronie {page} - koniec")
                    break
                
                # Jeśli nie ma wyraźnych wskaźników końca, spróbuj jeszcze kilka stron
                if page <= 5:  # Dla pierwszych 5 stron - może być przejściowy błąd
                    logger.warning(f"⚠️ Strona {page} pusta, ale kontynuuję (może być przejściowy błąd)")
                    page += 1
                    continue
                else:
                    logger.info(f"🏁 Brak ogłoszeń na stronie {page} - prawdopodobnie koniec wyników")
                    break
            
            logger.info(f"📋 Znaleziono {len(offers)} ogłoszeń na stronie {page}")
            
            # Dodaj sprawdzenie czy liczba ogłoszeń znacznie spadła
            if page > 3 and len(offers) < 10:  # Jeśli po 3 stronie mniej niż 10 ogłoszeń
                logger.warning(f"⚠️ Znaczny spadek liczby ogłoszeń na stronie {page} ({len(offers)})")
                
                # Sprawdź czy to rzeczywiście koniec
                total_items_text = soup.get_text()
                if "wynik" in total_items_text.lower():
                    # Spróbuj wyciągnąć informację o łącznej liczbie wyników
                    import re
                    matches = re.findall(r'(\d+)\s*wynik', total_items_text.lower())
                    if matches:
                        total_results = int(matches[0])
                        expected_pages = (total_results // 24) + 1
                        logger.info(f"📊 Znaleziono informację o {total_results} wynikach, oczekiwane strony: {expected_pages}")
                        
                        if page > expected_pages:
                            logger.info(f"🏁 Przekroczono oczekiwaną liczbę stron ({page} > {expected_pages})")
                            break
            
            # KROK 1: Sparsuj wszystkie podstawowe dane z tej strony
            page_listings = []
            for i, offer in enumerate(offers):
                try:
                    listing = parse_otodom_listing(offer)
                    if listing:
                        listing["source"] = "otodom.pl"
                        listing["source_page"] = page
                        listing["source_position"] = i + 1
                        page_listings.append(listing)
                        logger.debug(f"✅ Parsowano podstawowe dane {i+1}: {listing.get('title_raw', '')[:30]}...")
                except Exception as e:
                    logger.error(f"❌ Błąd parsowania podstawowych danych ogłoszenia {i+1}: {e}")
            
            # KROK 2: Jeśli scrape_details=True, pobierz szczegóły WIELOWĄTKOWO
            if scrape_details and page_listings:
                geocoding_status = "z geocodingiem ✅" if enable_geocoding and GEOCODING_AVAILABLE else "bez geocodingu ⚠️"
                logger.info(f"🚀 Rozpoczynam wielowątkowe pobieranie szczegółów dla {len(page_listings)} ogłoszeń ({max_workers} wątków, {geocoding_status})")
                
                # Ustaw licznik postępu
                with _progress_lock:
                    _progress_counter["current"] = 0
                    _progress_counter["total"] = len(page_listings)
                
                # Użyj ThreadPoolExecutor z konfigurowalną liczbą wątków
                with ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="OtodomScraper") as executor:
                    # Wyślij wszystkie zadania
                    future_to_listing = {
                        executor.submit(scrape_listing_details_thread_safe, listing.copy(), enable_geocoding): listing 
                        for listing in page_listings
                    }
                    
                    # Zbierz wyniki w miarę ich gotowości
                    completed_listings = []
                    for future in as_completed(future_to_listing):
                        try:
                            completed_listing = future.result(timeout=60)  # 60s timeout per listing
                            completed_listings.append(completed_listing)
                        except Exception as e:
                            original_listing = future_to_listing[future]
                            logger.error(f"❌ Błąd w wątku dla {original_listing.get('url', 'unknown')}: {e}")
                            # Dodaj podstawowe dane bez szczegółów
                            completed_listings.append(original_listing)
                
                # Zastąp podstawowe listingi uzupełnionymi
                page_listings = completed_listings
                logger.info(f"✅ Zakończono wielowątkowe pobieranie szczegółów dla strony {page}")
            
            # KROK 3: Dodaj do głównej listy i obsłuż batche
            for listing in page_listings:
                listings.append(listing)
                
                # Batch zapisu
                if batch_size and len(listings) >= batch_size and batch_callback:
                    logger.info("💾 Osiągnięto wielkość batcha – zapisuję do bazy…")
                    try:
                        batch_callback(listings)
                    finally:
                        listings.clear()
            
            random_delay()
            
            # Jeśli nie znaleziono żadnych ofert na kolejnej stronie, zakończ pętlę
            # (sprawdzenie będzie wykonane na początku kolejnej iteracji)

        except Exception as e:
            logger.error(f"❌ Błąd pobierania strony {page}: {e}")
            
            # LEPSZA OBSŁUGA BŁĘDÓW
            error_msg = str(e).lower()
            
            # Sprawdź czy to błąd tymczasowy
            temporary_errors = [
                "timeout", "connection", "network", "ssl", "http",
                "502", "503", "504", "connection reset", "connection refused"
            ]
            
            if any(temp_error in error_msg for temp_error in temporary_errors):
                logger.warning(f"⚠️ Błąd tymczasowy na stronie {page}, czekam 10 sekund i próbuję ponownie...")
                time.sleep(10)
                continue
            
            # Sprawdź czy to błąd blokady (anti-bot)
            blocking_errors = [
                "403", "forbidden", "blocked", "bot", "robot", "captcha"
            ]
            
            if any(block_error in error_msg for block_error in blocking_errors):
                logger.error(f"🚫 Prawdopodobna blokada anti-bot na stronie {page}")
                logger.info("💡 Sugestia: Zwiększ opóźnienia między żądaniami lub użyj proxy")
                break
            
            # Dla innych błędów - przejdź do następnej strony ale nie przerywaj całkowicie
            logger.warning(f"⚠️ Pomijam stronę {page} z powodu błędu: {e}")
            
            # Jeśli jest zbyt wiele błędów pod rząd, przerwij
            if not hasattr(get_otodom_listings, 'consecutive_errors'):
                consecutive_errors = 0
            else:
                consecutive_errors = getattr(get_otodom_listings, 'consecutive_errors', 0)
                
            consecutive_errors += 1
            setattr(get_otodom_listings, 'consecutive_errors', consecutive_errors)
            
            if consecutive_errors >= 3:
                logger.error(f"❌ Zbyt wiele błędów pod rząd ({consecutive_errors}), przerywam")
                break
                
            # Opóźnienie po błędzie
            time.sleep(5)
            
        # Zapisz progres
        if resume:
            progress_data[progress_key] = page
            try:
                progress_file.write_text(json.dumps(progress_data, ensure_ascii=False), encoding="utf-8")
            except Exception as e:
                logger.warning(f"⚠️ Nie udało się zapisać checkpointu: {e}")

        page += 1

    # Resetuj checkpoint po zakończeniu
    if resume and progress_key in progress_data:
        progress_data.pop(progress_key, None)
        try:
            progress_file.write_text(json.dumps(progress_data, ensure_ascii=False), encoding="utf-8")
        except Exception:
            pass

    logger.info(f"✅ Pobrano ŁĄCZNIE {len(listings)} ogłoszeń z Otodom.pl")
    return listings

def parse_otodom_listing(offer_element) -> Dict:
    """
    Parsuje pojedyncze ogłoszenie z Otodom.pl zgodnie z nową strukturą bazy
    
    Args:
        offer_element: Element BeautifulSoup z ogłoszeniem
    
    Returns:
        Dict: Dane ogłoszenia zgodne z nową strukturą bazy
    """
    # TYTUŁ (title_raw)
    title_elem = (offer_element.select_one("[data-cy='listing-item-title']") or
                  offer_element.select_one("p.css-u3orbr") or
                  offer_element.select_one("h3") or
                  offer_element.select_one("h2"))
    title_raw = clean_text(title_elem.get_text()) if title_elem else ""
    
    # CENA
    price_elem = (offer_element.select_one("span.css-2bt9f1") or
                  offer_element.select_one("[data-sentry-element='Content']") or
                  offer_element.select_one("[data-cy*='price']"))
    price_text = clean_text(price_elem.get_text()) if price_elem else ""
    price_data = extract_price(price_text)
    
    # LOKALIZACJA (address_raw)
    location_elem = (offer_element.select_one("p.css-42r2ms") or
                     offer_element.select_one("[data-sentry-element='StyledParagraph']") or
                     offer_element.select_one("[data-cy='listing-item-location']"))
    address_raw = clean_text(location_elem.get_text()) if location_elem else ""
    
    # LINK (URL)
    link_elem = (offer_element.select_one("[data-cy='listing-item-link']") or
                 offer_element.select_one("a[href*='/oferta/']") or
                 offer_element.select_one("a"))
    url = link_elem.get("href") if link_elem else ""
    if url and not url.startswith("http"):
        url = f"https://www.otodom.pl{url}"
    
    # POWIERZCHNIA I POKOJE z <dl> struktury
    area_value = None
    rooms_value = None
    
    specs_list = offer_element.select_one("dl.css-9q2yy4")
    if specs_list:
        dt_elements = specs_list.select("dt")
        dd_elements = specs_list.select("dd")
        
        for i, dt in enumerate(dt_elements):
            dt_text = clean_text(dt.get_text())
            if i < len(dd_elements):
                dd_text = clean_text(dd_elements[i].get_text())
                
                if "powierzchnia" in dt_text.lower():
                    area_value = extract_numeric_value(dd_text)
                elif "pokoi" in dt_text.lower() or "pokój" in dt_text.lower():
                    rooms_value = extract_numeric_value(dd_text)
    
    # Fallback dla powierzchni
    if not area_value:
        area_elem = offer_element.select_one("span:contains('m²')")
        if area_elem:
            area_value = extract_numeric_value(area_elem.get_text())
    
    # DODATKOWE SZCZEGÓŁY z sekcji AdDetails
    additional_details = extract_detailed_features(offer_element)
    
    # Sprawdź czy mamy podstawowe dane
    if not title_raw and not url:
        return None
    
    # Kombinowany tekst do analizy cech
    combined_text = f"{title_raw} {address_raw}".lower()
    
    # Wydobyj cechy boolean
    boolean_features = extract_boolean_features(combined_text)
    
    # Połącz z dodatkowymi cechami ze szczegółów
    boolean_features.update(additional_details['boolean_features'])
    
    # Określ typ rynku
    market_type = determine_market_type(combined_text, url)
    if additional_details.get('market'):
        market_type = additional_details['market']
    
    # Parsowanie zaawansowanych komponentów adresu
    address_components = parse_address_components(address_raw)
    
    # Wyciągnij komponenty
    street = address_components.get("street")
    district = address_components.get("district") 
    city = address_components.get("city")
    province = address_components.get("province")
    
    # Struktura danych zgodna z nową bazą danych
    listing = {
        # Podstawowe informacje
        "url": url,
        "listing_id": None,  # Będzie uzupełnione ze szczegółów
        "title_raw": title_raw,
        "address_raw": address_raw,
        
        # Cena i powierzchnia
        "price": price_data["price"],
        "area": area_value,
        "rooms": int(rooms_value) if rooms_value and rooms_value > 0 else None,
        
        # Lokalizacja (sparsowane komponenty)
        "city": city,
        "district": district,
        "street": street,
        "province": province,
        
        # Typ rynku
        "market": market_type,
        
        # Cechy boolean - podstawowe + szczegółowe
        "has_balcony": boolean_features.get("has_balcony", False),
        "has_garage": boolean_features.get("has_garage", False), 
        "has_garden": boolean_features.get("has_garden", False),
        "has_elevator": boolean_features.get("has_elevator", False),
        
        # Dodatkowe szczegóły budynku
        "year_of_construction": additional_details.get("year_of_construction"),
        "building_type": additional_details.get("building_type"),
        "floor": additional_details.get("floor"),
        "total_floors": additional_details.get("total_floors"),
        "standard_of_finish": additional_details.get("standard_of_finish"),
        
        # Pola które wymagają dodatkowych danych (na razie None)
        "listing_date": None,
        "latitude": None,
        "longitude": None,
        "distance_to_city_center": None,
        "distance_to_nearest_school": None,
        "distance_to_nearest_kindergarten": None,
        "distance_to_nearest_public_transport": None,
        "distance_to_nearest_supermarket": None,
        
        # Metadane
        "source": "otodom.pl"
    }
    
    return listing

def extract_detailed_features(offer_element) -> Dict:
    """
    Ekstraktuje szczegółowe cechy z sekcji AdDetails
    Na podstawie struktury: div[data-sentry-component="AdDetailsBase"]
    
    Args:
        offer_element: Element BeautifulSoup z ogłoszeniem
    
    Returns:
        Dict z dodatkowymi cechami
    """
    result = {
        'boolean_features': {
            'has_balcony': False,
            'has_garage': False,
            'has_garden': False,
            'has_elevator': False,
            'has_basement': False,
            'has_separate_kitchen': False
        },
        'market': None,
        'year_of_construction': None,
        'building_type': None,
        'floor': None,
        'total_floors': None,
        'standard_of_finish': None,
        'heating_type': None,
        'rent_amount': None
    }
    
    # Szukaj sekcji szczegółów
    details_container = offer_element.select_one('[data-sentry-component="AdDetailsBase"]')
    if not details_container:
        return result
    
    # Wszystkie pary klucz-wartość z sekcji szczegółów
    item_containers = details_container.select('[data-sentry-source-file="AdDetailItem.tsx"].css-1xw0jqp')
    
    for container in item_containers:
        # Znajdź etykietę i wartość
        label_elem = container.select_one('p.esen0m92.css-1airkmu:first-child')
        value_elem = container.select_one('p.esen0m92.css-1airkmu:nth-child(2), p.esen0m92.css-wcoypf')
        
        if not label_elem or not value_elem:
            continue
            
        label = clean_text(label_elem.get_text()).lower()
        value = clean_text(value_elem.get_text()).lower()
        
        # Mapowanie pól
        if 'powierzchnia' in label:
            # Już obsługiwane w głównej funkcji
            pass
        elif 'liczba pokoi' in label:
            # Już obsługiwane w głównej funkcji
            pass
        elif 'piętro' in label:
            # Format: "3/4" -> floor=3, total_floors=4
            if '/' in value:
                parts = value.split('/')
                try:
                    result['floor'] = int(parts[0].strip())
                    result['total_floors'] = int(parts[1].strip())
                except (ValueError, IndexError):
                    pass
        elif 'rok budowy' in label:
            try:
                year = int(value.strip())
                if 1800 <= year <= 2030:  # Walidacja rozsądnych lat
                    result['year_of_construction'] = year
            except ValueError:
                pass
        elif 'winda' in label:
            result['boolean_features']['has_elevator'] = 'tak' in value or 'yes' in value
        elif 'rodzaj zabudowy' in label:
            # blok, kamienica, dom wolnostojący, itp.
            result['building_type'] = value
        elif 'stan wykończenia' in label:
            result['standard_of_finish'] = value
        elif 'ogrzewanie' in label:
            result['heating_type'] = value
        elif 'czynsz' in label:
            # Wyciągnij kwotę czynszu
            rent_value = extract_numeric_value(value)
            if rent_value and rent_value > 0:
                result['rent_amount'] = rent_value
        elif 'rynek' in label:
            if 'pierwotny' in value:
                result['market'] = 'pierwotny'
            elif 'wtórny' in value:
                result['market'] = 'wtórny'
    
    # Szukaj cech boolean w sekcji "Informacje dodatkowe"
    additional_info_containers = details_container.select('span.css-axw7ok.esen0m94')
    for span in additional_info_containers:
        feature_text = clean_text(span.get_text()).lower()
        
        if 'balkon' in feature_text:
            result['boolean_features']['has_balcony'] = True
        elif 'garaż' in feature_text or 'parking' in feature_text:
            result['boolean_features']['has_garage'] = True
        elif 'ogród' in feature_text or 'działka' in feature_text:
            result['boolean_features']['has_garden'] = True
        elif 'piwnica' in feature_text:
            result['boolean_features']['has_basement'] = True
        elif 'oddzielna kuchnia' in feature_text:
            result['boolean_features']['has_separate_kitchen'] = True
        elif 'winda' in feature_text:
            result['boolean_features']['has_elevator'] = True
    
    return result

def scrape_individual_listing(url: str) -> Dict:
    """
    Scrapuje szczegółowe dane z indywidualnej strony ogłoszenia
    
    Args:
        url: URL do strony ogłoszenia
    
    Returns:
        Dict: Szczegółowe dane z ogłoszenia
    """
    try:
        # Pobierz stronę ogłoszenia
        soup = get_soup(url, use_selenium=True)
        
        if not soup:
            logger.error(f"❌ Nie udało się załadować strony: {url}")
            return {}
        
        # Dodaj krótkie opóźnienie między requestami
        random_delay()
        
        # Struktura wynikowa
        detailed_data = {
            "year_of_construction": None,
            "building_type": None,
            "floor": None,
            "total_floors": None,
            "standard_of_finish": None,
            "heating_type": None,
            "rent_amount": None,
            "has_balcony": False,
            "has_garage": False,
            "has_garden": False,
            "has_elevator": False,
            "has_basement": False,
            "has_separate_kitchen": False,
            "has_dishwasher": False,
            "has_fridge": False,
            "has_oven": False,
            "security_features": [],
            "media_features": []
        }
        
        # Znajdź sekcję AdDetails
        details_container = soup.select_one('[data-sentry-component="AdDetailsBase"]')
        if not details_container:
            # Fallback - szukaj innych kontenerów ze szczegółami
            details_container = soup.select_one('.css-8mnxk5') or soup
        
        # Parsuj szczegóły z par klucz-wartość
        item_containers = details_container.select('[data-sentry-source-file="AdDetailItem.tsx"].css-1xw0jqp')
        
        for container in item_containers:
            # Znajdź etykietę i wartość
            label_elem = container.select_one('p.esen0m92.css-1airkmu:first-child')
            value_elem = container.select_one('p.esen0m92.css-1airkmu:nth-child(2), p.esen0m92.css-wcoypf')
            
            if not label_elem or not value_elem:
                continue
                
            label = clean_text(label_elem.get_text()).lower()
            value = clean_text(value_elem.get_text()).lower()
            
            # Mapowanie pól szczegółowych
            if 'piętro' in label:
                # Format: "3/4" -> floor=3, total_floors=4
                if '/' in value:
                    parts = value.split('/')
                    try:
                        detailed_data['floor'] = int(parts[0].strip())
                        detailed_data['total_floors'] = int(parts[1].strip())
                    except (ValueError, IndexError):
                        pass
            elif 'rok budowy' in label:
                try:
                    year = int(value.strip())
                    if 1800 <= year <= 2030:  # Walidacja rozsądnych lat
                        detailed_data['year_of_construction'] = year
                except ValueError:
                    pass
            elif 'winda' in label:
                detailed_data['has_elevator'] = 'tak' in value or 'yes' in value
            elif 'rodzaj zabudowy' in label:
                # Mapuj na enum wartości z bazy
                building_mapping = {
                    'blok': 'blok',
                    'kamienica': 'kamienica', 
                    'apartamentowiec': 'apartamentowiec',
                    'dom wielorodzinny': 'dom wielorodzinny',
                    'wielka płyta': 'wielka płyta'
                }
                for key, mapped_value in building_mapping.items():
                    if key in value:
                        detailed_data['building_type'] = mapped_value
                        break
                if not detailed_data['building_type']:
                    detailed_data['building_type'] = 'inny'
            elif 'stan wykończenia' in label:
                # Mapuj na liczby (standard_of_finish to tinyint)
                finish_mapping = {
                    'do zamieszkania': 1,
                    'gotowe do zamieszkania': 1,
                    'developerski': 2,
                    'deweloperski': 2,
                    'do wykończenia': 3,
                    'do remontu': 4,
                    'surowy otwarty': 5,
                    'surowy zamknięty': 6
                }
                for key, mapped_value in finish_mapping.items():
                    if key in value:
                        detailed_data['standard_of_finish'] = mapped_value
                        break
            elif 'ogrzewanie' in label:
                detailed_data['heating_type'] = value
            elif 'czynsz' in label:
                # Wyciągnij kwotę czynszu
                rent_value = extract_numeric_value(value)
                if rent_value and rent_value > 0:
                    detailed_data['rent_amount'] = rent_value
            elif 'rynek' in label:
                # To jest już parsowane na poziomie listing, ale dla pewności
                if 'pierwotny' in value:
                    detailed_data['market'] = 'pierwotny'
                elif 'wtórny' in value:
                    detailed_data['market'] = 'wtórny'
        
        # Parsuj cechy boolean z sekcji "Informacje dodatkowe"
        additional_info_containers = details_container.select('span.css-axw7ok.esen0m94')
        for span in additional_info_containers:
            feature_text = clean_text(span.get_text()).lower()
            
            if 'balkon' in feature_text:
                detailed_data['has_balcony'] = True
            elif 'garaż' in feature_text or 'parking' in feature_text:
                detailed_data['has_garage'] = True
            elif 'ogród' in feature_text or 'działka' in feature_text:
                detailed_data['has_garden'] = True
            elif 'piwnica' in feature_text:
                detailed_data['has_basement'] = True
            elif 'oddzielna kuchnia' in feature_text:
                detailed_data['has_separate_kitchen'] = True
            elif 'winda' in feature_text:
                detailed_data['has_elevator'] = True
            elif 'zmywarka' in feature_text:
                detailed_data['has_dishwasher'] = True
            elif 'lodówka' in feature_text:
                detailed_data['has_fridge'] = True
            elif 'piekarnik' in feature_text:
                detailed_data['has_oven'] = True
        
        # Pobierz ID ogłoszenia z sekcji opisu
        try:
            # Szukaj ID w sekcji z opisem - używamy dokładnego selektora z przykładu
            id_element = soup.select_one('p.e1izz2zk2.css-htq2ld')
            if id_element and 'ID:' in id_element.get_text():
                id_text = id_element.get_text()
                # Wyciągnij samo ID (np. z "ID: 66708040")
                id_match = re.search(r'ID:\s*(\d+)', id_text)
                if id_match:
                    detailed_data['listing_id'] = id_match.group(1)
                    logger.debug(f"✅ Pobrano ID ogłoszenia: {detailed_data['listing_id']}")
            else:
                # Fallback - szukaj innych możliwych selektorów ID
                fallback_selectors = [
                    "p:contains('ID:')",
                    "[data-cy*='id']",
                    "*:contains('ID:')"
                ]
                for selector in fallback_selectors:
                    try:
                        id_element = soup.select_one(selector)
                        if id_element and 'ID:' in id_element.get_text():
                            id_text = id_element.get_text()
                            id_match = re.search(r'ID:\s*(\d+)', id_text)
                            if id_match:
                                detailed_data['listing_id'] = id_match.group(1)
                                logger.debug(f"✅ Pobrano ID (fallback): {detailed_data['listing_id']}")
                                break
                    except:
                        continue
        except Exception as e:
            logger.warning(f"⚠️ Nie udało się pobrać ID ogłoszenia: {e}")
        
        # Parsuj sekcje rozwijane (Wyposażenie, Zabezpieczenia, Media)
        parse_equipment_sections(soup, detailed_data)
        
        logger.debug(f"✅ Szczegóły pobrane: {sum(1 for v in detailed_data.values() if v)} pól wypełnionych")
        return detailed_data
        
    except Exception as e:
        logger.error(f"❌ Błąd scrapingu szczegółów {url}: {e}")
        return {}

def parse_equipment_sections(soup, detailed_data: Dict):
    """
    Parsuje sekcje wyposażenia, zabezpieczeń i mediów z rozwijanych accordionów
    
    Args:
        soup: BeautifulSoup object strony
        detailed_data: Słownik do aktualizacji danymi
    """
    try:
        # Znajdź wszystkie sekcje accordion
        accordion_sections = soup.select('[data-isopen="false"] .n-accordionitem-content, [data-isopen="true"] .n-accordionitem-content')
        
        for section in accordion_sections:
            # Sprawdź content sekcji
            section_text = clean_text(section.get_text()).lower()
            
            # Parsuj cechy z wyposażenia
            equipment_spans = section.select('span.css-axw7ok.esen0m94')
            for span in equipment_spans:
                feature_text = clean_text(span.get_text()).lower()
                
                # Wyposażenie AGD
                if 'zmywarka' in feature_text:
                    detailed_data['has_dishwasher'] = True
                elif 'lodówka' in feature_text:
                    detailed_data['has_fridge'] = True
                elif 'piekarnik' in feature_text:
                    detailed_data['has_oven'] = True
                
                # Zabezpieczenia
                elif 'antywłamaniowe' in feature_text or 'drzwi antywłamaniowe' in feature_text:
                    if 'security_features' not in detailed_data:
                        detailed_data['security_features'] = []
                    detailed_data['security_features'].append('drzwi_antywlamaniowe')
                elif 'domofon' in feature_text or 'wideofon' in feature_text:
                    if 'security_features' not in detailed_data:
                        detailed_data['security_features'] = []
                    detailed_data['security_features'].append('domofon')
                
                # Media
                elif 'internet' in feature_text:
                    if 'media_features' not in detailed_data:
                        detailed_data['media_features'] = []
                    detailed_data['media_features'].append('internet')
                elif 'telewizja kablowa' in feature_text:
                    if 'media_features' not in detailed_data:
                        detailed_data['media_features'] = []
                    detailed_data['media_features'].append('tv_kablowa')
                elif 'telefon' in feature_text:
                    if 'media_features' not in detailed_data:
                        detailed_data['media_features'] = []
                    detailed_data['media_features'].append('telefon')
    
    except Exception as e:
        logger.debug(f"⚠️ Błąd parsowania sekcji wyposażenia: {e}")

def parse_address_components(address_raw: str) -> Dict[str, str]:
    """
    Parsuje adres na komponenty: ulica, dzielnica, miasto, województwo
    
    Przykłady formatów z Otodom:
    - "ul. Kanarkowa, Gutkowo, Olsztyn, warmińsko-mazurskie"
    - "ul. Jana Boenigka, Jaroty, Olsztyn, warmińsko-mazurskie"
    - "Tęczowy Las, Osiedle Generałów, Olsztyn, warmińsko-mazurskie"
    - "ul. Franciszka Hynka, Dywity, Dywity, olsztyński, warmińsko-mazurskie"
    
    Args:
        address_raw: Surowy adres z portalu
        
    Returns:
        Dict z komponentami adresu: {street, district, city, province}
    """
    if not address_raw:
        return {"street": None, "district": None, "city": None, "province": None}
    
    # Podziel na części po przecinkach
    parts = [part.strip() for part in address_raw.split(',') if part.strip()]
    
    if not parts:
        return {"street": None, "district": None, "city": None, "province": None}
    
    result = {"street": None, "district": None, "city": None, "province": None}
    
    # Ostatnia część to zazwyczaj województwo
    if len(parts) >= 1:
        result["province"] = parts[-1]
    
    # Druga od końca to zazwyczaj miasto główne lub powiat
    if len(parts) >= 2:
        potential_city = parts[-2]
        
        # Sprawdź czy to nie jest powiat (kończący się na -ski/-ński)
        if potential_city.endswith(('ski', 'ński', 'cki', 'dzki')):
            # To jest powiat, miasto może być wcześniej
            if len(parts) >= 3:
                result["city"] = parts[-3]
        else:
            result["city"] = potential_city
    
    # Trzecia od końca to zazwyczaj dzielnica/osiedle
    if len(parts) >= 3:
        potential_district = parts[-3]
        
        # Jeśli miasto nie zostało jeszcze ustalone
        if not result["city"]:
            result["city"] = potential_district
        else:
            result["district"] = potential_district
    
    # Pierwsza część to zazwyczaj ulica
    if len(parts) >= 1:
        potential_street = parts[0]
        
        # Sprawdź czy zawiera typowe prefiks ulicy
        street_prefixes = ['ul.', 'al.', 'pl.', 'os.', 'ul', 'al', 'pl', 'os']
        has_street_prefix = any(potential_street.lower().startswith(prefix) for prefix in street_prefixes)
        
        if has_street_prefix or 'ul.' in potential_street.lower():
            result["street"] = potential_street
        elif len(parts) == 4 and not result["district"]:
            # Jeśli nie ma prefiksu, ale mamy 4 części, może to być nazwa osiedla/ulicy
            result["street"] = potential_street
        elif len(parts) >= 4 and not result["district"]:
            # Może to być dzielnica
            result["district"] = potential_street
    
    # Dodatkowa logika dla przypadków specjalnych
    if len(parts) == 4:
        # Format: "ulica, dzielnica, miasto, województwo"
        result["street"] = parts[0]
        result["district"] = parts[1]
        result["city"] = parts[2]
        result["province"] = parts[3]
    elif len(parts) == 5:
        # Format: "ulica, dzielnica, miasto, powiat, województwo"
        result["street"] = parts[0]
        result["district"] = parts[1]
        result["city"] = parts[2]
        # parts[3] to powiat - pomijamy
        result["province"] = parts[4]
    
    # Walidacja i oczyszczenie
    for key in result:
        if result[key]:
            result[key] = result[key].strip()
            # Usuń puste stringi
            if result[key] == "":
                result[key] = None
    
    return result

if __name__ == "__main__":
    """Test scrapera"""
    print("🧪 TEST SCRAPERA OTODOM.PL - WIELOWĄTKOWA WERSJA")
    print("="*60)
    
    try:
        # Test z wielowątkowością (4 wątki) + geocoding
        start_time = time.time()
        listings = get_otodom_listings(max_pages=0, max_workers=4, enable_geocoding=True)
        end_time = time.time()
        execution_time = end_time - start_time
        
        if listings:
            print(f"✅ Pobrano {len(listings)} ogłoszeń w {execution_time:.2f} sekund")
            print(f"⚡ Średni czas na ogłoszenie: {execution_time/len(listings):.2f}s")
            
            # Statystyki
            with_price = len([l for l in listings if l.get('price')])
            with_location = len([l for l in listings if l.get('address_raw')])
            with_area = len([l for l in listings if l.get('area')])
            with_rooms = len([l for l in listings if l.get('rooms')])
            
            # Statystyki cech boolean
            with_balcony = len([l for l in listings if l.get('has_balcony')])
            with_garage = len([l for l in listings if l.get('has_garage')])
            with_garden = len([l for l in listings if l.get('has_garden')])
            with_elevator = len([l for l in listings if l.get('has_elevator')])
            
            print(f"💰 Z cenami: {with_price}/{len(listings)} ({with_price/len(listings)*100:.1f}%)")
            print(f"📍 Z lokalizacją: {with_location}/{len(listings)} ({with_location/len(listings)*100:.1f}%)")
            print(f"📐 Z powierzchnią: {with_area}/{len(listings)} ({with_area/len(listings)*100:.1f}%)")
            print(f"🚪 Z pokojami: {with_rooms}/{len(listings)} ({with_rooms/len(listings)*100:.1f}%)")
            print(f"🏢 Z balkonem: {with_balcony}/{len(listings)} ({with_balcony/len(listings)*100:.1f}%)")
            print(f"🚗 Z garażem: {with_garage}/{len(listings)} ({with_garage/len(listings)*100:.1f}%)")
            print(f"🌿 Z ogrodem: {with_garden}/{len(listings)} ({with_garden/len(listings)*100:.1f}%)")
            print(f"🛗 Z windą: {with_elevator}/{len(listings)} ({with_elevator/len(listings)*100:.1f}%)")
            
            # Statystyki ID i adresów
            with_listing_id = len([l for l in listings if l.get('listing_id')])
            with_street = len([l for l in listings if l.get('street')])
            with_city = len([l for l in listings if l.get('city')])
            with_province = len([l for l in listings if l.get('province')])
            
            # Statystyki geocodingu
            with_coordinates = len([l for l in listings if l.get('latitude') and l.get('longitude')])
            
            print(f"🆔 Z ID ogłoszenia: {with_listing_id}/{len(listings)} ({with_listing_id/len(listings)*100:.1f}%)")
            print(f"🏠 Z ulicą: {with_street}/{len(listings)} ({with_street/len(listings)*100:.1f}%)")
            print(f"🏙️ Z miastem: {with_city}/{len(listings)} ({with_city/len(listings)*100:.1f}%)")
            print(f"📍 Z województwem: {with_province}/{len(listings)} ({with_province/len(listings)*100:.1f}%)")
            print(f"🌍 Z współrzędnymi: {with_coordinates}/{len(listings)} ({with_coordinates/len(listings)*100:.1f}%)")
            
            print(f"\n🚀 INFORMACJE O WIELOWĄTKOWOŚCI:")
            print(f"   • Użyto 4 wątków dla scrapowania szczegółów")
            print(f"   • Znaczne przyspieszenie w porównaniu do wersji sekwencyjnej")
            print(f"   • Thread-safe error handling i progress tracking")
            print(f"   • Geocoding zintegrowany: {'✅ WŁĄCZONY' if with_coordinates > 0 else '⚠️ WYŁĄCZONY'}")
            
            # Przykład
            if listings:
                listing = listings[0]
                print(f"\n📋 PRZYKŁAD NOWEJ STRUKTURY:")
                print(f"   ID: {listing.get('listing_id', 'brak')}")
                print(f"   Tytuł: {listing.get('title_raw', '')[:50]}...")
                print(f"   Cena: {listing.get('price', 0):,} zł")
                print(f"   Powierzchnia: {listing.get('area')} m²")
                print(f"   Pokoje: {listing.get('rooms')}")
                print(f"   Adres surowy: {listing.get('address_raw', '')}")
                print(f"   Ulica: {listing.get('street', 'brak')}")
                print(f"   Dzielnica: {listing.get('district', 'brak')}")
                print(f"   Miasto: {listing.get('city', 'brak')}")
                print(f"   Województwo: {listing.get('province', 'brak')}")
                print(f"   Rynek: {listing.get('market')}")
                print(f"   Balkon: {listing.get('has_balcony')}")
                print(f"   Garaż: {listing.get('has_garage')}")
                print(f"   Ogród: {listing.get('has_garden')}")
                print(f"   Winda: {listing.get('has_elevator')}")
                
                # Współrzędne
                lat = listing.get('latitude')
                lon = listing.get('longitude')
                if lat and lon:
                    print(f"   Współrzędne: {lat:.6f}, {lon:.6f} ✅")
                else:
                    print(f"   Współrzędne: Brak ❌")
        else:
            print("❌ Nie pobrano żadnych ogłoszeń")
            
    except Exception as e:
        print(f"❌ Błąd: {e}") 