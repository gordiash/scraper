# GitHub Actions - Troubleshooting MySQL Connection

## Problem z ModuleNotFoundError: No module named 'mysql'

Podczas uruchamiania scrapera w GitHub Actions wystąpił błąd:
```
ModuleNotFoundError: No module named 'mysql'
```

## Przyczyna

Problem występował z kilku powodów:
1. **Brak system dependencies** - Ubuntu w GitHub Actions potrzebuje bibliotek systemowych MySQL
2. **Niepoprawna instalacja mysql-connector-python** - czasami instalacja się nie udaje
3. **Brak fallback mechanizmu** - gdy jeden connector nie działa, potrzebny jest backup

## Rozwiązanie

### 1. Dodanie system dependencies

```yaml
- name: 🔧 Zainstaluj system dependencies dla MySQL
  run: |
    sudo apt-get update
    sudo apt-get install -y default-libmysqlclient-dev build-essential pkg-config
```

### 2. Instalacja wielu connectorów

```yaml
- name: 📦 Zainstaluj zależności Python
  run: |
    python -m pip install --upgrade pip setuptools wheel
    
    # Zainstaluj podstawowe zależności MySQL najpierw
    pip install mysql-connector-python==8.2.0
    
    # Zainstaluj również PyMySQL jako backup
    pip install PyMySQL==1.1.0
```

### 3. Fallback mechanizm w kodzie

```python
# Spróbuj różne connektory MySQL
connection_successful = False

# Pierwsza próba: mysql.connector
try:
    import mysql.connector
    conn = mysql.connector.connect(...)
    connection_successful = True
except ImportError:
    print('❌ mysql.connector nie jest dostępny')
except Exception as e:
    print(f'❌ Błąd mysql.connector: {e}')

# Druga próba: PyMySQL jako backup
if not connection_successful:
    try:
        import pymysql
        conn = pymysql.connect(...)
        connection_successful = True
    except ImportError:
        print('❌ PyMySQL nie jest dostępny')
    except Exception as e:
        print(f'❌ Błąd PyMySQL: {e}')
```

### 4. Diagnostyka

Dodano rozszerzony test importów:

```python
echo "🔍 Test importów MySQL..."
python -c "
import sys
print(f'🐍 Python version: {sys.version}')

try:
    import mysql.connector
    print('✅ mysql.connector imported successfully')
except ImportError as e:
    print(f'❌ mysql.connector failed: {e}')

try:
    import pymysql
    print('✅ pymysql imported successfully')
except ImportError as e:
    print(f'❌ pymysql failed: {e}')
"
```

## Test lokalny

Można przetestować połączenie lokalnie używając:

```bash
cd scripts
python test_mysql_connection.py
```

Ten skrypt testuje oba connectory i pokazuje szczegółowe informacje o połączeniu.

## Najczęstsze problemy

### 1. Brak zmiennych środowiskowych
```
❌ Brakujące sekrety: MYSQL_HOST MYSQL_PASSWORD
```
**Rozwiązanie**: Skonfiguruj sekrety w GitHub Settings > Secrets and variables > Actions

### 2. Timeout połączenia
```
❌ Błąd mysql.connector: Can't connect to MySQL server
```
**Rozwiązanie**: Sprawdź czy serwer MySQL jest dostępny z internetu

### 3. Brak tabeli
```
⚠️ Tabela nieruchomosci: NOT FOUND
```
**Rozwiązanie**: Uruchom skrypt SQL tworzący tabelę lub sprawdź nazwę bazy danych

## Sprawdzenie statusu w logach GitHub Actions

W logach workflow szukaj:
- ✅ oznacza sukces
- ❌ oznacza błąd
- ⚠️ oznacza ostrzeżenie

Przykład poprawnego działania:
```
🔍 Test połączenia z bazą MySQL...
📦 Używam mysql.connector...
✅ Połączenie z MySQL: OK (mysql.connector)
📊 MySQL version: 10.6.21-MariaDB
✅ Tabela nieruchomosci: EXISTS
```

## Monitoring

Workflow automatycznie:
1. Testuje połączenie przed scraperem
2. Pokazuje statystyki po scraperze
3. Wysyła powiadomienia o błędach
4. Zapisuje logi jako artefakty

Logi są dostępne przez 7 dni w sekcji "Artifacts" każdego uruchomienia. 