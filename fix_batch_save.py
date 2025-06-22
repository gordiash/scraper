#!/usr/bin/env python3
"""
Fix dla problemu z zapisem batch'a - zmiana require_complete na False
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from mysql_utils import save_listings_to_mysql
from scripts.scraper_main import run_scraping_phase
import logging

# Ustaw logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

def test_batch_save_fix():
    """Testuje zapis batch'a z require_complete=False"""
    
    print("🔧 TEST NAPRAWY PROBLEMU Z ZAPISEM BATCH'A")
    print("=" * 50)
    
    # Test 1: Pobierz próbkę ogłoszeń
    print("\n📥 Test 1: Pobieranie próbki ogłoszeń...")
    listings = run_scraping_phase(max_pages=1, scrape_details=False, batch_size=0)
    
    if not listings:
        print("❌ Brak ogłoszeń do testowania")
        return
    
    print(f"✅ Pobrano {len(listings)} ogłoszeń")
    
    # Test 2: Zapis z require_complete=True (domyślnie)
    print(f"\n💾 Test 2: Zapis z require_complete=True (obecne ustawienie)...")
    saved_strict = save_listings_to_mysql(listings, require_complete=True)
    print(f"✅ Zapisano (tryb restrykcyjny): {saved_strict}/{len(listings)} ogłoszeń")
    
    # Test 3: Zapis z require_complete=False (naprawione)
    print(f"\n💾 Test 3: Zapis z require_complete=False (naprawione ustawienie)...")
    saved_relaxed = save_listings_to_mysql(listings, require_complete=False)
    print(f"✅ Zapisano (tryb tolerancyjny): {saved_relaxed}/{len(listings)} ogłoszeń")
    
    # Podsumowanie
    print(f"\n" + "=" * 50)
    print(f"📊 PODSUMOWANIE TESTU:")
    print(f"Ogłoszeń pobranych: {len(listings)}")
    print(f"Zapisanych (tryb restrykcyjny): {saved_strict} ({saved_strict/len(listings)*100:.1f}%)")
    print(f"Zapisanych (tryb tolerancyjny): {saved_relaxed} ({saved_relaxed/len(listings)*100:.1f}%)")
    
    if saved_relaxed > saved_strict:
        diff = saved_relaxed - saved_strict
        print(f"\n✅ POPRAWA: +{diff} ogłoszeń więcej ({diff/len(listings)*100:.1f}%)")
        print(f"💡 REKOMENDACJA: Zmień require_complete na False w kodzie")
    else:
        print(f"\n⚠️ Brak poprawy - wszystkie dane były już kompletne")

if __name__ == "__main__":
    test_batch_save_fix() 