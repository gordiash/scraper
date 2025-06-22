#!/usr/bin/env python3
"""
GEOCODER - UZUPEŁNIANIE WSPÓŁRZĘDNYCH GEOGRAFICZNYCH
Pobiera adresy z tabeli addresses i uzupełnia kolumny longitude i latitude
"""
import logging
import time
import requests
import sys
import os
from typing import Dict, List, Optional, Tuple

# Dodaj główny katalog do ścieżki
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from mysql_utils import get_mysql_connection

# Konfiguracja logowania
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Konfiguracja geocodingu - ZOPTYMALIZOWANA
NOMINATIM_BASE_URL = "https://nominatim.openstreetmap.org/search"
DELAY_BETWEEN_REQUESTS = 1  # Zmniejszone z 1.1s
MAX_RETRIES = 2  # Zmniejszone z 3 dla szybkości
BATCH_SIZE = 100  # Zwiększone z 50

def build_simple_search_query(address_data: Dict) -> str:
    """
    Buduje UPROSZCZONE zapytanie wyszukiwania - tylko najważniejsze elementy
    
    Args:
        address_data: Słownik z danymi adresu
    
    Returns:
        str: Uproszczone zapytanie do geocodingu
    """
    components = []
    
    # 1. Ulica (bez "ul.", "al." itp.) - tylko nazwa
    if address_data.get('street_name'):
        street = address_data['street_name']
        # Usuń prefiksy ul., al., pl., os.
        street = street.replace('Ul. ', '').replace('Al. ', '').replace('Pl. ', '').replace('Os. ', '')
        street = street.replace('ul. ', '').replace('al. ', '').replace('pl. ', '').replace('os. ', '')
        if street:
            components.append(street)
    
    # 2. Miasto (obowiązkowe) - bez dzielnic!
    if address_data.get('city'):
        city = address_data['city']
        # Popraw znane błędy w nazwach miast
        city_fixes = {
            'Gdański': 'Pruszcz Gdański',
            'Łomianki': 'Łomianki',  # OK
            'Oleśnica': 'Oleśnica',  # OK
        }
        city = city_fixes.get(city, city)
        components.append(city)
    
    # 3. Zawsze dodaj "Polska"
    components.append("Polska")
    
    query = ", ".join(components)
    logger.debug(f"Uproszczone zapytanie geocoding: {query}")
    return query

def build_fallback_query(address_data: Dict) -> str:
    """
    Buduje zapytanie fallback - tylko miasto + Polska
    """
    if address_data.get('city'):
        city = address_data['city']
        # Popraw znane błędy
        city_fixes = {
            'Gdański': 'Pruszcz Gdański',
        }
        city = city_fixes.get(city, city)
        return f"{city}, Polska"
    return "Polska"

def geocode_address_improved(query: str, fallback_query: str = None) -> Optional[Tuple[float, float]]:
    """
    Pobiera współrzędne z próbą fallback
    """
    params = {
        'q': query,
        'format': 'json',
        'limit': 1,
        'countrycodes': 'pl',
        'addressdetails': 0,  # Wyłączone dla szybkości
        'extratags': 0       # Wyłączone dla szybkości
    }
    
    headers = {
        'User-Agent': 'Polish Real Estate Scraper/1.0 (educational purpose)'
    }
    
    # Próba 1: Główne zapytanie
    for attempt in range(MAX_RETRIES):
        try:
            logger.debug(f"Geocoding attempt {attempt + 1}: {query}")
            response = requests.get(NOMINATIM_BASE_URL, params=params, headers=headers, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            if data and len(data) > 0:
                result = data[0]
                lat = float(result['lat'])
                lon = float(result['lon'])
                
                # Walidacja współrzędnych dla Polski
                if 49.0 <= lat <= 54.9 and 14.1 <= lon <= 24.2:
                    logger.debug(f"Znaleziono współrzędne (główne): {lat}, {lon}")
                    return (lat, lon)
                else:
                    logger.warning(f"Współrzędne poza Polską: {lat}, {lon}")
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Błąd HTTP podczas geocodingu (próba {attempt + 1}): {e}")
            if attempt < MAX_RETRIES - 1:
                time.sleep(2 ** attempt)
        except (ValueError, KeyError) as e:
            logger.error(f"Błąd parsowania odpowiedzi geocodingu: {e}")
            break
        except Exception as e:
            logger.error(f"Nieoczekiwany błąd geocodingu: {e}")
            break
    
    # Próba 2: Fallback query (jeśli podane)
    if fallback_query and fallback_query != query:
        logger.debug(f"Próba fallback: {fallback_query}")
        time.sleep(DELAY_BETWEEN_REQUESTS)
        
        params['q'] = fallback_query
        
        try:
            response = requests.get(NOMINATIM_BASE_URL, params=params, headers=headers, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            if data and len(data) > 0:
                result = data[0]
                lat = float(result['lat'])
                lon = float(result['lon'])
                
                if 49.0 <= lat <= 54.9 and 14.1 <= lon <= 24.2:
                    logger.debug(f"Znaleziono współrzędne (fallback): {lat}, {lon}")
                    return (lat, lon)
                    
        except Exception as e:
            logger.error(f"Błąd fallback geocodingu: {e}")
    
    logger.warning(f"Brak wyników geocodingu dla: {query}")
    return None

def get_addresses_without_coordinates(limit: int = 100) -> List[Dict]:
    """
    Pobiera nieruchomości bez współrzędnych z bazy danych MySQL
    
    Args:
        limit: Maksymalna liczba adresów do pobrania
    
    Returns:
        List[Dict]: Lista adresów bez współrzędnych
    """
    try:
        connection = get_mysql_connection()
        cursor = connection.cursor(dictionary=True)
        
        # Pobierz nieruchomości gdzie latitude I longitude są null
        query = """
        SELECT ad_id, address_raw, city, district, street 
        FROM nieruchomosci 
        WHERE latitude IS NULL AND longitude IS NULL 
        AND address_raw IS NOT NULL
        LIMIT %s
        """
        
        cursor.execute(query, (limit,))
        results = cursor.fetchall()
        
        cursor.close()
        connection.close()
        
        if results:
            logger.info(f"📊 Znaleziono {len(results)} nieruchomości bez współrzędnych")
            return results
        else:
            logger.info("✅ Wszystkie nieruchomości mają już współrzędne")
            return []
            
    except Exception as e:
        logger.error(f"❌ Błąd pobierania adresów z MySQL: {e}")
        return []

def update_address_coordinates(address_id: int, latitude: float, longitude: float) -> bool:
    """Aktualizuje współrzędne dla nieruchomości w MySQL"""
    try:
        connection = get_mysql_connection()
        cursor = connection.cursor()
        
        query = """
        UPDATE nieruchomosci 
        SET latitude = %s, longitude = %s, updated_at = CURRENT_TIMESTAMP
        WHERE ad_id = %s
        """
        
        cursor.execute(query, (latitude, longitude, address_id))
        connection.commit()
        
        if cursor.rowcount > 0:
            logger.debug(f"✅ Zaktualizowano współrzędne dla nieruchomości ID {address_id}")
            cursor.close()
            connection.close()
            return True
        else:
            logger.warning(f"⚠️ Nie znaleziono nieruchomości ID {address_id}")
            cursor.close()
            connection.close()
            return False
            
    except Exception as e:
        logger.error(f"❌ Błąd aktualizacji współrzędnych w MySQL: {e}")
        return False

def update_coordinates_batch_optimized(coordinates_data: List[Tuple[int, Optional[Tuple[float, float]]]]) -> Dict[str, int]:
    """ZOPTYMALIZOWANY batch update współrzędnych w MySQL"""
    stats = {"success": 0, "failed": 0, "skipped": 0}
    
    # Przygotuj dane do batch update
    updates = []
    for address_id, coordinates in coordinates_data:
        if coordinates and address_id:
            lat, lon = coordinates
            updates.append((lat, lon, address_id))
    
    if not updates:
        stats["skipped"] = len(coordinates_data)
        return stats
    
    try:
        connection = get_mysql_connection()
        cursor = connection.cursor()
        
        # Batch update używając MySQL batch execute
        query = """
        UPDATE nieruchomosci 
        SET latitude = %s, longitude = %s, updated_at = CURRENT_TIMESTAMP
        WHERE ad_id = %s
        """
        
        # Przetwarzaj po 50 na raz dla wydajności MySQL
        batch_size = 50
        for i in range(0, len(updates), batch_size):
            batch = updates[i:i + batch_size]
            
            try:
                cursor.executemany(query, batch)
                connection.commit()
                stats["success"] += cursor.rowcount
                
                logger.debug(f"✅ Batch {i//batch_size + 1}: zaktualizowano {cursor.rowcount} rekordów")
                
            except Exception as e:
                logger.error(f"Błąd batch update {i//batch_size + 1}: {e}")
                stats["failed"] += len(batch)
                connection.rollback()
            
            # Krótkie opóźnienie między mini-batchami
            if i + batch_size < len(updates):
                time.sleep(0.1)
        
        cursor.close()
        connection.close()
        
        # Policz pominięte
        stats["skipped"] = len(coordinates_data) - len(updates)
        
        logger.info(f"✅ MySQL Batch update: {stats['success']} sukces, {stats['failed']} błędów, {stats['skipped']} pominiętych")
        
    except Exception as e:
        logger.error(f"❌ Błąd MySQL batch update: {e}")
        stats["failed"] = len(updates)
        stats["skipped"] = len(coordinates_data) - len(updates)
    
    return stats

def process_geocoding_batch_improved(addresses: List[Dict]) -> Dict[str, int]:
    """
    ZOPTYMALIZOWANY batch processing z grupowaniem requestów - MySQL
    """
    stats = {
        "processed": 0,
        "success": 0,
        "failed": 0,
        "skipped": 0,
        "fallback_success": 0
    }
    
    # Przygotuj dane do geocodingu
    geocoding_tasks = []
    
    for address in addresses:
        address_id = address['ad_id']
        
        # Sprawdź czy już ma współrzędne
        if address.get('latitude') and address.get('longitude'):
            logger.debug(f"Nieruchomość ID {address_id} już ma współrzędne - pomijam")
            stats["skipped"] += 1
            continue
        
        # Buduj zapytania na podstawie danych z MySQL
        address_data = {
            'city': address.get('city'),
            'district': address.get('district'),
            'street_name': address.get('street'),
            'address_raw': address.get('address_raw')
        }
        
        main_query = build_simple_search_query(address_data)
        fallback_query = build_fallback_query(address_data)
        
        if not main_query or main_query == "Polska":
            logger.warning(f"Pusty adres dla ID {address_id} - pomijam")
            stats["skipped"] += 1
            continue
        
        geocoding_tasks.append((address_id, main_query, fallback_query))
    
    if not geocoding_tasks:
        return stats
    
    # Przetwarzaj geocoding w grupach po 10 dla lepszej wydajności
    batch_results = []
    group_size = 10
    
    for i in range(0, len(geocoding_tasks), group_size):
        group = geocoding_tasks[i:i + group_size]
        
        for j, (address_id, main_query, fallback_query) in enumerate(group, 1):
            try:
                # Geocoding z fallback
                coordinates = geocode_address_improved(main_query, fallback_query)
                
                if coordinates:
                    batch_results.append((address_id, coordinates))
                    stats["success"] += 1
                    
                    # Sprawdź czy użyto fallback (uproszczone)
                    if main_query != fallback_query:
                        stats["fallback_success"] += 1
                    
                    logger.info(f"✅ {i+j}/{len(geocoding_tasks)} - ID {address_id}: {coordinates[0]:.6f}, {coordinates[1]:.6f}")
                else:
                    batch_results.append((address_id, None))
                    stats["failed"] += 1
                    logger.warning(f"⚠️ {i+j}/{len(geocoding_tasks)} - Brak współrzędnych dla ID {address_id}")
                
                stats["processed"] += 1
                
                # Opóźnienie między requestami (zmniejszone)
                if j < len(group):
                    time.sleep(DELAY_BETWEEN_REQUESTS)
                    
            except Exception as e:
                batch_results.append((address_id, None))
                stats["failed"] += 1
                logger.error(f"❌ Błąd przetwarzania nieruchomości ID {address_id}: {e}")
        
        # Krótkie opóźnienie między grupami
        if i + group_size < len(geocoding_tasks):
            time.sleep(0.5)
    
    # Batch update wszystkich wyników na raz
    if batch_results:
        logger.info(f"💾 Zapisuję {len(batch_results)} wyników batch update do MySQL...")
        update_stats = update_coordinates_batch_optimized(batch_results)
        
        # Skoryguj statystyki na podstawie rzeczywistego zapisu
        if update_stats["success"] != stats["success"]:
            logger.warning(f"⚠️ Różnica w zapisie: geocoded {stats['success']}, saved {update_stats['success']}")
    
    return stats

def update_all_coordinates_improved(batch_size: int = BATCH_SIZE, max_addresses: int = None) -> None:
    """
    Główna funkcja z ulepszonym algorytmem i obsługą offset
    """
    print("="*80)
    print("🚀 ZOPTYMALIZOWANY GEOCODER - UZUPEŁNIANIE WSPÓŁRZĘDNYCH")
    print("="*80)
    print(f"📊 Parametry:")
    print(f"   • Rozmiar batcha: {batch_size}")
    print(f"   • Maksymalne adresy: {max_addresses or 'wszystkie'}")
    print(f"   • Opóźnienie między requestami: {DELAY_BETWEEN_REQUESTS}s")
    print(f"   • Maksymalne retry: {MAX_RETRIES}")
    print(f"   • Uproszczone zapytania: TAK")
    print(f"   • Fallback queries: TAK")
    print(f"   • Batch update: TAK")
    print("="*80)
    
    total_stats = {
        "processed": 0,
        "success": 0,
        "failed": 0,
        "skipped": 0,
        "fallback_success": 0
    }
    
    processed_count = 0
    batch_number = 1
    start_time = time.time()
    
    while True:
        # Pobierz następny batch z offset
        remaining_limit = batch_size
        if max_addresses:
            remaining_limit = min(batch_size, max_addresses - processed_count)
            if remaining_limit <= 0:
                break
        
        # Pobierz następny batch (zawsze pierwsze 50 bez współrzędnych)
        addresses = get_addresses_without_coordinates(limit=remaining_limit)
        
        if not addresses:
            print("✅ Wszystkie adresy mają już współrzędne!")
            break
        
        print(f"\n🔄 PRZETWARZANIE BATCHA {batch_number}")
        print(f"📋 Adresy w batchu: {len(addresses)}")
        print("-" * 60)
        
        # Pomiar czasu batcha
        batch_start_time = time.time()
        
        # Przetwórz batch
        batch_stats = process_geocoding_batch_improved(addresses)
        
        # Oblicz wydajność batcha
        batch_time = time.time() - batch_start_time
        addresses_per_second = len(addresses) / batch_time if batch_time > 0 else 0
        
        # Aktualizuj statystyki
        for key in total_stats:
            total_stats[key] += batch_stats[key]
        
        processed_count += len(addresses)
        
        # Podsumowanie batcha
        print(f"\n📊 WYNIKI BATCHA {batch_number}:")
        print(f"   ✅ Sukces: {batch_stats['success']}")
        print(f"   🔄 Fallback sukces: {batch_stats['fallback_success']}")
        print(f"   ❌ Błędy: {batch_stats['failed']}")
        print(f"   ⏭️ Pominięte: {batch_stats['skipped']}")
        print(f"   ⏱️ Czas: {batch_time:.1f}s ({addresses_per_second:.1f} adr/s)")
        
        # Sprawdź czy osiągnięto limit
        if max_addresses and processed_count >= max_addresses:
            break
        
        # Jeśli batch był mniejszy niż limit, to koniec
        if len(addresses) < batch_size:
            print(f"📄 Ostatni batch - pobrano {len(addresses)} < {batch_size}")
            break
        
        batch_number += 1
        
        # Zmniejszone opóźnienie między batchami
        print(f"⏳ Opóźnienie 2 sekundy przed następnym batchem...")
        time.sleep(2)
    
    # Podsumowanie końcowe z wydajnością
    total_time = time.time() - start_time
    addresses_per_second = total_stats['processed'] / total_time if total_time > 0 else 0
    
    print("\n" + "="*80)
    print("📊 PODSUMOWANIE ZOPTYMALIZOWANEGO GEOCODINGU")
    print("="*80)
    print(f"📋 Łącznie przetworzonych: {total_stats['processed']}")
    print(f"✅ Pomyślnie geocodowanych: {total_stats['success']}")
    print(f"🔄 Sukces przez fallback: {total_stats['fallback_success']}")
    print(f"❌ Błędów geocodingu: {total_stats['failed']}")
    print(f"⏭️ Pominiętych: {total_stats['skipped']}")
    print(f"⏱️ Całkowity czas: {total_time:.1f}s")
    print(f"🚀 Wydajność: {addresses_per_second:.1f} adresów/sekundę")
    
    if total_stats['processed'] > 0:
        success_rate = (total_stats['success'] / total_stats['processed']) * 100
        print(f"📈 Skuteczność: {success_rate:.1f}%")
        
        if total_stats['fallback_success'] > 0:
            fallback_rate = (total_stats['fallback_success'] / total_stats['success']) * 100
            print(f"🔄 Udział fallback: {fallback_rate:.1f}%")
    
    print("="*80)

def main_geocoding_process(max_addresses: int = 100, batch_size: int = 50) -> bool:
    """
    Główny proces geocodingu - prosty i niezawodny
    
    Args:
        max_addresses: Maksymalna liczba adresów do przetworzenia
        batch_size: Rozmiar batcha
    
    Returns:
        bool: True jeśli proces zakończył się sukcesem
    """
    print(f"\n🌍 URUCHAMIANIE GEOCODINGU")
    print(f"📊 Parametry: max_addresses={max_addresses}, batch_size={batch_size}")
    
    try:
        # Sprawdź połączenie z bazą
        connection = get_mysql_connection()
        connection.close()
        print("✅ Połączenie z bazą MySQL: OK")
    except Exception as e:
        print(f"❌ Błąd połączenia z bazą: {e}")
        return False
    
    total_processed = 0
    total_success = 0
    
    while total_processed < max_addresses:
        # Oblicz rozmiar batcha
        current_batch_size = min(batch_size, max_addresses - total_processed)
        
        print(f"\n🔄 Przetwarzanie batcha {current_batch_size} adresów...")
        
        # Pobierz adresy bez współrzędnych
        addresses = get_addresses_without_coordinates(current_batch_size)
        
        if not addresses:
            print("✅ Wszystkie adresy mają już współrzędne!")
            break
        
        # Przetwórz batch
        batch_stats = process_geocoding_batch_improved(addresses)
        
        total_processed += len(addresses)
        total_success += batch_stats.get('geocoded', 0)
        
        print(f"   📊 Batch: {batch_stats.get('geocoded', 0)}/{len(addresses)} geocoded")
        
        # Jeśli batch był mniejszy niż oczekiwany, to był ostatni
        if len(addresses) < current_batch_size:
            break
    
    # Podsumowanie
    success_rate = (total_success / total_processed * 100) if total_processed > 0 else 0
    print(f"\n📊 PODSUMOWANIE GEOCODINGU:")
    print(f"   • Przetworzonych: {total_processed}")
    print(f"   • Geocoded: {total_success}")
    print(f"   • Skuteczność: {success_rate:.1f}%")
    
    return True

if __name__ == "__main__":
    """Test geocodera"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Geocoder nieruchomości')
    parser.add_argument('--test', action='store_true', help='Uruchom test')
    parser.add_argument('--run', action='store_true', help='Uruchom geocoding')
    parser.add_argument('--max-addresses', type=int, default=50, help='Maksymalna liczba adresów')
    parser.add_argument('--batch-size', type=int, default=20, help='Rozmiar batcha')
    
    args = parser.parse_args()
    
    if args.test:
        print("🧪 TEST GEOCODERA")
        print("="*50)
        
        # Test połączenia z bazą
        try:
            connection = get_mysql_connection()
            cursor = connection.cursor()
            cursor.execute("SELECT COUNT(*) FROM nieruchomosci WHERE latitude IS NULL AND longitude IS NULL")
            count = cursor.fetchone()[0]
            print(f"📊 Nieruchomości bez współrzędnych: {count}")
            cursor.close()
            connection.close()
        except Exception as e:
            print(f"❌ Błąd połączenia z bazą: {e}")
            exit(1)
        
        # Test z małą próbką
        success = main_geocoding_process(max_addresses=5, batch_size=5)
        print(f"🎯 Test result: {'✅ SUKCES' if success else '❌ BŁĄD'}")
        
    elif args.run:
        print("🚀 URUCHAMIANIE GEOCODERA")
        success = main_geocoding_process(
            max_addresses=args.max_addresses,
            batch_size=args.batch_size
        )
        print(f"🎯 Wynik: {'✅ SUKCES' if success else '❌ BŁĄD'}")
        
    else:
        print("🌍 GEOCODER NIERUCHOMOŚCI")
        print("Użycie:")
        print("  python geocoder.py --test                    # Test na 5 adresach") 
        print("  python geocoder.py --run                     # Geocoding 50 adresów")
        print("  python geocoder.py --run --max-addresses 100 # Geocoding 100 adresów") 