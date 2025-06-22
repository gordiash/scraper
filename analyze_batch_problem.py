#!/usr/bin/env python3
"""
Skrypt diagnostyczny - Analiza problemu z zapisem batch'a
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from mysql_utils import REQUIRED_FIELDS, validate_listing_completeness
import logging

# Ustaw logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

def analyze_batch_problem():
    """Analizuje problem z zapisem batch'a"""
    
    print("🔍 ANALIZA PROBLEMU Z ZAPISEM BATCH'A")
    print("=" * 50)
    
    # Sprawdź czy imports działają
    try:
        from src.scrapers.otodom_scraper import get_otodom_listings
        print("✅ Import otodom_scraper OK")
    except Exception as e:
        print(f"❌ Błąd importu otodom_scraper: {e}")
        return
    
    # Pobierz próbkę ogłoszeń (1 strona, bez szczegółów dla szybkości)
    print("\n📥 Pobieranie próbki ogłoszeń...")
    try:
        # Spróbuj z verbose logging
        logging.getLogger().setLevel(logging.DEBUG)
        sample_listings = get_otodom_listings(max_pages=1, scrape_details=False)
        print(f"✅ Pobrano {len(sample_listings)} ogłoszeń")
    except Exception as e:
        print(f"❌ Błąd pobierania: {e}")
        import traceback
        traceback.print_exc()
        return
    
    if not sample_listings:
        print("❌ Brak ogłoszeń do analizy")
        print("💡 Możliwe przyczyny:")
        print("   1. Problem z połączeniem internetowym")
        print("   2. Zmiana struktury strony Otodom.pl")
        print("   3. Blokada przez anti-bot")
        print("   4. Nieprawidłowy URL bazowy")
        
        # Sprawdź URL bazowy
        from src.scrapers.otodom_scraper import DEFAULT_BASE_URL
        print(f"\n🔗 Domyślny URL: {DEFAULT_BASE_URL}")
        
        return
    
    print(f"\n📋 Wymagane pola do zapisu: {REQUIRED_FIELDS}")
    print("-" * 50)
    
    # Sprawdź kompletność każdego ogłoszenia
    complete_count = 0
    incomplete_count = 0
    missing_fields_stats = {}
    
    print("\n🔍 Analiza kompletności danych:")
    
    for i, listing in enumerate(sample_listings, 1):
        is_complete, missing_fields = validate_listing_completeness(listing)
        
        if is_complete:
            complete_count += 1
            print(f"✅ #{i:2d}: {listing.get('title_raw', 'Brak tytułu')[:40]}...")
        else:
            incomplete_count += 1
            title = listing.get('title_raw', 'Brak tytułu')[:40]
            print(f"❌ #{i:2d}: {title}... (brak: {', '.join(missing_fields)})")
            
            # Zlicz brakujące pola
            for field in missing_fields:
                missing_fields_stats[field] = missing_fields_stats.get(field, 0) + 1
    
    # Podsumowanie
    print("\n" + "=" * 50)
    print("📊 PODSUMOWANIE:")
    print(f"✅ Kompletne ogłoszenia: {complete_count}/{len(sample_listings)} ({complete_count/len(sample_listings)*100:.1f}%)")
    print(f"❌ Niepełne ogłoszenia: {incomplete_count}/{len(sample_listings)} ({incomplete_count/len(sample_listings)*100:.1f}%)")
    
    if missing_fields_stats:
        print(f"\n🔍 Najczęściej brakujące pola:")
        for field, count in sorted(missing_fields_stats.items(), key=lambda x: x[1], reverse=True):
            print(f"   • {field}: {count} razy ({count/len(sample_listings)*100:.1f}%)")
    
    # Sprawdź przykładowe dane
    print(f"\n📋 Przykładowe dane z pierwszego ogłoszenia:")
    if sample_listings:
        first_listing = sample_listings[0]
        for field in REQUIRED_FIELDS:
            value = first_listing.get(field)
            status = "✅" if value is not None and str(value) != "" and str(value).lower() != "none" else "❌"
            print(f"   {status} {field}: {repr(value)}")
        
        # Pokaż wszystkie dostępne pola
        print(f"\n📋 Wszystkie dostępne pola w pierwszym ogłoszeniu:")
        for key, value in first_listing.items():
            print(f"   • {key}: {repr(value)}")
    
    # Rekomendacje
    print(f"\n💡 REKOMENDACJE:")
    if complete_count == 0:
        print("❌ PROBLEM: Żadne ogłoszenie nie ma kompletnych danych!")
        print("🔧 ROZWIĄZANIA:")
        print("   1. Ustaw require_complete=False w save_listings_to_mysql()")
        print("   2. Popraw parsowanie najczęściej brakujących pól")
        print("   3. Sprawdź czy struktura strony Otodom.pl się zmieniła")
    else:
        print(f"1. Sprawdź parsowanie danych - {incomplete_count} z {len(sample_listings)} ogłoszeń ma niepełne dane")
        
        if missing_fields_stats:
            most_missing = max(missing_fields_stats.items(), key=lambda x: x[1])
            print(f"2. Najczęściej brakuje: '{most_missing[0]}' ({most_missing[1]} razy)")
            
        print(f"3. Rozważ uruchomienie z require_complete=False aby zapisać częściowe dane")
        print(f"4. Lub popraw parsowanie dla najczęściej brakujących pól")

if __name__ == "__main__":
    analyze_batch_problem() 