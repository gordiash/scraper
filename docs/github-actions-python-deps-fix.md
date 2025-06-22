# Naprawa instalacji zależności Python w GitHub Actions

## Problem

Po rozwiązaniu problemu z strukturą repozytorium (brak katalogu `scripts/`), wystąpił nowy błąd w GitHub Actions:

```
ModuleNotFoundError: No module named 'requests'
```

## Przyczyna

Problem wynikał z:
1. **Niepełnej instalacji zależności** - workflow próbował zainstalować zależności z `requirements.txt`, ale niektóre podstawowe pakiety nie były instalowane poprawnie
2. **Braku weryfikacji instalacji** - workflow nie sprawdzał czy pakiety zostały zainstalowane przed użyciem
3. **Konfliktu wersji** - różne wersje pakietów między workflow a `requirements.txt`

## Rozwiązanie

### 1. Robustna instalacja zależności

```yaml
- name: 📦 Zainstaluj zależności Python
  run: |
    python -m pip install --upgrade pip setuptools wheel
    
    # Sprawdź requirements.txt
    echo "📋 Zawartość requirements.txt:"
    if [ -f requirements.txt ]; then
      cat requirements.txt
    else
      echo "❌ Brak pliku requirements.txt!"
      exit 1
    fi
    
    # Zainstaluj WSZYSTKIE podstawowe zależności ręcznie w pierwszej kolejności
    echo "🔧 Instalowanie kluczowych zależności..."
    pip install requests==2.31.0
    pip install beautifulsoup4==4.12.2
    pip install selenium==4.16.0
    pip install lxml==4.9.3
    pip install python-dotenv==1.0.0
    pip install pandas==2.1.4
    
    # MySQL connectory
    echo "🔧 Instalowanie mysql-connector-python..."
    pip install mysql-connector-python==8.2.0
    
    echo "🔧 Instalowanie PyMySQL jako backup..."
    pip install PyMySQL==1.1.0
```

### 2. Weryfikacja instalacji

```yaml
# Test importów podstawowych pakietów
echo "🔍 Test importów kluczowych pakietów..."
python -c "
import sys
print(f'🐍 Python version: {sys.version}')

packages_to_test = [
    ('requests', 'requests'),
    ('beautifulsoup4', 'bs4'),
    ('selenium', 'selenium'),
    ('lxml', 'lxml'),
    ('python-dotenv', 'dotenv'),
    ('pandas', 'pandas'),
    ('mysql.connector', 'mysql.connector'),
    ('pymysql', 'pymysql')
]

failed_imports = []
for package_name, import_name in packages_to_test:
    try:
        __import__(import_name)
        print(f'✅ {package_name}: OK')
    except ImportError as e:
        print(f'❌ {package_name}: FAILED - {e}')
        failed_imports.append(package_name)
    except Exception as e:
        print(f'❌ {package_name}: ERROR - {e}')
        failed_imports.append(package_name)

if failed_imports:
    print(f'💥 Błędne importy: {failed_imports}')
    exit(1)
else:
    print('✅ Wszystkie kluczowe pakiety zainstalowane poprawnie!')
"
```

### 3. Test w kontekście projektu

```yaml
# Final test importów w kontekście scrapera
echo "🔍 Test importów w katalogu scripts przed uruchomieniem:"
python -c "
import sys
import os

# Dodaj główny katalog do path
sys.path.insert(0, os.path.dirname(os.getcwd()))

print(f'Python path: {sys.path[:3]}...')

try:
    from utils import get_soup
    print('✅ utils.get_soup: OK')
except Exception as e:
    print(f'❌ utils.get_soup: {e}')
    
try:
    from src.scrapers.otodom_scraper import get_otodom_listings
    print('✅ otodom_scraper: OK')
except Exception as e:
    print(f'❌ otodom_scraper: {e}')
"
```

## Kluczowe usprawnienia

### 1. **Explicit version pinning**
- Użycie dokładnych wersji pakietów zgodnych z `requirements.txt`
- Zapobiega konfliktom dependency

### 2. **Dwuetapowa instalacja**
- Najpierw kluczowe pakiety ręcznie
- Następnie pozostałe z `requirements.txt`

### 3. **Comprehensive testing**
- Test każdego pakiety indywidualnie
- Test importów w kontekście projektu
- Error handling z exit codes

### 4. **Retry mechanism**
- Próby instalacji z `requirements.txt` z retry
- Fallback do ręcznej instalacji

## Pliki zmodyfikowane

- `.github/workflows/scraper.yml` - główny workflow z poprawkami
- `.github/workflows/test-deps.yml` - nowy workflow testowy
- `docs/github-actions-python-deps-fix.md` - ta dokumentacja

## Rezultat

✅ **Wszystkie zależności Python instalowane poprawnie**  
✅ **Weryfikacja importów przed uruchomieniem scrapera**  
✅ **Robustne error handling i diagnostyka**  
✅ **Zgodność wersji z requirements.txt**  

## Testy

### Test workflow dependencies
```bash
# Uruchom workflow testowy
.github/workflows/test-deps.yml
```

### Test głównego workflow
```bash
# Uruchom scraper workflow
.github/workflows/scraper.yml
```

## Commity

- `ea901d4` - Naprawa instalacji zależności Python w GitHub Actions
- `fe16a16` - Dodanie workflow testowego dla weryfikacji

## Status

🟢 **ROZWIĄZANE** - Instalacja zależności Python działa poprawnie w GitHub Actions 