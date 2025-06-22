# 🏠 SCRAPER NIERUCHOMOŚCI - OTODOM.PL (MySQL)

Zaawansowany system scrapowania ogłoszeń mieszkaniowych z Otodom.pl z pełnym szczegółowym parsowaniem każdego ogłoszenia i integracją z bazą danych MySQL.

## ✨ Kluczowe Funkcjonalności V2.0:

- **🎯 Pełny Scraping Otodom.pl:** Automatyczne wchodzenie w każde ogłoszenie dla maksymalnego pobrania danych
- **🔍 Zaawansowane Parsowanie Adresów:** Automatyczne rozdzielanie na ulicę, dzielnicę, miasto i województwo
- **📋 ID Ogłoszeń:** Pobieranie unikalnych ID z sekcji opisu każdego ogłoszenia
- **🏢 Cechy Nieruchomości:** Wykrywanie balkonu (63.5%), garażu (41.9%), windy (37.8%), ogrodu (6.8%)
- **🏗️ Szczegóły Budynku:** Rok budowy, piętro, typ budynku, standard wykończenia, ogrzewanie
- **🔧 Wyposażenie AGD:** Zmywarka, lodówka, piekarnik i inne udogodnienia
- **🛡️ Zabezpieczenia:** Drzwi antywłamaniowe, domofon, monitoring
- **🌐 Media:** Internet, TV kablowa, telefon
- **🗄️ Kompletna Baza MySQL:** Z indeksami, constraintami, funkcjami i procedurami

## 🚀 SZYBKA INSTALACJA

### Opcja A - Automatyczna (zalecana):
```bash
python install.py
```

### Opcja B - Manualna:
```bash
# 1. Zainstaluj zależności
pip install -r requirements.txt

# 2. Skonfiguruj środowisko
cp .env_template .env
# Edytuj .env z danymi MySQL

# 3. Utwórz bazę danych
mysql -u root -p < sql/create_complete_database.sql

# 4. Przetestuj instalację
python src/scrapers/otodom_scraper.py
```

## 📊 UŻYTKOWANIE

### Podstawowe komendy:
```bash
# Scraping 2 stron z pełnymi szczegółami (domyślnie)
python scripts/scraper_main.py --pages 2

# Szybki scraping bez szczegółów
python scripts/scraper_main.py --pages 3 --no-details

# Tylko scraping bez geocodingu
python scripts/scraper_main.py --pages 5 --scraping-only
```

### Zarządzanie bazą:
```bash
# Statystyki bazy
mysql -u root -p nieruchomosci_db -e "CALL GetDatabaseStats();"

# Sprawdź jakość danych
mysql -u root -p nieruchomosci_db -e "SELECT * FROM vw_nieruchomosci_stats LIMIT 10;"
```

## 🎯 JAKOŚĆ DANYCH

**PRZED modyfikacją (tylko listing):**
- Balkon: 0/74 (0.0%) ❌
- Garaż: 0/74 (0.0%) ❌  
- Ogród: 0/74 (0.0%) ❌
- Winda: 0/74 (0.0%) ❌

**PO modyfikacji (szczegółowy scraping):**
- ✅ **Balkon: 47/74 (63.5%)**
- ✅ **Garaż: 31/74 (41.9%)**
- ✅ **Ogród: 5/74 (6.8%)**
- ✅ **Winda: 28/74 (37.8%)**
- ✅ **ID ogłoszenia: 73/74 (98.6%)**
- ✅ **Ulica: 61/74 (82.4%)**
- ✅ **Miasto: 74/74 (100.0%)**
- ✅ **Województwo: 74/74 (100.0%)**

## 🤖 AUTOMATYZACJA - GITHUB ACTIONS

Scraper może być uruchamiany automatycznie co 6 godzin przy użyciu GitHub Actions:

### 🔧 Konfiguracja
1. **Skonfiguruj sekrety w GitHub**: `Settings → Secrets and variables → Actions`
   - `MYSQL_HOST`, `MYSQL_PORT`, `MYSQL_USER`, `MYSQL_PASSWORD`, `MYSQL_DATABASE`
   - `WEBHOOK_URL` (opcjonalne - dla powiadomień Slack/Discord)

2. **Test lokalny** przed włączeniem GitHub Actions:
   ```bash
   python scripts/test_github_actions.py
   ```

3. **Uruchomienie ręczne**: Zakładka `Actions` → `🏠 Scraper Nieruchomości` → `Run workflow`

### 📊 Funkcjonalności workflow
- ✅ Automatyczne uruchamianie co 6 godzin (00:00, 06:00, 12:00, 18:00 UTC)
- ✅ Ręczne uruchamianie z konfigurowalnymi parametrami
- ✅ Instalacja Chrome/ChromeDriver dla Selenium
- ✅ Test połączenia z bazą danych przed scrapingiem
- ✅ Powiadomienia o statusie (Slack/Discord)
- ✅ Artefakty z logami (przechowywane 7 dni)
- ✅ Statystyki końcowe i podsumowania

Szczegóły konfiguracji: **[docs/github-actions-setup.md](docs/github-actions-setup.md)**

## 📚 DOKUMENTACJA

- **[INSTRUKCJE_INSTALACJI.md](INSTRUKCJE_INSTALACJI.md)** - Kompletny przewodnik instalacji
- **[sql/create_complete_database.sql](sql/create_complete_database.sql)** - Skrypt bazy danych
- **[.env_template](.env_template)** - Szablon konfiguracji
- **[docs/github-actions-setup.md](docs/github-actions-setup.md)** - Konfiguracja GitHub Actions

## 📊 Podsumowanie Migracji

Szczegółowe informacje na temat migracji z Supabase na MySQL, kluczowych zmian i zalet nowej konfiguracji znajdziesz w:

[MIGRACJA_MYSQL_PODSUMOWANIE.md](MIGRACJA_MYSQL_PODSUMOWANIE.md)

## 🔧 Struktura Projektu

```
scraper/
├── scripts/               # Główne skrypty do uruchamiania pipeline
├── src/                   # Kod źródłowy (scrapery, parsery, geocoding)
│   ├── scrapers/          # Moduły do scrapowania danych z portali
│   ├── parsers/           # Moduły do parsowania adresów
│   └── geocoding/         # Moduły do geocodingu
├── sql/                   # Skrypty SQL do tworzenia/zarządzania bazą MySQL
├── tests/                 # Testy jednostkowe i integracyjne
├── docs/                  # Dodatkowa dokumentacja
├── legacy/                # Starsze, nieużywane już wersje kodu/plików
├── mysql_utils.py         # Moduł do obsługi bazy danych MySQL
├── env_example.txt        # Przykładowy plik konfiguracyjny .env
├── requirements.txt       # Lista zależności Python
├── INSTRUKCJE_URUCHOMIENIA_MYSQL.md # **Główna dokumentacja uruchomienia**
├── MIGRACJA_MYSQL_PODSUMOWANIE.md # **Podsumowanie migracji z Supabase na MySQL**
└── README.md              # Ten plik
```

## 🔧 Najnowsze poprawki geocodingu

### Problem z fuzzywuzzy

**Błąd:** Scraper wyrzucał błąd `ImportError: Biblioteka fuzzywuzzy nie jest zainstalowana` i przerywał działanie.

**Rozwiązanie:**
1. ✅ **Poprawiono deduplicator** (`src/deduplication/deduplicator.py`):
   - Dodano alternatywne funkcje porównania tekstów gdy `fuzzywuzzy` nie jest dostępne
   - Zaimplementowano `simple_ratio()` i `levenshtein_ratio()` jako zamienniki
   - Deduplicator teraz działa niezależnie od dostępności biblioteki

2. ✅ **Poprawiono instalację w GitHub Actions**:
   - Dodano jawną instalację `fuzzywuzzy==0.18.0` i `python-Levenshtein==0.23.0`
   - Dodano testy importów dla bibliotek tekstowych

### Problem z optimized geocoder

**Błąd:** Optimized geocoder używał nieistniejącego `supabase_utils.py`.

**Rozwiązanie:**
1. ✅ **Przepisano optimized geocoder** na MySQL:
   - Zmieniono importy z `supabase_utils` na `mysql_utils`
   - Przepisano funkcje bazy danych na SQL zamiast Supabase API
   - Poprawiono nazwy kolumn (`street` zamiast `street_name`)

2. ✅ **Stworzono niezawodny geocoder**:
   - Dodano funkcję `main_geocoding_process()` w `src/geocoding/geocoder.py`
   - Prosty, stabilny proces geocodingu bez async/await
   - Lepsze raportowanie błędów i statystyk

### Aktualne działanie geocodingu

**Scraper główny:** Używa `main_geocoding_process()` - prosty i niezawodny
**Test geocodera:** `python src/geocoding/geocoder.py --test`
**Ręczny geocoding:** `python src/geocoding/geocoder.py --run --max-addresses 100`

### Biblioteki wymagane dla geocodingu
- `requests` - zapytania HTTP do Nominatim OSM
- `mysql-connector-python` - połączenie z bazą MySQL  
- `fuzzywuzzy` + `python-Levenshtein` - porównanie tekstów (opcjonalne)

Wszystkie biblioteki są automatycznie instalowane w GitHub Actions.

---