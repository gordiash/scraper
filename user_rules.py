"""
Konfiguracja parametrów scrapera Otodom.
Tutaj możesz dostosować ustawienia scrapera do swoich potrzeb.
"""

# Parametry scrapowania
SCRAPING_CONFIG = {
    # Liczba równoległych wątków do scrapowania
    'MAX_WORKERS': 6,
    
    # Opóźnienia między requestami (w sekundach)
    'DELAYS': {
        'BETWEEN_PAGES': (1, 3),  # (min, max) opóźnienie między stronami
        'BETWEEN_REQUESTS': (2, 5),  # (min, max) opóźnienie między requestami
        'RETRY_DELAY': 5,  # opóźnienie przy ponownych próbach
    },
    
    # Limity i zabezpieczenia
    'MAX_RETRIES': 3,  # maksymalna liczba prób dla pojedynczego requestu
    'REQUEST_TIMEOUT': 30,  # timeout dla requestów w sekundach
    
    # Parametry bazy danych
    'DB_CONFIG': {
        'CHARSET': 'utf8mb4',
        'CURSOR_CLASS': 'DictCursor',
        'PORT': 3306,
    },
    
    # Parametry logowania
    'LOG_CONFIG': {
        'LEVEL': 'INFO',
        'FORMAT': '%(asctime)s - %(levelname)s - %(message)s',
        'FILE': 'scraper.log',
    },
    
    # URL-e
    'URLS': {
        'BASE_URL': 'https://www.otodom.pl',
        'LISTINGS_URL': 'https://www.otodom.pl/pl/wyniki/sprzedaz/mieszkanie/cala-polska',
    },
    
    # Parametry proxy (opcjonalne)
    'PROXY_LIST': [
        None,  # Bez proxy
        # 'http://proxy1.example.com:8080',  # Przykładowe proxy - odkomentuj i dodaj swoje
        # 'http://proxy2.example.com:8080',
    ],
    
    # Parametry zapisywania postępu
    'PROGRESS_FILE': 'progress.txt',
    
    # Parametry parsowania
    'PARSING': {
        'MAX_AREA': 1000,  # maksymalna powierzchnia w m²
        'MAX_ROOMS': 10,   # maksymalna liczba pokoi
        'VALID_MARKETS': ['pierwotny', 'wtórny'],  # dozwolone wartości rynku
    }
}

# Funkcje pomocnicze do konfiguracji
def get_random_delay(delay_range):
    """Zwraca losowe opóźnienie z podanego zakresu."""
    import random
    return random.uniform(*delay_range)

def get_delay_between_pages():
    """Zwraca losowe opóźnienie między stronami."""
    return get_random_delay(SCRAPING_CONFIG['DELAYS']['BETWEEN_PAGES'])

def get_delay_between_requests():
    """Zwraca losowe opóźnienie między requestami."""
    return get_random_delay(SCRAPING_CONFIG['DELAYS']['BETWEEN_REQUESTS'])

def get_db_config():
    """Zwraca konfigurację bazy danych."""
    return SCRAPING_CONFIG['DB_CONFIG']

def get_log_config():
    """Zwraca konfigurację logowania."""
    return SCRAPING_CONFIG['LOG_CONFIG']

def get_urls():
    """Zwraca konfigurację URL-i."""
    return SCRAPING_CONFIG['URLS']

def get_proxy_list():
    """Zwraca listę proxy."""
    return SCRAPING_CONFIG['PROXY_LIST']

def get_parsing_config():
    """Zwraca konfigurację parsowania."""
    return SCRAPING_CONFIG['PARSING']

def get_max_workers():
    """Zwraca maksymalną liczbę wątków."""
    return SCRAPING_CONFIG['MAX_WORKERS']

def get_max_retries():
    """Zwraca maksymalną liczbę prób."""
    return SCRAPING_CONFIG['MAX_RETRIES']

def get_request_timeout():
    """Zwraca timeout dla requestów."""
    return SCRAPING_CONFIG['REQUEST_TIMEOUT']

def get_progress_file():
    """Zwraca nazwę pliku postępu."""
    return SCRAPING_CONFIG['PROGRESS_FILE'] 