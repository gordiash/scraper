#!/usr/bin/env python3
"""
MYSQL UTILS - OBSŁUGA BAZY DANYCH MYSQL
Zastępuje supabase_utils.py dla połączenia z bazą MySQL
"""
import logging
import os
import json
import mysql.connector
from mysql.connector import Error
from datetime import datetime
from typing import List, Dict, Tuple
from dotenv import load_dotenv

# Załaduj zmienne środowiskowe
load_dotenv()

# Konfiguracja logowania
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Konfiguracja MySQL
MYSQL_CONFIG = {
    'host': os.getenv('MYSQL_HOST', 'localhost'),
    'port': int(os.getenv('MYSQL_PORT', 3306)),
    'user': os.getenv('MYSQL_USER', 'root'),
    'password': os.getenv('MYSQL_PASSWORD', ''),
    'database': os.getenv('MYSQL_DATABASE', 'nieruchomosci_db'),
    'charset': 'utf8mb4',
    'collation': 'utf8mb4_unicode_ci',
    'autocommit': True,
    'raise_on_warnings': True
}

# Wymagane pola dla kompletnego ogłoszenia - ZAKTUALIZOWANE
REQUIRED_FIELDS = [
    'title_raw',   # Tytuł ogłoszenia (zmienione z 'title')
    'price',       # Cena (liczba)
    'address_raw', # Lokalizacja (zmienione z 'location')
    'url',         # Link do ogłoszenia
    'area',        # Powierzchnia (decimal)
    'rooms',       # Liczba pokoi (tinyint)
    'source'       # Źródło (portal)
]

# Cache dla istniejących kolumn - żeby nie sprawdzać za każdym razem
_table_columns_cache = {}

def get_mysql_connection():
    """
    Tworzy połączenie z bazą danych MySQL
    
    Returns:
        mysql.connector.MySQLConnection: Połączenie z bazą MySQL
    """
    try:
        connection = mysql.connector.connect(**MYSQL_CONFIG)
        if connection.is_connected():
            logger.debug("✅ Połączenie z MySQL nawiązane pomyślnie")
            return connection
    except Error as e:
        logger.error(f"❌ Błąd połączenia z MySQL: {e}")
        raise Exception(f"Nie można połączyć z bazą MySQL: {e}")

def validate_listing_completeness(listing: dict) -> tuple[bool, list]:
    """
    Sprawdza kompletność danych ogłoszenia zgodnie z nową strukturą bazy
    
    Args:
        listing: Słownik z danymi ogłoszenia
    
    Returns:
        tuple: (is_complete, missing_fields)
    """
    missing_fields = []
    
    # Sprawdź wymagane pola
    for field in REQUIRED_FIELDS:
        value = listing.get(field)
        if value is None or value == "" or str(value).lower() == "none":
            missing_fields.append(field)
    
    # Dodatkowe walidacje
    if listing.get('price') is not None and listing.get('price') <= 0:
        missing_fields.append('price (wartość <= 0)')
        
    if listing.get('area') is not None and listing.get('area') <= 0:
        missing_fields.append('area (wartość <= 0)')
        
    if listing.get('rooms') is not None and listing.get('rooms') <= 0:
        missing_fields.append('rooms (wartość <= 0)')
    
    is_complete = len(missing_fields) == 0
    return is_complete, missing_fields

def get_table_columns(table: str = "nieruchomosci") -> list:
    """
    Sprawdza jakie kolumny istnieją w tabeli MySQL
    
    Returns:
        list: Lista nazw kolumn
    """
    # Sprawdź cache
    if table in _table_columns_cache:
        return _table_columns_cache[table]
    
    try:
        connection = get_mysql_connection()
        cursor = connection.cursor()
        
        # Sprawdź kolumny w tabeli
        cursor.execute(f"DESCRIBE {table}")
        columns = [column[0] for column in cursor.fetchall()]
        
        cursor.close()
        connection.close()
        
        _table_columns_cache[table] = columns
        logger.info(f"📋 Dostępne kolumny w tabeli '{table}': {', '.join(columns)}")
        return columns
        
    except Error as e:
        logger.error(f"❌ Błąd sprawdzania kolumn tabeli {table}: {e}")
        # Zwróć nową strukturę kolumn jako fallback
        return [
            'ad_id', 'url', 'price', 'area', 'rooms', 'market', 'listing_date',
            'title_raw', 'address_raw', 'city', 'district', 'street',
            'latitude', 'longitude', 'has_balcony', 'has_garage', 'has_garden',
            'has_elevator', 'standard_of_finish', 'source', 'created_at', 'updated_at'
        ]

def save_listing(listing: dict, table: str = "nieruchomosci", require_complete: bool = True) -> bool:
    """
    Zapisuje ogłoszenie do tabeli MySQL zgodnie z nową strukturą bazy
    
    Args:
        listing: Słownik z danymi ogłoszenia
        table: Nazwa tabeli w MySQL
        require_complete: Czy wymagać kompletnych danych (domyślnie True)
    
    Returns:
        bool: True jeśli zapis się udał, False w przeciwnym razie
    """
    # WALIDACJA KOMPLETNOŚCI DANYCH
    if require_complete:
        is_complete, missing_fields = validate_listing_completeness(listing)
        if not is_complete:
            title = listing.get('title_raw', 'Brak tytułu')[:30]
            logger.warning(f"❌ Niepełne dane - pomijam: {title}... (brak: {', '.join(missing_fields)})")
            return False
    
    try:
        connection = get_mysql_connection()
        cursor = connection.cursor()
        
        # Sprawdź czy ogłoszenie już istnieje (po URL)
        url = listing.get("url", "")
        if url:
            cursor.execute(f"SELECT ad_id FROM {table} WHERE url = %s", (url,))
            if cursor.fetchone():
                logger.debug(f"Ogłoszenie już istnieje: {url}")
                cursor.close()
                connection.close()
                return False
        
        # Pobierz dostępne kolumny
        available_columns = get_table_columns(table)
        
        # WSZYSTKIE MOŻLIWE DANE - struktura zgodna z nową bazą danych
        all_possible_data = {
            # Podstawowe informacje (ad_id pomijamy - AUTO_INCREMENT)
            "url": listing.get("url"),
            "listing_id": listing.get("listing_id"),
            "title_raw": listing.get("title_raw"),
            "address_raw": listing.get("address_raw"),
            
            # Cena i powierzchnia - konwersja na odpowiednie typy
            "price": float(listing.get("price")) if listing.get("price") is not None and listing.get("price") != '' else None,
            "area": float(listing.get("area")) if listing.get("area") is not None and listing.get("area") != '' else None,
            "rooms": int(listing.get("rooms")) if listing.get("rooms") is not None and listing.get("rooms") != '' else None,
            
            # Typ rynku
            "market": listing.get("market"),
            
            # Data ogłoszenia
            "listing_date": listing.get("listing_date"),
            
            # Lokalizacja
            "city": listing.get("city"),
            "district": listing.get("district"),
            "street": listing.get("street"),
            "province": listing.get("province"),
            "latitude": float(listing.get("latitude")) if listing.get("latitude") is not None and listing.get("latitude") != '' else None,
            "longitude": float(listing.get("longitude")) if listing.get("longitude") is not None and listing.get("longitude") != '' else None,
            
            # Cechy boolean
            "has_balcony": 1 if listing.get("has_balcony") else 0,
            "has_garage": 1 if listing.get("has_garage") else 0,
            "has_garden": 1 if listing.get("has_garden") else 0,
            "has_elevator": 1 if listing.get("has_elevator") else 0,
            "has_basement": 1 if listing.get("has_basement") else 0,
            "has_separate_kitchen": 1 if listing.get("has_separate_kitchen") else 0,
            "has_dishwasher": 1 if listing.get("has_dishwasher") else 0,
            "has_fridge": 1 if listing.get("has_fridge") else 0,
            "has_oven": 1 if listing.get("has_oven") else 0,
            
            # Informacje o budynku
            "year_of_construction": int(listing.get("year_of_construction")) if listing.get("year_of_construction") is not None and listing.get("year_of_construction") != '' else None,
            "building_type": listing.get("building_type"),
            "floor": int(listing.get("floor")) if listing.get("floor") is not None and listing.get("floor") != '' else None,
            "total_floors": int(listing.get("total_floors")) if listing.get("total_floors") is not None and listing.get("total_floors") != '' else None,
            "standard_of_finish": int(listing.get("standard_of_finish")) if listing.get("standard_of_finish") is not None and listing.get("standard_of_finish") != '' else None,
            
            # Ogrzewanie i media
            "heating_type": listing.get("heating_type"),
            "rent_amount": float(listing.get("rent_amount")) if listing.get("rent_amount") is not None and listing.get("rent_amount") != '' else None,
            
            # Odległości - poprawne nazwy kolumn
            "distance_to_city_center": int(listing.get("distance_to_city_center")) if listing.get("distance_to_city_center") is not None and listing.get("distance_to_city_center") != '' else None,
            "distance_to_nearest_lake": int(listing.get("distance_to_nearest_lake")) if listing.get("distance_to_nearest_lake") is not None and listing.get("distance_to_nearest_lake") != '' else None,
            "distance_to_university": int(listing.get("distance_to_university")) if listing.get("distance_to_university") is not None and listing.get("distance_to_university") != '' else None,
            "distance_to_nearest_public_transport": int(listing.get("distance_to_nearest_public_transport")) if listing.get("distance_to_nearest_public_transport") is not None and listing.get("distance_to_nearest_public_transport") != '' else None,
            "distance_to_nearest_school": int(listing.get("distance_to_nearest_school")) if listing.get("distance_to_nearest_school") is not None and listing.get("distance_to_nearest_school") != '' else None,
            "distance_to_nearest_kindergarten": int(listing.get("distance_to_nearest_kindergarten")) if listing.get("distance_to_nearest_kindergarten") is not None and listing.get("distance_to_nearest_kindergarten") != '' else None,
            "distance_to_nearest_supermarket": int(listing.get("distance_to_nearest_supermarket")) if listing.get("distance_to_nearest_supermarket") is not None and listing.get("distance_to_nearest_supermarket") != '' else None,
            
            # JSON fields
            "security_features": listing.get("security_features"),
            "media_features": listing.get("media_features"),
            
            # Metadane
            "source": listing.get("source", "otodom.pl"),
            "source_page": int(listing.get("source_page")) if listing.get("source_page") is not None and listing.get("source_page") != '' else None,
            "source_position": int(listing.get("source_position")) if listing.get("source_position") is not None and listing.get("source_position") != '' else None
        }
        
        # FILTRUJ tylko te kolumny które istnieją w tabeli I MAJĄ WARTOŚCI
        data_to_save = {}
        for column, value in all_possible_data.items():
            # Konwersja list/dict -> JSON string
            if isinstance(value, (list, dict)):
                try:
                    value = json.dumps(value, ensure_ascii=False)
                except Exception:
                    value = str(value)
            if column in available_columns and value is not None and value != "" and str(value) != "None":
                data_to_save[column] = value
        
        # Przygotuj zapytanie INSERT
        if data_to_save:
            columns = ', '.join(data_to_save.keys())
            placeholders = ', '.join(['%s'] * len(data_to_save))
            values = list(data_to_save.values())
            
            query = f"INSERT INTO {table} ({columns}) VALUES ({placeholders})"
            cursor.execute(query, values)
            connection.commit()
            
            logger.info(f"✅ Zapisano: {listing.get('title_raw', 'Brak tytułu')[:30]}...")
            return True
        else:
            logger.warning(f"⚠️ Brak danych do zapisu dla: {listing.get('title_raw', 'Brak tytułu')[:30]}...")
            return False
        
    except Error as e:
        error_msg = str(e)
        if "doesn't exist" in error_msg or "Unknown column" in error_msg:
            logger.warning(f"⚠️ Kolumna nie istnieje w tabeli - pomijam: {error_msg}")
            logger.info("💡 Sprawdź strukturę tabeli w bazie danych")
            # Wyczyść cache kolumn - może się zmienić
            if table in _table_columns_cache:
                del _table_columns_cache[table]
        else:
            logger.error(f"❌ Błąd zapisu do MySQL: {e}")
        return False
    except Exception as e:
        logger.error(f"❌ Nieoczekiwany błąd: {e}")
        return False
    finally:
        # Zawsze zamknij połączenie
        try:
            if cursor:
                cursor.close()
            if connection:
                connection.close()
        except:
            pass

def save_listings_to_mysql(listings: list, table: str = "nieruchomosci", require_complete: bool = True) -> int:
    """
    Zapisuje listę ogłoszeń do MySQL z walidacją kompletności danych
    
    Args:
        listings: Lista słowników z ogłoszeniami
        table: Nazwa tabeli w MySQL  
        require_complete: Czy wymagać kompletnych danych
    
    Returns:
        int: Liczba zapisanych ogłoszeń
    """
    if not listings:
        logger.warning("⚠️ Brak ogłoszeń do zapisu")
        return 0
    
    logger.info(f"💾 Rozpoczynam zapis {len(listings)} ogłoszeń do MySQL...")
    
    saved_count = 0
    incomplete_listings = []
    
    for i, listing in enumerate(listings, 1):
        logger.debug(f"Przetwarzam ogłoszenie {i}/{len(listings)}")
        
        if save_listing(listing, table, require_complete):
            saved_count += 1
        else:
            # Sprawdź czy to duplikat czy niepełne dane
            is_complete, missing_fields = validate_listing_completeness(listing)
            if not is_complete:
                title = listing.get('title_raw', 'Brak tytułu')[:30]
                incomplete_listings.append((title, missing_fields))
    
    # Podsumowanie
    logger.info(f"✅ Zapisano {saved_count} nowych ogłoszeń do MySQL")
    
    if incomplete_listings:
        logger.warning(f"⚠️ Pominięto {len(incomplete_listings)} niepełnych ogłoszeń:")
        for title, missing in incomplete_listings[:5]:  # Pokaż max 5 przykładów
            logger.warning(f"   • {title} (brak: {', '.join(missing)})")
        if len(incomplete_listings) > 5:
            logger.warning(f"   ... i {len(incomplete_listings) - 5} więcej")
    
    return saved_count

def save_listings_to_supabase(listings: list, table: str = "nieruchomosci", require_complete: bool = True) -> int:
    """
    Alias dla kompatybilności wstecznej - teraz używa MySQL
    """
    return save_listings_to_mysql(listings, table, require_complete)

def test_mysql_connection() -> bool:
    """
    Testuje połączenie z bazą danych MySQL
    
    Returns:
        bool: True jeśli połączenie działa
    """
    try:
        connection = get_mysql_connection()
        cursor = connection.cursor()
        
        # Sprawdź czy tabela istnieje
        cursor.execute("SHOW TABLES LIKE 'nieruchomosci'")
        result = cursor.fetchone()
        
        if result:
            logger.info("✅ Połączenie z MySQL działa! Tabela 'nieruchomosci' istnieje.")
        else:
            logger.warning("⚠️ Połączenie działa, ale tabela 'nieruchomosci' nie istnieje")
            logger.info("💡 Uruchom skrypt: sql/create_nieruchomosci_mysql.sql")
        
        cursor.close()
        connection.close()
        return True
        
    except Exception as e:
        logger.error(f"❌ Błąd połączenia z MySQL: {e}")
        show_mysql_setup_info()
        return False

def show_mysql_setup_info():
    """
    Informacja o konfiguracji MySQL
    """
    logger.info("💡 Aby skonfigurować MySQL:")
    logger.info("   1. Zainstaluj MySQL Server")
    logger.info("   2. Utwórz bazę danych 'nieruchomosci_db'")
    logger.info("   3. Skonfiguruj plik .env z danymi połączenia")
    logger.info("   4. Uruchom skrypt: sql/create_nieruchomosci_mysql.sql")
    logger.info("   ")
    logger.info("   Przykład konfiguracji .env:")
    logger.info("   MYSQL_HOST=localhost")
    logger.info("   MYSQL_PORT=3306")
    logger.info("   MYSQL_USER=root")
    logger.info("   MYSQL_PASSWORD=twoje_haslo")
    logger.info("   MYSQL_DATABASE=nieruchomosci_db")

# Aliasy dla kompatybilności wstecznej
get_supabase_client = get_mysql_connection
save_batch_listings = save_listings_to_mysql

if __name__ == "__main__":
    """Test połączenia z MySQL"""
    print("🧪 TEST POŁĄCZENIA Z MYSQL")
    print("=" * 50)
    
    # Test połączenia
    if test_mysql_connection():
        print("✅ MySQL gotowy do użycia!")
        
        # Test kolumn
        columns = get_table_columns("nieruchomosci")
        print(f"📋 Dostępne kolumny ({len(columns)}): {', '.join(columns[:5])}...")
    else:
        print("❌ Problemy z połączeniem MySQL") 