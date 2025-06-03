# OtoDom Scraper z integracją Notion

Skrypt do automatycznego pobierania ogłoszeń mieszkaniowych z serwisu OtoDom i zapisywania ich w bazie Notion.

## Funkcjonalności

- Scraping ogłoszeń mieszkaniowych z OtoDom
- Automatyczna paginacja (przechodzenie przez wszystkie strony wyników)
- Wykrywanie i pomijanie duplikatów
- Walidacja danych (np. sprawdzanie poprawności ceny)
- Zapisywanie danych w bazie Notion
- Obsługa limitów zapytań (delays między requestami)
- Zapisywanie daty pobrania ogłoszenia
- Automatyczne uruchamianie codziennie o 01:00 AM (GitHub Actions)

## Pobierane dane

- Tytuł ogłoszenia
- Cena
- Adres
- Powierzchnia
- Liczba pokoi
- Rynek (pierwotny/wtórny)
- ID ogłoszenia
- URL ogłoszenia
- Data pobrania

## Wymagania

- Python 3.8+
- Konto w Notion
- Notion API Key
- Baza danych w Notion z odpowiednią strukturą
- (Opcjonalnie) Konto GitHub dla automatycznego uruchamiania

## Instalacja

1. Sklonuj repozytorium:
```bash
git clone [url-repozytorium]
cd [nazwa-folderu]
```

2. Zainstaluj wymagane zależności:
```bash
pip install -r requirements.txt
```

3. Utwórz plik `.env` w głównym katalogu projektu:
```
NOTION_API_KEY=twój_klucz_api_notion
NOTION_DATABASE_ID=id_twojej_bazy_danych
```

## Konfiguracja bazy Notion

1. Utwórz nową bazę danych w Notion
2. Dodaj następujące kolumny:
   - Title (type: title)
   - Price (type: rich text)
   - Address (type: rich text)
   - Area (type: rich text)
   - Rooms (type: rich text)
   - Market (type: rich text)
   - Ad ID (type: rich text)
   - URL (type: url)
   - Date (type: date)

3. Utwórz nową integrację na stronie: https://www.notion.so/my-integrations
4. Skopiuj klucz API (Integration Token)
5. Połącz bazę danych z integracją (Share -> Add connections)
6. Skopiuj ID bazy danych z URL (32 znaki po nazwie workspace w URL)

## Automatyczne uruchamianie (GitHub Actions)

Skrypt może być automatycznie uruchamiany codziennie o 01:00 AM UTC za pomocą GitHub Actions.

Aby skonfigurować automatyczne uruchamianie:

1. Utwórz fork tego repozytorium na GitHub
2. Przejdź do Settings -> Secrets and variables -> Actions
3. Dodaj następujące sekrety:
   - `NOTION_API_KEY`: Twój klucz API Notion
   - `NOTION_DATABASE_ID`: ID Twojej bazy danych Notion
4. GitHub Actions automatycznie uruchomi scraper według harmonogramu

Możesz też ręcznie uruchomić scraper poprzez zakładkę "Actions" w repozytorium.

## Użycie lokalne

Uruchom skrypt komendą:
```bash
python scraper.py
```

Skrypt będzie:
1. Pobierał listę istniejących ogłoszeń z bazy Notion
2. Przechodził przez kolejne strony wyników na OtoDom
3. Pobierał szczegóły każdego ogłoszenia
4. Pomijał duplikaty i ogłoszenia bez ceny
5. Zapisywał nowe ogłoszenia w bazie Notion

## Bezpieczeństwo

- Skrypt używa losowych opóźnień między requestami (2-5 sekund)
- Dodatkowe opóźnienia między stronami (3-7 sekund)
- Proper User-Agent headers
- Obsługa błędów i wyjątków
- Bezpieczne przechowywanie kluczy w GitHub Secrets

## Uwagi

- Upewnij się, że masz odpowiednie uprawnienia do bazy Notion
- Sprawdź limity API Notion dla swojego konta
- Regularnie monitoruj zmiany w strukturze strony OtoDom, które mogą wpłynąć na działanie scrapera
- GitHub Actions może mieć limity dla darmowych kont - sprawdź aktualną dokumentację GitHub 