# GitHub Actions - Poprawki instalacji zależności

## Problem

W GitHub Actions wystąpiły błędy:

1. **Brak modułu `fake_useragent`**:
   ```
   ❌ utils.get_soup: No module named 'fake_useragent'
   ❌ otodom_scraper: No module named 'fake_useragent'
   ```

2. **Problem z importem modułu `src`**:
   ```
   ❌ otodom_scraper: FAILED - No module named 'src'
   ```

## Rozwiązanie

### 1. Dodano `fake-useragent` do kluczowych pakietów

```yaml
# Zainstaluj WSZYSTKIE podstawowe zależności ręcznie w pierwszej kolejności
echo "🔧 Instalowanie kluczowych zależności..."
pip install requests==2.31.0
pip install beautifulsoup4==4.12.2
pip install selenium==4.16.0
pip install lxml==4.9.3
pip install python-dotenv==1.0.0
pip install pandas==2.1.4
pip install fake-useragent==1.4.0  # ← DODANE
```

### 2. Rozszerzono weryfikację importów

```yaml
packages_to_test = [
    ('requests', 'requests'),
    ('beautifulsoup4', 'bs4'),
    ('selenium', 'selenium'),
    ('lxml', 'lxml'),
    ('python-dotenv', 'dotenv'),
    ('pandas', 'pandas'),
    ('fake-useragent', 'fake_useragent'),  # ← DODANE
    ('mysql.connector', 'mysql.connector'),
    ('pymysql', 'pymysql')
]
```

### 3. Poprawiono importy modułów projektowych

```yaml
# Final test importów w kontekście scrapera
echo "🔍 Test importów w katalogu scripts przed uruchomieniem:"
python -c "
# Dodaj główny katalog do path
main_dir = os.path.dirname(os.getcwd())
sys.path.insert(0, main_dir)

# Test projektowych importów
try:
    import utils
    from utils import get_soup
    print('✅ utils.get_soup: OK')
except Exception as e:
    print(f'❌ utils.get_soup: {e}')
    
try:
    import src
    from src.scrapers import otodom_scraper
    from src.scrapers.otodom_scraper import get_otodom_listings
    print('✅ otodom_scraper.get_otodom_listings: OK')
except Exception as e:
    print(f'❌ otodom_scraper: {e}')

# Final test scrapera przed uruchomieniem
try:
    from src.scrapers.otodom_scraper import get_otodom_listings, DEFAULT_BASE_URL
    print('✅ otodom_scraper: READY')
except Exception as e:
    print(f'❌ otodom_scraper: FAILED - {e}')
    exit(1)
"
```

## Rezultat

✅ **Dodano `fake-useragent==1.4.0` do instalacji**  
✅ **Rozszerzono weryfikację importów**  
✅ **Poprawiono ścieżki Python dla modułów projektowych**  
✅ **Dodano final test przed uruchomieniem scrapera**  

## Commit

- `0ccdedc` - Napraw importy: dodaj fake-useragent i rozszerz weryfikację modułów src

## Status

🟡 **W TRAKCIE TESTOWANIA** - Poprawki wysłane do GitHub, oczekujemy na weryfikację w GitHub Actions

---

**Następny krok**: Uruchomić workflow i sprawdzić czy wszystkie importy działają poprawnie. 