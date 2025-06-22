#!/usr/bin/env python3
"""
GŁÓWNY SKRIPT SCRAPERA - NOWA STRUKTURA BAZY DANYCH MYSQL
Łączy scraping → parsing adresów → geocoding w jeden proces
Zaktualizowany do nowej struktury z polami market, has_balcony, itp. + MySQL
"""
import logging
import sys
import os
import argparse
from datetime import datetime
from typing import List, Dict

# Dodaj główny katalog do ścieżki
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.scrapers.otodom_scraper import get_otodom_listings, DEFAULT_BASE_URL
from src.parsers.address_parser import process_all_locations
from src.geocoding.geocoder import update_all_coordinates_improved
from mysql_utils import save_listings_to_mysql, get_mysql_connection
from src.deduplication.deduplicator import deduplicate_listings, generate_duplicate_report

# Konfiguracja logowania
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('scraper.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

def print_banner():
    """Wyświetl banner aplikacji"""
    print("="*80)
    print("🏠 SCRAPER NIERUCHOMOŚCI - MYSQL + NOWA STRUKTURA BAZY DANYCH")
    print("="*80)
    print("📅 Data uruchomienia:", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    print("🔗 Źródło: Otodom.pl")
    print("💾 Baza danych: MySQL (nowa struktura)")
    print("🌍 Geocoding: OpenStreetMap Nominatim")
    print("🏷️ Cechy: market, has_balcony, has_garage, has_garden, has_elevator")
    print("="*80)

def get_database_stats() -> Dict[str, int]:
    """Pobierz statystyki z bazy danych MySQL"""
    try:
        connection = get_mysql_connection()
        cursor = connection.cursor()
        
        # Statystyki nieruchomosci
        cursor.execute("SELECT COUNT(*) FROM nieruchomosci")
        total_listings = cursor.fetchone()[0]
        
        # Statystyki z cenami
        cursor.execute("SELECT COUNT(*) FROM nieruchomosci WHERE price IS NOT NULL")
        with_price_count = cursor.fetchone()[0]
        
        # Statystyki z powierzchnią
        cursor.execute("SELECT COUNT(*) FROM nieruchomosci WHERE area IS NOT NULL")
        with_area_count = cursor.fetchone()[0]
        
        # Statystyki geocoded
        cursor.execute("SELECT COUNT(*) FROM nieruchomosci WHERE latitude IS NOT NULL")
        geocoded_count = cursor.fetchone()[0]
        
        # Statystyki rynku
        cursor.execute("SELECT COUNT(*) FROM nieruchomosci WHERE market = 'pierwotny'")
        primary_market_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM nieruchomosci WHERE market = 'wtórny'")
        secondary_market_count = cursor.fetchone()[0]
        
        # Statystyki udogodnień
        cursor.execute("SELECT COUNT(*) FROM nieruchomosci WHERE has_balcony = 1")
        with_balcony_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM nieruchomosci WHERE has_garage = 1")
        with_garage_count = cursor.fetchone()[0]
        
        cursor.close()
        connection.close()
        
        return {
            "total_listings": total_listings,
            "with_price_count": with_price_count,
            "with_area_count": with_area_count,
            "geocoded_count": geocoded_count,
            "primary_market_count": primary_market_count,
            "secondary_market_count": secondary_market_count,
            "with_balcony_count": with_balcony_count,
            "with_garage_count": with_garage_count
        }
        
    except Exception as e:
        logger.error(f"❌ Błąd pobierania statystyk z MySQL: {e}")
        return {
            "total_listings": 0,
            "with_price_count": 0,
            "with_area_count": 0,
            "geocoded_count": 0,
            "primary_market_count": 0,
            "secondary_market_count": 0,
            "with_balcony_count": 0,
            "with_garage_count": 0
        }

def print_stats(title: str, stats: Dict[str, int]):
    """Wyświetl statystyki"""
    print(f"\n📊 {title}")
    print("-" * 60)
    print(f"📋 Łącznie ogłoszeń: {stats['total_listings']:,}")
    print(f"💰 Z cenami: {stats['with_price_count']:,}")
    print(f"📐 Z powierzchnią: {stats['with_area_count']:,}")
    print(f"🌍 Z współrzędnymi: {stats['geocoded_count']:,}")
    
    if stats['total_listings'] > 0:
        price_rate = (stats['with_price_count'] / stats['total_listings']) * 100
        area_rate = (stats['with_area_count'] / stats['total_listings']) * 100
        geocoding_rate = (stats['geocoded_count'] / stats['total_listings']) * 100
        print(f"📈 Pokrycie cen: {price_rate:.1f}%")
        print(f"📈 Pokrycie powierzchni: {area_rate:.1f}%")
        print(f"📈 Pokrycie geocoding: {geocoding_rate:.1f}%")
    
    print(f"\n🏷️ STATYSTYKI RYNKU:")
    print(f"🆕 Rynek pierwotny: {stats['primary_market_count']:,}")
    print(f"🏘️ Rynek wtórny: {stats['secondary_market_count']:,}")
    
    print(f"\n🏠 STATYSTYKI UDOGODNIEŃ:")
    print(f"🏢 Z balkonem: {stats['with_balcony_count']:,}")
    print(f"🚗 Z garażem: {stats['with_garage_count']:,}")

def run_scraping_phase(max_pages: int, scrape_details: bool = True, base_url: str = DEFAULT_BASE_URL, batch_size: int = 0, enable_scraper_geocoding: bool = True) -> List[Dict]:
    """
    Faza 1: Scrapowanie ogłoszeń z Otodom.pl z nową strukturą danych
    
    Args:
        max_pages: Maksymalna liczba stron do scrapowania
        scrape_details: Czy pobierać szczegółowe dane z indywidualnych stron
    
    Returns:
        List[Dict]: Lista pobranych ogłoszeń
    """
    print(f"\n🔍 FAZA 1: SCRAPOWANIE OTODOM.PL {'+ SZCZEGÓŁOWE DANE' if scrape_details else '(TYLKO LISTA)'}")
    print(f"📄 Maksymalna liczba stron: {'WSZYSTKIE' if (max_pages is None or max_pages <= 0) else max_pages}")
    print(f"🔍 Szczegółowy scraping: {'✅ TAK' if scrape_details else '❌ NIE'}")
    print(f"💾 Batch zapis: {'co ' + str(batch_size) + ' ofert' if batch_size else 'po zakończeniu'}")
    print("-" * 60)
    
    try:
        # Funkcja zapisu batcha
        def batch_save(batch: List[Dict]):
            if not batch:
                return
            print(f"\n💾 Zapis batcha ({len(batch)}) do bazy…")
            unique_batch = deduplicate_listings(batch, similarity_threshold=75.0, keep_best_source=True)
            saved = save_listings_to_mysql(unique_batch, require_complete=False)
            print(f"✅ Batch zapisany: {saved}/{len(unique_batch)} rekordów")

        listings = get_otodom_listings(base_url=base_url,
                                       max_pages=max_pages,
                                       scrape_details=scrape_details,
                                       batch_size=batch_size,
                                       batch_callback=batch_save if batch_size else None,
                                       resume=False,
                                       enable_geocoding=enable_scraper_geocoding)
        
        if listings:
            print(f"✅ Pobrano {len(listings)} ogłoszeń z Otodom.pl")
            
            # Statystyki jakości danych
            with_price = len([l for l in listings if l.get('price')])
            with_address = len([l for l in listings if l.get('address_raw')])
            with_area = len([l for l in listings if l.get('area')])
            with_rooms = len([l for l in listings if l.get('rooms')])
            with_city = len([l for l in listings if l.get('city')])
            
            # Statystyki nowych pól
            with_balcony = len([l for l in listings if l.get('has_balcony')])
            with_garage = len([l for l in listings if l.get('has_garage')])
            with_garden = len([l for l in listings if l.get('has_garden')])
            with_elevator = len([l for l in listings if l.get('has_elevator')])
            
            primary_market = len([l for l in listings if l.get('market') == 'pierwotny'])
            secondary_market = len([l for l in listings if l.get('market') == 'wtórny'])
            
            print(f"💰 Z cenami: {with_price}/{len(listings)} ({with_price/len(listings)*100:.1f}%)")
            print(f"📍 Z adresami: {with_address}/{len(listings)} ({with_address/len(listings)*100:.1f}%)")
            print(f"📐 Z powierzchnią: {with_area}/{len(listings)} ({with_area/len(listings)*100:.1f}%)")
            print(f"🚪 Z pokojami: {with_rooms}/{len(listings)} ({with_rooms/len(listings)*100:.1f}%)")
            print(f"🏙️ Z miastem: {with_city}/{len(listings)} ({with_city/len(listings)*100:.1f}%)")
            
            print(f"\n🏷️ STATYSTYKI RYNKU:")
            print(f"🆕 Rynek pierwotny: {primary_market}/{len(listings)} ({primary_market/len(listings)*100:.1f}%)")
            print(f"🏘️ Rynek wtórny: {secondary_market}/{len(listings)} ({secondary_market/len(listings)*100:.1f}%)")
            
            print(f"\n🏠 STATYSTYKI UDOGODNIEŃ:")
            print(f"🏢 Z balkonem: {with_balcony}/{len(listings)} ({with_balcony/len(listings)*100:.1f}%)")
            print(f"🚗 Z garażem: {with_garage}/{len(listings)} ({with_garage/len(listings)*100:.1f}%)")
            print(f"🌿 Z ogrodem: {with_garden}/{len(listings)} ({with_garden/len(listings)*100:.1f}%)")
            print(f"🛗 Z windą: {with_elevator}/{len(listings)} ({with_elevator/len(listings)*100:.1f}%)")
            
            # Dodatkowe statystyki szczegółowych danych (jeśli dostępne)
            if scrape_details:
                with_year = len([l for l in listings if l.get('year_of_construction')])
                with_floor = len([l for l in listings if l.get('floor')])
                with_building_type = len([l for l in listings if l.get('building_type')])
                with_finish = len([l for l in listings if l.get('standard_of_finish')])
                
                print(f"\n🏗️ STATYSTYKI SZCZEGÓŁOWYCH DANYCH:")
                print(f"📅 Z rokiem budowy: {with_year}/{len(listings)} ({with_year/len(listings)*100:.1f}%)")
                print(f"🏢 Z piętrem: {with_floor}/{len(listings)} ({with_floor/len(listings)*100:.1f}%)")
                print(f"🏘️ Z typem budynku: {with_building_type}/{len(listings)} ({with_building_type/len(listings)*100:.1f}%)")
                print(f"🎨 Ze stanem wykończenia: {with_finish}/{len(listings)} ({with_finish/len(listings)*100:.1f}%)")
            
            return listings
        else:
            print("❌ Nie pobrano żadnych ogłoszeń")
            return []
            
    except Exception as e:
        logger.error(f"❌ Błąd w fazie scrapowania: {e}")
        return []

def run_saving_phase(listings: List[Dict]) -> int:
    """
    Faza 2: Zapis ogłoszeń do bazy danych MySQL (nowa struktura)
    
    Args:
        listings: Lista ogłoszeń do zapisu
    
    Returns:
        int: Liczba zapisanych ogłoszeń
    """
    print(f"\n💾 FAZA 2: ZAPIS DO BAZY DANYCH MYSQL (NOWA STRUKTURA)")
    print(f"📋 Ogłoszeń do zapisu: {len(listings)}")
    print("-" * 60)
    
    try:
        saved_count = save_listings_to_mysql(listings, require_complete=False)
        
        if saved_count > 0:
            print(f"✅ Zapisano {saved_count} nowych ogłoszeń do MySQL")
            
            # Statystyki zapisu
            duplicate_count = len(listings) - saved_count
            if duplicate_count > 0:
                print(f"⏭️ Pominięto {duplicate_count} duplikatów")
                
            success_rate = (saved_count / len(listings)) * 100
            print(f"📈 Skuteczność zapisu: {success_rate:.1f}%")
        else:
            print("⚠️ Nie zapisano żadnych nowych ogłoszeń (wszystkie to duplikaty)")
            
        return saved_count
        
    except Exception as e:
        logger.error(f"❌ Błąd w fazie zapisu do MySQL: {e}")
        return 0

def run_geocoding_phase(max_addresses: int) -> bool:
    """
    Faza 3: Geocoding - uzupełnianie współrzędnych
    
    Args:
        max_addresses: Maksymalna liczba adresów do geocodingu
    
    Returns:
        bool: True jeśli geocoding się udał
    """
    print(f"\n🌍 FAZA 3: GEOCODING WSPÓŁRZĘDNYCH")
    print(f"📍 Maksymalna liczba adresów: {max_addresses}")
    print("-" * 60)
    
    try:
        # Zoptymalizowane parametry
        optimal_batch_size = min(100, max_addresses) if max_addresses else 100
        
        print(f"⚡ Parametry optymalizacji:")
        print(f"   • Batch size: {optimal_batch_size}")
        print(f"   • Opóźnienie: 1.0s między requestami")
        print(f"   • Max retries: 2")
        
        # Uruchom geocoding (funkcja wyświetla własne statystyki)
        update_all_coordinates_improved(max_addresses=max_addresses)
        print("✅ Geocoding zakończony")
        return True
        
    except Exception as e:
        logger.error(f"❌ Błąd w fazie geocodingu: {e}")
        return False

def run_complete_pipeline(max_pages: int = 0, max_geocoding_addresses: int = 100, scrape_details: bool = True, base_url: str = DEFAULT_BASE_URL, batch_size: int = 0, enable_scraper_geocoding: bool = True) -> bool:
    """
    Uruchamia kompletny pipeline: scraping → zapis → geocoding
    
    Args:
        max_pages: Maksymalna liczba stron do scrapowania
        max_geocoding_addresses: Maksymalna liczba adresów do geocodingu
        scrape_details: Czy pobierać szczegółowe dane z indywidualnych stron
    
    Returns:
        bool: True jeśli wszystkie fazy się udały
    """
    print_banner()
    
    # Statystyki początkowe
    initial_stats = get_database_stats()
    print_stats("STATYSTYKI POCZĄTKOWE", initial_stats)
    
    # FAZA 1: Scrapowanie
    listings = run_scraping_phase(max_pages, scrape_details, base_url=base_url, batch_size=batch_size, enable_scraper_geocoding=enable_scraper_geocoding)
    if not listings:
        print("❌ Brak danych do dalszego przetwarzania")
        return False

    # FAZA 2: Deduplikacja
    print(f"\n✨ FAZA 2: DEDUPLIKACJA OGŁOSZEŃ")
    print(f"📋 Ogłoszeń przed deduplikacją: {len(listings)}")
    print("-" * 60)
    
    unique_listings = deduplicate_listings(listings, similarity_threshold=75.0, keep_best_source=True)
    duplicates_found = len(listings) - len(unique_listings)
    
    print(f"✅ Ogłoszeń po deduplikacji: {len(unique_listings)}")
    print(f"⏭️ Usunięto duplikatów: {duplicates_found}")
    
    if duplicates_found > 0:
        # Opcjonalnie można by wygenerować raport tutaj, jeśli potrzebny jest szczegółowy log
        pass # generate_duplicate_report(duplicates_list) jeśli lista duplikatów jest zwracana

    # FAZA 3: Zapis do bazy
    saved_count = run_saving_phase(unique_listings)
    
    # FAZA 4: Geocoding (tylko jeśli zapisano nowe dane)
    geocoding_success = True
    if saved_count > 0:
        geocoding_success = run_geocoding_phase(max_geocoding_addresses)
    else:
        print(f"\n🌍 FAZA 3: GEOCODING POMINIĘTY")
        print("💡 Brak nowych danych do geocodingu")
    
    # Statystyki końcowe
    final_stats = get_database_stats()
    print_stats("STATYSTYKI KOŃCOWE", final_stats)
    
    # Podsumowanie
    print(f"\n🎉 PODSUMOWANIE PIPELINE:")
    print("="*60)
    print(f"📊 Pobrano ogłoszeń: {len(listings)}")
    print(f"💾 Zapisano nowych: {saved_count}")
    print(f"🌍 Geocoding: {'✅ OK' if geocoding_success else '❌ BŁĄD'}")
    
    # Przyrost danych
    new_listings = final_stats['total_listings'] - initial_stats['total_listings']
    if new_listings > 0:
        print(f"📈 Przyrost w bazie: +{new_listings} ogłoszeń")
    
    return True

def main():
    """Główna funkcja"""
    parser = argparse.ArgumentParser(description='Scraper nieruchomości - MySQL + nowa struktura bazy')
    parser.add_argument('--pages', type=int, default=0, help='Maksymalna liczba stron do scrapowania (0 = wszystkie)')
    parser.add_argument('--geocoding', type=int, default=100, help='Maksymalna liczba adresów do geocodingu')
    parser.add_argument('--scraping-only', action='store_true', help='Tylko scrapowanie bez geocodingu')
    parser.add_argument('--no-details', action='store_true', help='Pomiń szczegółowy scraping (tylko lista)')
    parser.add_argument('--no-scraper-geocoding', action='store_true', help='Wyłącz geocoding w scrapperze (użyj osobny proces)')
    parser.add_argument('--url', type=str, help='Niestandardowy URL wyników Otodom (opcjonalnie)')
    parser.add_argument('--batch-size', type=int, default=100, help='Rozmiar batcha do zapisu (0 = zapis na końcu)')
    
    args = parser.parse_args()
    
    # Określ czy scraping szczegółów
    scrape_details = not args.no_details
    
    # Określ czy geocoding w scrapperze
    enable_scraper_geocoding = not args.no_scraper_geocoding
    
    try:
        if args.scraping_only:
            # Tylko scrapowanie i zapis
            print_banner()
            initial_stats = get_database_stats()
            print_stats("STATYSTYKI POCZĄTKOWE", initial_stats)
            
            base_url = args.url or DEFAULT_BASE_URL
            batch_size = args.batch_size
            listings = run_scraping_phase(args.pages, scrape_details, base_url=base_url, batch_size=batch_size)
            if listings:
                saved_count = run_saving_phase(listings)
                print(f"\n🎉 ZAKOŃCZONO: Pobrano {len(listings)}, zapisano {saved_count}")
            else:
                print("❌ Nie pobrano żadnych danych")
        else:
            # Kompletny pipeline
            success = run_complete_pipeline(args.pages, args.geocoding, scrape_details, args.url or DEFAULT_BASE_URL, batch_size=args.batch_size, enable_scraper_geocoding=enable_scraper_geocoding)
            if success:
                print(f"\n🎉 PIPELINE ZAKOŃCZONY POMYŚLNIE!")
            else:
                print(f"\n❌ PIPELINE ZAKOŃCZONY Z BŁĘDAMI")
                
    except KeyboardInterrupt:
        print(f"\n⚠️ Przerwano przez użytkownika")
    except Exception as e:
        logger.error(f"❌ Błąd głównego procesu: {e}")
        print(f"\n❌ Błąd: {e}")

if __name__ == "__main__":
    main() 