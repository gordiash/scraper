#!/usr/bin/env python3
"""
PARSER ADRESÓW - ROZDZIELANIE LOKALIZACJI Z BAZY MYSQL
Analizuje i rozdziela lokalizacje z tabeli nieruchomosci na komponenty
"""

import re
import argparse
import logging
import sys
import os
from typing import Dict, List, Optional, Tuple

# Dodaj główny katalog do ścieżki  
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from mysql_utils import get_mysql_connection

# Konfiguracja logowania
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# SŁOWNIKI MAPOWANIA - ROZSZERZONE

# Prefiksy ulic
STREET_PREFIXES = {
    'ul.': 'ulica',
    'Ul.': 'ulica', 
    'UL.': 'ulica',
    'al.': 'aleja',
    'Al.': 'aleja',
    'AL.': 'aleja', 
    'pl.': 'plac',
    'Pl.': 'plac',
    'PL.': 'plac',
    'os.': 'osiedle',
    'Os.': 'osiedle',
    'OS.': 'osiedle',
    'rondo': 'rondo',
    'Rondo': 'rondo',
    'bulwar': 'bulwar',
    'Bulwar': 'bulwar'
}

# Mapowanie miast - DOKŁADNE nazwy
CITY_MAPPING = {
    # Warszawa i okolice
    'Warszawa': 'Warszawa',
    'warszawa': 'Warszawa',
    'WARSZAWA': 'Warszawa',
    'Piaseczno': 'Piaseczno',
    'Legionowo': 'Legionowo',
    'Pruszków': 'Pruszków',
    'Józefów': 'Józefów',
    'Konstancin-Jeziorna': 'Konstancin-Jeziorna',
    'Marki': 'Marki',
    'Ząbki': 'Ząbki',
    'Kobyłka': 'Kobyłka',
    'Łomianki': 'Łomianki',
    'Piastów': 'Piastów',
    'Michałowice': 'Michałowice',
    'Raszyn': 'Raszyn',
    'Wilanów': 'Warszawa',  # dzielnica Warszawy
    'Ursus': 'Warszawa',    # dzielnica Warszawy
    'Bemowo': 'Warszawa',   # dzielnica Warszawy
    'Mokotów': 'Warszawa',  # dzielnica Warszawy
    'Wola': 'Warszawa',     # dzielnica Warszawy
    'Śródmieście': 'Warszawa', # dzielnica Warszawy
    'Praga': 'Warszawa',    # dzielnica Warszawy
    'Żoliborz': 'Warszawa', # dzielnica Warszawy
    'Ochota': 'Warszawa',   # dzielnica Warszawy
    'Targówek': 'Warszawa', # dzielnica Warszawy
    'Bielany': 'Warszawa',  # dzielnica Warszawy
    'Białołęka': 'Warszawa', # dzielnica Warszawy
    'Wawer': 'Warszawa',    # dzielnica Warszawy
    'Wesołą': 'Warszawa',   # dzielnica Warszawy
    'Włochy': 'Warszawa',   # dzielnica Warszawy
    'Rembertów': 'Warszawa', # dzielnica Warszawy
    
    # Kraków i okolice
    'Kraków': 'Kraków',
    'kraków': 'Kraków',
    'KRAKÓW': 'Kraków',
    'Wieliczka': 'Wieliczka',
    'Niepołomice': 'Niepołomice',
    'Skawina': 'Skawina',
    'Zabierzów': 'Zabierzów',
    'Michałowice': 'Michałowice',
    
    # Gdańsk Trójmiasto
    'Gdańsk': 'Gdańsk',
    'gdańsk': 'Gdańsk',
    'GDAŃSK': 'Gdańsk',
    'Gdynia': 'Gdynia',
    'Sopot': 'Sopot',
    'Rumia': 'Rumia',
    'Reda': 'Reda',
    'Pruszcz Gdański': 'Pruszcz Gdański',
    'Gdański': 'Pruszcz Gdański',  # często skracane
    
    # Wrocław
    'Wrocław': 'Wrocław',
    'wrocław': 'Wrocław',
    'WROCŁAW': 'Wrocław',
    'Oławą': 'Oława',
    'Kobierzyce': 'Kobierzyce',
    'Długołęka': 'Długołęka',
    
    # Poznań
    'Poznań': 'Poznań',
    'poznań': 'Poznań',
    'POZNAŃ': 'Poznań',
    'Luboń': 'Luboń',
    'Puszczykowo': 'Puszczykowo',
    'Swarzędz': 'Swarzędz',
    
    # Łódź
    'Łódź': 'Łódź',
    'łódź': 'Łódź',
    'ŁÓDŹ': 'Łódź',
    'Pabianice': 'Pabianice',
    'Zgierz': 'Zgierz',
    
    # Katowice/Śląsk
    'Katowice': 'Katowice',
    'katowice': 'Katowice',
    'KATOWICE': 'Katowice',
    'Sosnowiec': 'Sosnowiec',
    'Gliwice': 'Gliwice',
    'Zabrze': 'Zabrze',
    'Bytom': 'Bytom',
    'Ruda Śląska': 'Ruda Śląska',
    'Dąbrowa Górnicza': 'Dąbrowa Górnicza',
    'Tychy': 'Tychy',
    'Chorzów': 'Chorzów',
    'Mysłowice': 'Mysłowice',
    'Siemianowice Śląskie': 'Siemianowice Śląskie',
    'Będzin': 'Będzin',
    'Piekarny Śląskie': 'Piekary Śląskie',
    'Świętochłowice': 'Świętochłowice',
    
    # Inne większe miasta
    'Lublin': 'Lublin',
    'Bydgoszcz': 'Bydgoszcz',
    'Białystok': 'Białystok',
    'Olsztyn': 'Olsztyn',
    'Rzeszów': 'Rzeszów',
    'Kielce': 'Kielce',
    'Szczecin': 'Szczecin',
    'Toruń': 'Toruń',
    'Radom': 'Radom',
    'Płock': 'Płock',
    'Elbląg': 'Elbląg',
    'Opole': 'Opole',
    'Gorzów Wielkopolski': 'Gorzów Wielkopolski',
    'Zielona Góra': 'Zielona Góra',
    'Jelenia Góra': 'Jelenia Góra',
    'Nowy Sącz': 'Nowy Sącz',
    'Koszalin': 'Koszalin',
    'Słupsk': 'Słupsk',
    'Częstochowa': 'Częstochowa',
    'Rybnik': 'Rybnik',
    'Jastrzębie-Zdrój': 'Jastrzębie-Zdrój'
}

def clean_address_component(text: str) -> str:
    """Czyści komponent adresu z niepotrzebnych znaków"""
    if not text:
        return ""
    
    # Usuń nadmiarowe spacje i znaki specjalne
    text = re.sub(r'\s+', ' ', text.strip())
    text = re.sub(r'[^\w\s\.\-ąćęłńóśźżĄĆĘŁŃÓŚŹŻ]', ' ', text)
    text = re.sub(r'\s+', ' ', text.strip())
    
    return text

def identify_city(component: str) -> Optional[str]:
    """Identyfikuje miasto na podstawie komponentu adresu"""
    if not component:
        return None
    
    component_clean = clean_address_component(component)
    
    # Sprawdź dokładne dopasowanie
    if component_clean in CITY_MAPPING:
        return CITY_MAPPING[component_clean]
    
    # Sprawdź dopasowanie bez rozróżniania wielkości liter
    component_lower = component_clean.lower()
    for city_variant, city_name in CITY_MAPPING.items():
        if component_lower == city_variant.lower():
            return city_name
    
    return None

def identify_street(component: str) -> Optional[str]:
    """Identyfikuje ulicę na podstawie komponentu adresu"""
    if not component:
        return None
    
    component_clean = clean_address_component(component)
    
    # Sprawdź czy zawiera prefiks ulicy
    for prefix in STREET_PREFIXES.keys():
        if component_clean.lower().startswith(prefix.lower()):
            return component_clean
    
    # Sprawdź czy zawiera słowa kluczowe ulicy bez prefiksu
    street_keywords = ['ulica', 'aleja', 'plac', 'osiedle', 'rondo', 'bulwar']
    component_lower = component_clean.lower()
    
    for keyword in street_keywords:
        if keyword in component_lower:
            return component_clean
    
    # Jeśli zawiera numery, prawdopodobnie to ulica
    if re.search(r'\d+', component_clean):
        return component_clean
    
    return None

def parse_location_advanced(location: str) -> Dict[str, Optional[str]]:
    """
    Zaawansowane parsowanie lokalizacji na komponenty
    
    Args:
        location: Surowy tekst lokalizacji
    
    Returns:
        Dict z komponentami: city, district, street
    """
    if not location:
        return {"city": None, "district": None, "street": None}
    
    # Podziel po przecinkach
    components = [comp.strip() for comp in location.split(',') if comp.strip()]
    
    if not components:
        return {"city": None, "district": None, "street": None}
    
    result = {"city": None, "district": None, "street": None}
    
    # Strategia parsowania w zależności od liczby komponentów
    if len(components) == 1:
        # Tylko jeden komponent - sprawdź czy to miasto czy ulica
        component = components[0]
        city = identify_city(component)
        if city:
            result["city"] = city
        else:
            street = identify_street(component)
            if street:
                result["street"] = street
            else:
                # Prawdopodobnie dzielnica lub nieznane miasto
                result["district"] = clean_address_component(component)
    
    elif len(components) == 2:
        # Dwa komponenty - prawdopodobnie miasto + dzielnica lub miasto + ulica
        comp1, comp2 = components
        
        city1 = identify_city(comp1)
        city2 = identify_city(comp2)
        street1 = identify_street(comp1)
        street2 = identify_street(comp2)
        
        if city1:
            result["city"] = city1
            if street2:
                result["street"] = street2
            else:
                result["district"] = clean_address_component(comp2)
        elif city2:
            result["city"] = city2
            if street1:
                result["street"] = street1
            else:
                result["district"] = clean_address_component(comp1)
        else:
            # Żadne nie jest rozpoznanym miastem
            if street1:
                result["street"] = street1
                result["district"] = clean_address_component(comp2)
            elif street2:
                result["street"] = street2
                result["district"] = clean_address_component(comp1)
            else:
                # Prawdopodobnie dzielnica + pod-dzielnica
                result["district"] = clean_address_component(comp1)
    
    elif len(components) >= 3:
        # Trzy lub więcej komponentów - miasto + dzielnica + ulica
        comp1, comp2, comp3 = components[0], components[1], components[2]
        
        # Sprawdź które są miastami
        cities = [(i, identify_city(comp)) for i, comp in enumerate([comp1, comp2, comp3]) if identify_city(comp)]
        streets = [(i, identify_street(comp)) for i, comp in enumerate([comp1, comp2, comp3]) if identify_street(comp)]
        
        if cities:
            # Użyj pierwszego rozpoznanego miasta
            city_idx, city_name = cities[0]
            result["city"] = city_name
            
            # Przypisz pozostałe komponenty
            remaining_components = [comp for i, comp in enumerate([comp1, comp2, comp3]) if i != city_idx]
            
            if streets:
                # Znajdź ulicę wśród pozostałych komponentów
                for street_idx, street_name in streets:
                    if street_idx != city_idx:
                        result["street"] = street_name
                        break
            
            # Przypisz pierwszy nie-miasto, nie-ulica jako dzielnicę
            for i, comp in enumerate([comp1, comp2, comp3]):
                if i != city_idx and comp != result.get("street"):
                    result["district"] = clean_address_component(comp)
                    break
        else:
            # Brak rozpoznanych miast - użyj pierwszego jako potencjalne miasto
            result["city"] = clean_address_component(comp1)
            result["district"] = clean_address_component(comp2)
            
            if identify_street(comp3):
                result["street"] = comp3
            else:
                result["street"] = clean_address_component(comp3)
    
    return result

def process_all_locations(max_locations: int = 500, batch_size: int = 100) -> Dict[str, int]:
    """
    Przetwarza wszystkie lokalizacje z bazy danych MySQL
    
    Args:
        max_locations: Maksymalna liczba lokalizacji do przetworzenia
        batch_size: Rozmiar batcha dla paginacji
    
    Returns:
        Dict ze statystykami przetwarzania
    """
    logger.info(f"🏠 ROZPOCZĘCIE PARSOWANIA ADRESÓW - MySQL")
    logger.info(f"📊 Maksymalna liczba lokalizacji: {max_locations}")
    logger.info(f"📦 Rozmiar batcha: {batch_size}")
    
    stats = {
        "total_processed": 0,
        "successful_saves": 0,
        "failed_saves": 0,
        "cities_found": 0,
        "districts_found": 0,
        "streets_found": 0
    }
    
    offset = 0
    processed_count = 0
    
    while processed_count < max_locations:
        # Pobierz batch danych
        current_batch_size = min(batch_size, max_locations - processed_count)
        listings = get_listings_batch(offset=offset, page_size=current_batch_size)
        
        if not listings:
            logger.info(f"✅ Koniec danych. Przetworzono łącznie: {processed_count}")
            break
        
        logger.info(f"📦 Przetwarzanie batcha {offset//batch_size + 1}: {len(listings)} ogłoszeń")
        
        for listing in listings:
            try:
                listing_id = listing['ad_id']
                address_raw = listing['address_raw']
                
                if not address_raw:
                    continue
                
                # Parsuj adres
                parsed = parse_location_advanced(address_raw)
                
                # Aktualizuj statystyki
                if parsed.get('city'):
                    stats["cities_found"] += 1
                if parsed.get('district'):
                    stats["districts_found"] += 1
                if parsed.get('street'):
                    stats["streets_found"] += 1
                
                # Zapisz do bazy danych
                if any(parsed.values()):  # Jeśli cokolwiek zostało sparsowane
                    success = save_parsed_address(listing_id, parsed)
                    if success:
                        stats["successful_saves"] += 1
                        logger.debug(f"✅ ID {listing_id}: {parsed}")
                    else:
                        stats["failed_saves"] += 1
                        logger.warning(f"❌ Błąd zapisu ID {listing_id}")
                
                stats["total_processed"] += 1
                processed_count += 1
                
                if processed_count >= max_locations:
                    break
                    
            except Exception as e:
                logger.error(f"❌ Błąd przetwarzania ogłoszenia {listing.get('ad_id', 'UNKNOWN')}: {e}")
                stats["failed_saves"] += 1
        
        offset += len(listings)
    
    # Wyświetl podsumowanie
    print_processing_summary(stats)
    
    return stats

def print_processing_summary(stats: Dict[str, int]):
    """Wyświetla podsumowanie przetwarzania"""
    print("\n" + "="*80)
    print("📊 PODSUMOWANIE PARSOWANIA ADRESÓW")
    print("="*80)
    print(f"📋 Łącznie przetworzonych: {stats['total_processed']:,}")
    print(f"✅ Udanych zapisów: {stats['successful_saves']:,}")
    print(f"❌ Nieudanych zapisów: {stats['failed_saves']:,}")
    
    if stats['total_processed'] > 0:
        success_rate = (stats['successful_saves'] / stats['total_processed']) * 100
        print(f"📈 Skuteczność: {success_rate:.1f}%")
    
    print(f"\n🏷️ STATYSTYKI KOMPONENTÓW:")
    print(f"🏙️ Miast znalezionych: {stats['cities_found']:,}")
    print(f"🏘️ Dzielnic znalezionych: {stats['districts_found']:,}")
    print(f"🛣️ Ulic znalezionych: {stats['streets_found']:,}")
    
    if stats['total_processed'] > 0:
        city_rate = (stats['cities_found'] / stats['total_processed']) * 100
        district_rate = (stats['districts_found'] / stats['total_processed']) * 100
        street_rate = (stats['streets_found'] / stats['total_processed']) * 100
        
        print(f"📈 Pokrycie miast: {city_rate:.1f}%")
        print(f"📈 Pokrycie dzielnic: {district_rate:.1f}%")
        print(f"📈 Pokrycie ulic: {street_rate:.1f}%")
    
    print("="*80)

def check_mysql_connection() -> bool:
    """Sprawdza połączenie z MySQL"""
    try:
        connection = get_mysql_connection()
        cursor = connection.cursor()
        
        # Sprawdź czy tabela nieruchomosci istnieje
        cursor.execute("SHOW TABLES LIKE 'nieruchomosci'")
        result = cursor.fetchone()
        
        cursor.close()
        connection.close()
        
        if result:
            logger.info("✅ Połączenie z MySQL działa, tabela 'nieruchomosci' istnieje")
            return True
        else:
            logger.error("❌ Tabela 'nieruchomosci' nie istnieje w MySQL")
            logger.info("💡 Uruchom skrypt: sql/create_nieruchomosci_mysql.sql")
            return False
            
    except Exception as e:
        logger.error(f"❌ Błąd połączenia z MySQL: {e}")
        return False

def get_listings_batch(offset: int = 0, page_size: int = 100) -> List[Dict]:
    """
    Pobiera batch ogłoszeń z tabeli nieruchomosci w MySQL
    
    Args:
        offset: Offset dla paginacji
        page_size: Rozmiar strony
    
    Returns:
        List[Dict]: Lista ogłoszeń z adresami do przetworzenia
    """
    try:
        connection = get_mysql_connection()
        cursor = connection.cursor(dictionary=True)
        
        # Pobierz ogłoszenia z adresami, które nie zostały jeszcze sparsowane
        query = """
        SELECT ad_id, address_raw 
        FROM nieruchomosci 
        WHERE address_raw IS NOT NULL 
        AND (city IS NULL OR district IS NULL)
        LIMIT %s OFFSET %s
        """
        
        cursor.execute(query, (page_size, offset))
        results = cursor.fetchall()
        
        cursor.close()
        connection.close()
        
        return results if results else []
        
    except Exception as e:
        logger.error(f"❌ Błąd pobierania ogłoszeń z MySQL: {e}")
        return []

def save_parsed_address(listing_id: int, parsed_data: Dict) -> bool:
    """
    Zapisuje sparsowane dane adresu bezpośrednio do tabeli nieruchomosci
    
    Args:
        listing_id: ID ogłoszenia
        parsed_data: Sparsowane dane adresu
    
    Returns:
        bool: True jeśli zapis się udał
    """
    try:
        connection = get_mysql_connection()
        cursor = connection.cursor()
        
        # Aktualizuj pola w tabeli nieruchomosci
        update_fields = []
        values = []
        
        if parsed_data.get('city'):
            update_fields.append("city = %s")
            values.append(parsed_data['city'])
            
        if parsed_data.get('district'):
            update_fields.append("district = %s")
            values.append(parsed_data['district'])
            
        if parsed_data.get('street'):
            update_fields.append("street = %s")
            values.append(parsed_data['street'])
        
        if not update_fields:
            return False
        
        # Dodaj updated_at i ad_id na końcu
        update_fields.append("updated_at = CURRENT_TIMESTAMP")
        values.append(listing_id)
        
        query = f"""
        UPDATE nieruchomosci 
        SET {', '.join(update_fields)}
        WHERE ad_id = %s
        """
        
        cursor.execute(query, values)
        connection.commit()
        
        success = cursor.rowcount > 0
        
        cursor.close()
        connection.close()
        
        if success:
            logger.debug(f"✅ Zaktualizowano adres dla ogłoszenia ID {listing_id}")
        else:
            logger.warning(f"⚠️ Nie znaleziono ogłoszenia ID {listing_id}")
            
        return success
        
    except Exception as e:
        logger.error(f"❌ Błąd zapisu adresu do MySQL: {e}")
        return False

def main():
    """Główna funkcja z obsługą argumentów"""
    if not check_mysql_connection():
        print("❌ Tabela 'nieruchomosci' nie istnieje. Utwórz ją najpierw w MySQL.")
        return
        
    parser = argparse.ArgumentParser(description='Parser adresów z bazy MySQL')
    parser.add_argument('--limit', type=int, default=500, help='Maksymalna liczba adresów do przetworzenia')
    parser.add_argument('--batch-size', type=int, default=100, help='Rozmiar batcha')
    parser.add_argument('--test', action='store_true', help='Tryb testowy - tylko wyświetl przykłady')
    
    args = parser.parse_args()
    
    if args.test:
        # Tryb testowy
        test_locations = [
            "Warszawa, Mokotów, ul. Puławska 15",
            "Kraków, Stare Miasto, Rynek Główny 1", 
            "Gdańsk, Śródmieście, ul. Długa 20",
            "Poznań, Grunwald, os. Przyjaźni 10",
            "Wrocław, Krzyki, al. Powstańców Śląskich 5"
        ]
        
        print("🧪 TRYB TESTOWY - PRZYKŁADY PARSOWANIA")
        print("="*60)
        
        for i, location in enumerate(test_locations, 1):
            print(f"\n{i}. Testowanie: '{location}'")
            parsed = parse_location_advanced(location)
            print(f"   Wynik: {parsed}")
    else:
        # Główne przetwarzanie
        process_all_locations(args.limit, args.batch_size)

if __name__ == "__main__":
    main() 