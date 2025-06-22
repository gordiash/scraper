#!/usr/bin/env python3
"""
Szybki test naprawionych funkcji scrapera
"""
from src.scrapers.otodom_scraper import get_otodom_listings

def quick_test():
    print("🔍 SZYBKI TEST NAPRAWIONEGO SCRAPERA")
    print("=" * 50)
    
    # Test z 3 stronami
    listings = get_otodom_listings(
        max_pages=3,
        scrape_details=False,
        batch_size=0,
        enable_geocoding=False
    )
    
    print(f"✅ Pobrano {len(listings)} ogłoszeń z 3 stron")
    
    # Sprawdź strony
    pages = set()
    for listing in listings:
        if 'source_page' in listing:
            pages.add(listing['source_page'])
    
    print(f"📄 Strony: {sorted(pages)}")
    
    if len(listings) >= 50:  # Oczekujemy ~72 ogłoszeń (24x3)
        print("✅ SUCCESS: Scraper działa prawidłowo!")
        return True
    else:
        print("❌ PROBLEM: Nadal za mało ogłoszeń")
        return False

if __name__ == "__main__":
    quick_test() 