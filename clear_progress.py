#!/usr/bin/env python3
"""
Skrypt do usunięcia zapamiętanych postępów scrapera
"""
import os
from pathlib import Path

def clear_scraper_progress():
    """Usuwa plik z zapamiętanymi postępami scrapera"""
    
    print("🧹 USUWANIE ZAPAMIĘTANYCH POSTĘPÓW SCRAPERA")
    print("=" * 50)
    
    # Plik progress w katalogu domowym użytkownika
    progress_file = Path.home() / ".otodom_progress.json"
    
    try:
        if progress_file.exists():
            progress_file.unlink()
            print(f"✅ Usunięto plik: {progress_file}")
        else:
            print(f"⚠️ Plik nie istnieje: {progress_file}")
            
        print("\n📝 Zmiany w kodzie:")
        print("✅ resume=False ustawione jako domyślne w get_otodom_listings()")
        print("✅ resume=False ustawione w scraper_main.py")
        print("\n🎯 EFEKT:")
        print("• Scraper zawsze zaczyna od początku")
        print("• Nie zapisuje checkpointów")
        print("• Nie pamięta gdzie skończył")
        
    except Exception as e:
        print(f"❌ Błąd usuwania pliku: {e}")

if __name__ == "__main__":
    clear_scraper_progress() 