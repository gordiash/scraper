# 🚀 GitHub Actions - Konfiguracja Scrapera

## 📋 Przegląd

Ten projekt zawiera automatyczny workflow GitHub Actions do uruchamiania scrapera nieruchomości w regularnych odstępach czasu.

## ⚙️ Konfiguracja Repository Secrets

Aby GitHub Actions działały poprawnie, musisz skonfigurować następujące sekrety w swoim repozytorium:

### 🔐 Wymagane sekrety MySQL
Idź do `Settings > Secrets and variables > Actions` i dodaj:

- `MYSQL_HOST` - adres serwera MySQL (np. `s108.cyber-folks.pl`)
- `MYSQL_PORT` - port MySQL (np. `3306`)  
- `MYSQL_USER` - nazwa użytkownika MySQL
- `MYSQL_PASSWORD` - hasło do bazy MySQL
- `MYSQL_DATABASE` - nazwa bazy danych

### 📢 Opcjonalne powiadomienia
- `WEBHOOK_URL` - URL webhook'a Slack/Discord do powiadomień (opcjonalne)
  - Jeśli nie ustawione, powiadomienia będą pomijane

## 🕒 Harmonogram uruchamiania

### Automatyczne uruchamianie
Workflow uruchamia się automatycznie **co 6 godzin**:
- 00:00 UTC
- 06:00 UTC  
- 12:00 UTC
- 18:00 UTC

### Ręczne uruchamianie
Możesz uruchomić scraper ręcznie z następującymi parametrami:
- **max_pages**: Maksymalna liczba stron (domyślnie: 5)
- **batch_size**: Rozmiar batcha zapisu (domyślnie: 100)
- **scraping_only**: Tylko scrapowanie bez geocodingu (domyślnie: false)
- **no_details**: Pomiń szczegółowy scraping (domyślnie: false)

## 🔧 Co robi workflow

1. **🐍 Przygotowanie środowiska**
   - Instaluje Python 3.11
   - Instaluje Chrome i ChromeDriver dla Selenium
   - Instaluje wszystkie zależności z `requirements.txt`

2. **🔧 Konfiguracja**
   - Tworzy plik `.env` z sekretami
   - Testuje połączenie z bazą MySQL

3. **🔍 Scraping**
   - Uruchamia scraper z odpowiednimi parametrami
   - Zapisuje dane do bazy MySQL
   - Wykonuje geocoding (jeśli włączony)

4. **📊 Raportowanie**
   - Wyświetla statystyki końcowe
   - Zapisuje logi jako artefakty
   - Wysyła powiadomienia o statusie (jeśli skonfigurowane)

## 📁 Artefakty

Po każdym uruchomieniu workflow zapisuje:
- Logi scrapera (`scraper-logs-{run_number}`)
- Przechowywane przez 7 dni

## 🚨 Powiadomienia

Jeśli skonfigurujesz `WEBHOOK_URL`, otrzymasz powiadomienia:

### ✅ Sukces
```
✅ Scraper nieruchomości: Zakończony pomyślnie
📊 Łącznie: 1,234 ogłoszeń
🆕 Dodane dzisiaj: 45
⏰ Ostatnia godzina: 12
💰 Z cenami: 1,200
🌍 Geocoded: 980
🔗 Szczegóły: [link do workflow]
```

### ❌ Błąd
```
❌ Scraper nieruchomości: Błąd podczas wykonania
🔗 Link: [link do workflow]
```

## 🧪 Testowanie przed uruchomieniem

### Test lokalny
```bash
python scripts/test_github_actions.py
```

### Test połączenia w GitHub
1. Idź do zakładki `Actions` → `🧪 Test Połączenia z Bazą`
2. Kliknij `Run workflow`
3. Ten test zajmuje 2-3 minuty i sprawdza tylko połączenie z bazą

## 🔍 Monitorowanie

### Sprawdzanie statusu workflow
1. Idź do zakładki `Actions` w swoim repozytorium
2. Wybierz workflow `🏠 Scraper Nieruchomości`
3. Zobacz historię uruchomień i ich statusy

### Pobieranie logów
1. Wejdź w konkretne uruchomienie workflow
2. Pobierz artefakt `scraper-logs-{number}`
3. Rozpakuj i przejrzyj logi

## ⚡ Przykłady uruchomienia

### Szybki test (5 stron, bez geocodingu)
```yaml
max_pages: "5"
scraping_only: true
```

### Pełny scraping (20 stron z geocodingiem)  
```yaml
max_pages: "20"
batch_size: "50"
scraping_only: false
```

### Tylko lista bez szczegółów
```yaml
max_pages: "10"
no_details: true
batch_size: "200"
```

## 🛠️ Rozwiązywanie problemów

### Błąd połączenia z bazą
- Sprawdź czy sekrety MySQL są poprawnie skonfigurowane
- Zweryfikuj czy serwer MySQL jest dostępny

### Timeout workflow
- Workflow ma limit 60 minut
- Zmniejsz `max_pages` lub zwiększ `batch_size`

### Błędy Selenium
- Chrome i ChromeDriver są automatycznie instalowane
- Scraper używa trybu headless (bez GUI)

### Brak powiadomień
- Sprawdź czy `WEBHOOK_URL` jest poprawnie skonfigurowany
- Zweryfikuj format webhook'a (Slack/Discord)

## 🔄 Modyfikacja harmonogramu

Aby zmienić częstotliwość uruchamiania, edytuj `.github/workflows/scraper.yml`:

```yaml
schedule:
  - cron: '0 */6 * * *'  # Co 6 godzin
  # - cron: '0 8 * * *'   # Codziennie o 8:00 UTC  
  # - cron: '0 */3 * * *' # Co 3 godziny
```

## 📈 Optymalizacja wydajności

### Dla szybkiego scrapingu
```yaml
max_pages: "3"
batch_size: "50"
no_details: true
```

### Dla dokładnych danych
```yaml
max_pages: "10" 
batch_size: "25"
scraping_only: false
```

## 🔒 Bezpieczeństwo

- Wszystkie dane dostępowe są przechowywane jako GitHub Secrets
- Workflow wykorzystuje najnowsze wersje akcji
- Logi nie zawierają wrażliwych danych
- Automatic cleanup artefaktów po 7 dniach 