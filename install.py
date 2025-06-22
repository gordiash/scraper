#!/usr/bin/env python3
"""
SKRYPT AUTOMATYCZNEJ INSTALACJI SCRAPERA NIERUCHOMOŚCI
Automatycznie konfiguruje bazę danych, środowisko i testuje instalację
"""

import os
import sys
import subprocess
import shutil
import getpass
from pathlib import Path

def print_banner():
    """Wyświetl banner powitalny"""
    print("=" * 60)
    print("🏠 SCRAPER NIERUCHOMOŚCI - INSTALATOR AUTOMATYCZNY")
    print("=" * 60)
    print("Ten skrypt pomoże Ci skonfigurować kompletny system scrapingu.")
    print("Sprawdzimy wymagania, skonfigurujemy bazę danych i przetestujemy instalację.")
    print("")

def check_python_version():
    """Sprawdź wersję Python"""
    print("🐍 Sprawdzanie wersji Python...")
    
    if sys.version_info < (3, 8):
        print("❌ Wymagany Python 3.8+, masz:", sys.version)
        return False
    
    print(f"✅ Python {sys.version.split()[0]} - OK")
    return True

def check_mysql():
    """Sprawdź czy MySQL jest dostępny"""
    print("🗄️ Sprawdzanie MySQL...")
    
    try:
        result = subprocess.run(['mysql', '--version'], 
                              capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            print(f"✅ MySQL dostępny: {result.stdout.strip()}")
            return True
    except:
        pass
    
    print("❌ MySQL nie jest dostępny")
    print("💡 Zainstaluj MySQL Server z https://dev.mysql.com/downloads/")
    return False

def check_chrome():
    """Sprawdź czy Chrome jest zainstalowany"""
    print("🌐 Sprawdzanie Google Chrome...")
    
    chrome_paths = [
        "google-chrome",
        "chrome",
        "chromium",
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
        "C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe"
    ]
    
    for path in chrome_paths:
        try:
            if os.path.exists(path) or shutil.which(path):
                print("✅ Google Chrome znaleziony")
                return True
        except:
            continue
    
    print("❌ Google Chrome nie znaleziony")
    print("💡 Zainstaluj Chrome z https://www.google.com/chrome/")
    return False

def install_python_packages():
    """Zainstaluj pakiety Python"""
    print("📦 Instalowanie pakietów Python...")
    
    try:
        # Sprawdź czy pip jest dostępny
        subprocess.run([sys.executable, '-m', 'pip', '--version'], 
                      check=True, capture_output=True)
        
        # Zainstaluj podstawowe pakiety
        basic_packages = [
            'selenium==4.16.0',
            'beautifulsoup4==4.12.2',
            'mysql-connector-python==8.2.0',
            'python-dotenv==1.0.0',
            'requests==2.31.0',
            'lxml==4.9.3',
            'webdriver-manager==4.0.1'
        ]
        
        print("Instaluję podstawowe pakiety...")
        for package in basic_packages:
            print(f"  📥 {package}")
            subprocess.run([sys.executable, '-m', 'pip', 'install', package], 
                          check=True, capture_output=True)
        
        print("✅ Pakiety Python zainstalowane")
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"❌ Błąd instalacji pakietów: {e}")
        return False

def create_env_file():
    """Utwórz plik .env"""
    print("⚙️ Konfiguracja środowiska...")
    
    if os.path.exists('.env'):
        response = input("Plik .env już istnieje. Nadpisać? (t/n): ")
        if response.lower() != 't':
            print("➡️ Pomijam tworzenie .env")
            return True
    
    # Pobierz dane od użytkownika
    print("Podaj dane połączenia z MySQL:")
    mysql_host = input("Host MySQL [localhost]: ") or "localhost"
    mysql_port = input("Port MySQL [3306]: ") or "3306"
    mysql_user = input("Użytkownik MySQL [root]: ") or "root"
    mysql_password = getpass.getpass("Hasło MySQL: ")
    mysql_database = input("Nazwa bazy danych [nieruchomosci_db]: ") or "nieruchomosci_db"
    
    # Utwórz plik .env
    env_content = f"""# Konfiguracja bazy danych MySQL
MYSQL_HOST={mysql_host}
MYSQL_PORT={mysql_port}
MYSQL_USER={mysql_user}
MYSQL_PASSWORD={mysql_password}
MYSQL_DATABASE={mysql_database}

# Ustawienia scrapera
SCRAPER_DELAY_MIN=2
SCRAPER_DELAY_MAX=5
MAX_RETRIES=3
USE_HEADLESS=true

# Ustawienia logowania
LOG_LEVEL=INFO
LOG_TO_FILE=true
LOG_FILE=scraper.log

# Ustawienia bezpieczeństwa
ENABLE_RATE_LIMITING=true
MAX_PAGES_PER_SESSION=10
ROTATE_USER_AGENTS=true
"""
    
    with open('.env', 'w', encoding='utf-8') as f:
        f.write(env_content)
    
    print("✅ Plik .env utworzony")
    return True

def create_database():
    """Utwórz bazę danych"""
    print("🗄️ Tworzenie bazy danych...")
    
    # Załaduj konfigurację
    try:
        from dotenv import load_dotenv
        load_dotenv()
        
        mysql_host = os.getenv('MYSQL_HOST')
        mysql_user = os.getenv('MYSQL_USER')
        mysql_password = os.getenv('MYSQL_PASSWORD')
        mysql_database = os.getenv('MYSQL_DATABASE')
        
    except ImportError:
        print("❌ Nie można załadować konfiguracji (brak python-dotenv)")
        return False
    
    # Sprawdź czy plik SQL istnieje
    sql_file = Path("sql/create_complete_database.sql")
    if not sql_file.exists():
        print(f"❌ Nie znaleziono pliku: {sql_file}")
        return False
    
    # Wykonaj skrypt SQL
    try:
        print(f"Tworzę bazę danych: {mysql_database}")
        
        # Polecenie MySQL
        cmd = [
            'mysql',
            f'-h{mysql_host}',
            f'-u{mysql_user}',
            f'-p{mysql_password}'
        ]
        
        with open(sql_file, 'r', encoding='utf-8') as f:
            result = subprocess.run(cmd, input=f.read(), text=True, 
                                  capture_output=True, timeout=60)
        
        if result.returncode == 0:
            print("✅ Baza danych utworzona")
            return True
        else:
            print(f"❌ Błąd tworzenia bazy: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        print("❌ Timeout - sprawdź połączenie z MySQL")
        return False
    except Exception as e:
        print(f"❌ Błąd: {e}")
        return False

def test_connection():
    """Przetestuj połączenie z bazą"""
    print("🧪 Testowanie połączenia z bazą danych...")
    
    try:
        # Import i test
        sys.path.append('.')
        from mysql_utils import test_mysql_connection
        
        if test_mysql_connection():
            print("✅ Połączenie z bazą działa")
            return True
        else:
            print("❌ Problemy z połączeniem")
            return False
            
    except ImportError as e:
        print(f"❌ Nie można zaimportować mysql_utils: {e}")
        return False
    except Exception as e:
        print(f"❌ Błąd testowania: {e}")
        return False

def test_scraper():
    """Przetestuj scraper"""
    print("🕷️ Testowanie scrapera...")
    
    try:
        # Test podstawowego scrapingu
        print("Testuję podstawowy scraping (może potrwać 1-2 minuty)...")
        
        result = subprocess.run([
            sys.executable, 
            'src/scrapers/otodom_scraper.py'
        ], capture_output=True, text=True, timeout=180)
        
        if "✅ Pobrano" in result.stdout:
            print("✅ Scraper działa poprawnie")
            return True
        else:
            print("❌ Problemy ze scraperem")
            print("Szczegóły:", result.stderr[-200:] if result.stderr else "Brak błędów")
            return False
            
    except subprocess.TimeoutExpired:
        print("❌ Timeout scrapera - może być problem z internetem")
        return False
    except Exception as e:
        print(f"❌ Błąd testowania scrapera: {e}")
        return False

def create_shortcuts():
    """Utwórz skróty uruchamiania"""
    print("🚀 Tworzenie skrótów...")
    
    shortcuts = {
        'scrape.py': """#!/usr/bin/env python3
\"\"\"Skrót do uruchamiania scrapera\"\"\"
import subprocess
import sys

# Uruchom scraper z domyślnymi ustawieniami
subprocess.run([
    sys.executable, 
    'scripts/scraper_main.py', 
    '--pages', '2'
])
""",
        'test.py': """#!/usr/bin/env python3
\"\"\"Skrót do testowania systemu\"\"\"
import subprocess
import sys

print("🧪 Test połączenia z bazą:")
subprocess.run([sys.executable, '-c', 
               'from mysql_utils import test_mysql_connection; test_mysql_connection()'])

print("\\n🕷️ Test scrapera:")
subprocess.run([sys.executable, 'src/scrapers/otodom_scraper.py'])
"""
    }
    
    for filename, content in shortcuts.items():
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(content)
        
        # Dodaj uprawnienia wykonywania (Linux/Mac)
        try:
            os.chmod(filename, 0o755)
        except:
            pass
    
    print("✅ Skróty utworzone: scrape.py, test.py")

def main():
    """Główna funkcja instalatora"""
    print_banner()
    
    # Sprawdzenia wymagań
    checks = [
        ("Python 3.8+", check_python_version),
        ("MySQL Server", check_mysql),
        ("Google Chrome", check_chrome),
    ]
    
    failed_checks = []
    for name, check_func in checks:
        if not check_func():
            failed_checks.append(name)
    
    if failed_checks:
        print(f"\n❌ Nieudane sprawdzenia: {', '.join(failed_checks)}")
        print("Zainstaluj brakujące komponenty i uruchom ponownie.")
        return False
    
    print("\n✅ Wszystkie wymagania spełnione!")
    
    # Instalacja i konfiguracja
    steps = [
        ("Pakiety Python", install_python_packages),
        ("Konfiguracja .env", create_env_file),
        ("Baza danych", create_database),
        ("Test połączenia", test_connection),
        ("Test scrapera", test_scraper),
        ("Skróty", create_shortcuts),
    ]
    
    print("\n🔧 INSTALACJA:")
    for name, step_func in steps:
        print(f"\n--- {name} ---")
        if not step_func():
            print(f"\n❌ Instalacja zatrzymana na kroku: {name}")
            return False
    
    # Podsumowanie
    print("\n" + "=" * 60)
    print("🎉 INSTALACJA ZAKOŃCZONA POMYŚLNIE!")
    print("=" * 60)
    print("\n📋 NASTĘPNE KROKI:")
    print("1. python scrape.py          # Podstawowy scraping")
    print("2. python test.py            # Test systemu")
    print("3. python scripts/scraper_main.py --pages 5  # Pełny scraping")
    print("\n📚 DOKUMENTACJA:")
    print("- Przeczytaj: INSTRUKCJE_INSTALACJI.md")
    print("- Konfiguracja: .env")
    print("- Logi: scraper.log")
    print("\n🚀 Miłego scrapingu!")
    
    return True

if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⏹️ Instalacja przerwana przez użytkownika")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n💥 Nieoczekiwany błąd: {e}")
        sys.exit(1) 