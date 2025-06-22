#!/usr/bin/env python3
"""
SKRYPT TESTOWY DLA GITHUB ACTIONS
Symuluje lokalne uruchomienie workflow GitHub Actions
"""
import os
import sys
import subprocess
import json
from datetime import datetime

# Dodaj ścieżkę do głównego katalogu
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def print_header():
    """Wyświetl nagłówek skryptu testowego"""
    print("="*80)
    print("🧪 GITHUB ACTIONS - TEST LOKALNY")
    print("="*80)
    print(f"📅 Data: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"🐍 Python: {sys.version}")
    print(f"📁 Katalog: {os.getcwd()}")
    print("="*80)

def check_environment():
    """Sprawdź konfigurację środowiska"""
    print("\n🔍 SPRAWDZANIE ŚRODOWISKA")
    print("-" * 60)
    
    # Sprawdź plik .env
    env_file = ".env"
    if os.path.exists(env_file):
        print("✅ Plik .env istnieje")
        
        # Sprawdź wymagane zmienne
        required_vars = [
            'MYSQL_HOST', 'MYSQL_PORT', 'MYSQL_USER', 
            'MYSQL_PASSWORD', 'MYSQL_DATABASE'
        ]
        
        with open(env_file, 'r') as f:
            env_content = f.read()
            
        missing_vars = []
        for var in required_vars:
            if f"{var}=" not in env_content or f"{var}=" in env_content and env_content.split(f"{var}=")[1].split('\n')[0].strip() == '':
                missing_vars.append(var)
        
        if missing_vars:
            print(f"❌ Brakujące zmienne: {', '.join(missing_vars)}")
            return False
        else:
            print("✅ Wszystkie wymagane zmienne są skonfigurowane")
    else:
        print("❌ Brak pliku .env")
        print("💡 Skopiuj .env_template jako .env i uzupełnij dane")
        return False
    
    return True

def check_dependencies():
    """Sprawdź czy wszystkie zależności są zainstalowane"""
    print("\n📦 SPRAWDZANIE ZALEŻNOŚCI")
    print("-" * 60)
    
    try:
        # Sprawdź requirements.txt
        if not os.path.exists('requirements.txt'):
            print("❌ Brak pliku requirements.txt")
            return False
        
        print("✅ Plik requirements.txt istnieje")
        
        # Sprawdź kluczowe biblioteki
        key_libs = {
            'selenium': 'selenium',
            'beautifulsoup4': 'bs4',
            'mysql-connector-python': 'mysql.connector',
            'requests': 'requests',
            'python-dotenv': 'dotenv'
        }
        
        missing_libs = []
        for lib_name, import_name in key_libs.items():
            try:
                __import__(import_name)
                print(f"✅ {lib_name}")
            except ImportError:
                print(f"❌ {lib_name}")
                missing_libs.append(lib_name)
        
        if missing_libs:
            print(f"\n💡 Zainstaluj brakujące: pip install {' '.join(missing_libs)}")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ Błąd sprawdzania zależności: {e}")
        return False

def test_database_connection():
    """Testuj połączenie z bazą danych"""
    print("\n🔗 TEST POŁĄCZENIA Z BAZĄ")
    print("-" * 60)
    
    try:
        from mysql_utils import get_mysql_connection
        
        conn = get_mysql_connection()
        cursor = conn.cursor()
        
        # Test podstawowy
        cursor.execute("SELECT 1")
        result = cursor.fetchone()
        
        if result and result[0] == 1:
            print("✅ Połączenie z MySQL: OK")
            
            # Sprawdź tabelę nieruchomosci
            cursor.execute("SHOW TABLES LIKE 'nieruchomosci'")
            table_exists = cursor.fetchone() is not None
            
            if table_exists:
                print("✅ Tabela 'nieruchomosci' istnieje")
                
                # Sprawdź liczbę rekordów
                cursor.execute("SELECT COUNT(*) FROM nieruchomosci")
                count = cursor.fetchone()[0]
                print(f"📊 Rekordów w bazie: {count:,}")
                
            else:
                print("⚠️ Tabela 'nieruchomosci' nie istnieje")
                print("💡 Uruchom skrypt tworzenia bazy danych")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Błąd połączenia z bazą: {e}")
        return False

def test_chrome_selenium():
    """Testuj dostępność Chrome i Selenium"""
    print("\n🌐 TEST CHROME/SELENIUM")
    print("-" * 60)
    
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.chrome.service import Service
        from webdriver_manager.chrome import ChromeDriverManager
        
        # Konfiguracja Chrome
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        
        # Sprawdź ChromeDriver
        try:
            service = Service(ChromeDriverManager().install())
            print("✅ ChromeDriver: OK")
        except Exception as e:
            print(f"❌ ChromeDriver: {e}")
            return False
        
        # Test podstawowy Selenium
        try:
            driver = webdriver.Chrome(service=service, options=chrome_options)
            driver.get("https://www.google.com")
            title = driver.title
            driver.quit()
            
            if "Google" in title:
                print("✅ Selenium + Chrome: OK")
                return True
            else:
                print(f"⚠️ Selenium - nieoczekiwany tytuł: {title}")
                return False
                
        except Exception as e:
            print(f"❌ Selenium error: {e}")
            return False
            
    except ImportError as e:
        print(f"❌ Brak bibliotek Selenium: {e}")
        return False

def simulate_scraper_run():
    """Symuluj uruchomienie scrapera"""
    print("\n🚀 SYMULACJA URUCHOMIENIA SCRAPERA")
    print("-" * 60)
    
    try:
        # Przejdź do katalogu scripts
        scripts_dir = os.path.join(os.path.dirname(__file__))
        original_dir = os.getcwd()
        
        if scripts_dir != original_dir:
            os.chdir(scripts_dir)
            print(f"📁 Zmieniono katalog na: {scripts_dir}")
        
        # Przygotuj komendę testową (1 strona, bez geocodingu)
        cmd = [
            sys.executable, 
            "scraper_main.py",
            "--pages", "1",
            "--scraping-only",
            "--no-details"
        ]
        
        print(f"⚡ Uruchamiam: {' '.join(cmd)}")
        print("⏱️ To może potrwać kilka minut...")
        
        # Uruchom scraper
        result = subprocess.run(
            cmd, 
            capture_output=True, 
            text=True,
            timeout=300  # 5 minut timeout
        )
        
        # Wróć do oryginalnego katalogu
        os.chdir(original_dir)
        
        if result.returncode == 0:
            print("✅ Scraper uruchomiony pomyślnie!")
            print("\n📊 OSTATNIE LINIE WYJŚCIA:")
            print("-" * 40)
            output_lines = result.stdout.split('\n')
            for line in output_lines[-10:]:  # Ostatnie 10 linii
                if line.strip():
                    print(line)
            return True
        else:
            print(f"❌ Scraper zakończył się błędem (kod: {result.returncode})")
            print("\n🔍 BŁĘDY:")
            print("-" * 40)
            print(result.stderr)
            return False
            
    except subprocess.TimeoutExpired:
        print("⏰ Timeout - scraper trwał zbyt długo")
        return False
    except Exception as e:
        print(f"❌ Błąd uruchomienia scrapera: {e}")
        return False

def generate_config_template():
    """Wygeneruj szablon konfiguracji dla GitHub Secrets"""
    print("\n📋 SZABLON KONFIGURACJI GITHUB SECRETS")
    print("-" * 60)
    
    secrets_template = {
        "MYSQL_HOST": "s108.cyber-folks.pl",
        "MYSQL_PORT": "3306", 
        "MYSQL_USER": "your_mysql_user",
        "MYSQL_PASSWORD": "your_mysql_password",
        "MYSQL_DATABASE": "your_database_name",
        "WEBHOOK_URL": "https://hooks.slack.com/services/... (opcjonalne)"
    }
    
    print("🔐 Dodaj następujące sekrety w GitHub:")
    print("   Repository → Settings → Secrets and variables → Actions\n")
    
    for key, value in secrets_template.items():
        print(f"   {key:<18} = {value}")
    
    print(f"\n💾 Zapisano szablon do: github_secrets_template.json")
    
    with open("github_secrets_template.json", "w") as f:
        json.dump(secrets_template, f, indent=2)

def main():
    """Główna funkcja testowa"""
    print_header()
    
    tests = [
        ("Środowisko", check_environment),
        ("Zależności", check_dependencies), 
        ("Baza danych", test_database_connection),
        ("Chrome/Selenium", test_chrome_selenium),
        ("Scraper", simulate_scraper_run)
    ]
    
    results = {}
    
    # Uruchom wszystkie testy
    for test_name, test_func in tests:
        print(f"\n{'='*80}")
        try:
            results[test_name] = test_func()
        except Exception as e:
            print(f"❌ Nieoczekiwany błąd w teście '{test_name}': {e}")
            results[test_name] = False
    
    # Podsumowanie
    print(f"\n{'='*80}")
    print("🎯 PODSUMOWANIE TESTÓW")
    print("="*80)
    
    passed = 0
    total = len(tests)
    
    for test_name, success in results.items():
        status = "✅ PASSED" if success else "❌ FAILED"
        print(f"{test_name:<20} {status}")
        if success:
            passed += 1
    
    print(f"\n📊 Wynik: {passed}/{total} testów przeszło pomyślnie")
    
    if passed == total:
        print("🎉 Wszystkie testy przeszły! GitHub Actions powinno działać.")
    else:
        print("⚠️ Niektóre testy nie przeszły. Sprawdź konfigurację przed włączeniem GitHub Actions.")
    
    # Generuj szablon konfiguracji
    generate_config_template()
    
    print("\n📚 Następne kroki:")
    print("1. Skonfiguruj GitHub Secrets (użyj github_secrets_template.json)")
    print("2. Wypchnij zmiany do repozytorium")
    print("3. Sprawdź zakładkę Actions w GitHub")

if __name__ == "__main__":
    main() 