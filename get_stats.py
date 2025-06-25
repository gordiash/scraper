import os
from datetime import datetime
from dotenv import load_dotenv

# Załaduj zmienne środowiskowe z pliku .env
load_dotenv()

# Debug informacje
print("🔍 Próba połączenia z bazą danych...")

# Spróbuj różne connektory MySQL
connection_successful = False
conn = None

# Pierwsza próba: mysql.connector
try:
    import mysql.connector
    print('📦 Używam mysql.connector...')
    
    conn = mysql.connector.connect(
        host=os.getenv('MYSQL_HOST'),
        port=int(os.getenv('MYSQL_PORT', 3306)),
        user=os.getenv('MYSQL_USER'),
        password=os.getenv('MYSQL_PASSWORD'),
        database=os.getenv('MYSQL_DATABASE')
    )
    print("✅ Połączenie z MySQL: OK (mysql.connector)")
    connection_successful = True
    
except ImportError:
    print('❌ mysql.connector nie jest dostępny')
except Exception as e:
    print(f'❌ Błąd mysql.connector: {e}')

# Druga próba: PyMySQL jako backup
if not connection_successful:
    try:
        import pymysql
        print('📦 Używam PyMySQL jako backup...')
        
        conn = pymysql.connect(
            host=os.getenv('MYSQL_HOST'),
            port=int(os.getenv('MYSQL_PORT', 3306)),
            user=os.getenv('MYSQL_USER'),
            password=os.getenv('MYSQL_PASSWORD'),
            database=os.getenv('MYSQL_DATABASE')
        )
        print("✅ Połączenie z MySQL: OK (PyMySQL)")
        connection_successful = True
        
    except ImportError:
        print('❌ PyMySQL nie jest dostępny')
    except Exception as e:
        print(f'❌ Błąd PyMySQL: {e}')

if connection_successful:
    try:
        cursor = conn.cursor()
        
        # Statystyki podstawowe
        cursor.execute('SELECT COUNT(*) FROM nieruchomosci')
        total = cursor.fetchone()[0]
        print(f"📊 Pobrałem total: {total}")
        
        cursor.execute('SELECT COUNT(*) FROM nieruchomosci WHERE created_at >= DATE_SUB(NOW(), INTERVAL 1 DAY)')
        today = cursor.fetchone()[0]
        print(f"📊 Pobrałem today: {today}")
        
        cursor.execute('SELECT COUNT(*) FROM nieruchomosci WHERE updated_at >= DATE_SUB(NOW(), INTERVAL 1 HOUR)')
        last_hour = cursor.fetchone()[0]
        print(f"📊 Pobrałem last_hour: {last_hour}")
        
        # Statystyki jakości danych
        cursor.execute('SELECT COUNT(*) FROM nieruchomosci WHERE price IS NOT NULL')
        with_price = cursor.fetchone()[0]
        print(f"📊 Pobrałem with_price: {with_price}")
        
        cursor.execute('SELECT COUNT(*) FROM nieruchomosci WHERE latitude IS NOT NULL')
        geocoded = cursor.fetchone()[0]
        print(f"📊 Pobrałem geocoded: {geocoded}")
        
        # Dodatkowe statystyki
        cursor.execute('SELECT COUNT(*) FROM nieruchomosci WHERE market = "pierwotny"')
        primary_market = cursor.fetchone()[0]
        print(f"📊 Pobrałem primary_market: {primary_market}")
        
        cursor.execute('SELECT COUNT(*) FROM nieruchomosci WHERE market = "wtórny"')
        secondary_market = cursor.fetchone()[0]
        print(f"📊 Pobrałem secondary_market: {secondary_market}")
        
        cursor.execute('SELECT COUNT(*) FROM nieruchomosci WHERE has_balcony = 1')
        with_balcony = cursor.fetchone()[0]
        print(f"📊 Pobrałem with_balcony: {with_balcony}")
        
        cursor.execute('SELECT COUNT(*) FROM nieruchomosci WHERE has_garage = 1')
        with_garage = cursor.fetchone()[0]
        print(f"📊 Pobrałem with_garage: {with_garage}")
        
        # Wyświetl sformatowane statystyki
        print("\n" + "="*80)
        print("📊 STATYSTYKI BAZY DANYCH NIERUCHOMOŚCI")
        print("="*80)
        print(f"📅 Data: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"🏢 Host: {os.getenv('MYSQL_HOST')}")
        print(f"💾 Baza: {os.getenv('MYSQL_DATABASE')}")
        print("-"*80)
        
        print(f"📊 Łącznie w bazie: {total:,} ogłoszeń")
        print(f"🆕 Dodane dzisiaj: {today:,} ogłoszeń")
        print(f"⏰ Ostatnia godzina: {last_hour:,} ogłoszeń")
        print(f"💰 Z cenami: {with_price:,} ogłoszeń ({with_price/max(total,1)*100:.1f}%)")
        print(f"🌍 Geocoded: {geocoded:,} ogłoszeń ({geocoded/max(total,1)*100:.1f}%)")
        
        print(f"\n🏷️ STATYSTYKI RYNKU:")
        print(f"🆕 Rynek pierwotny: {primary_market:,} ogłoszeń ({primary_market/max(total,1)*100:.1f}%)")
        print(f"🏘️ Rynek wtórny: {secondary_market:,} ogłoszeń ({secondary_market/max(total,1)*100:.1f}%)")
        
        print(f"\n🏠 STATYSTYKI UDOGODNIEŃ:")
        print(f"🏢 Z balkonem: {with_balcony:,} ogłoszeń ({with_balcony/max(total,1)*100:.1f}%)")
        print(f"🚗 Z garażem: {with_garage:,} ogłoszeń ({with_garage/max(total,1)*100:.1f}%)")
        
        print("="*80)
        
        conn.close()
        print("✅ Statystyki pobrane pomyślnie")
        
    except Exception as e:
        print(f"❌ Błąd podczas pobierania statystyk: {e}")
        if conn:
            conn.close()
else:
    print("❌ Nie udało się połączyć z bazą danych")
    print("💡 Sprawdź konfigurację w pliku .env")
    print(f"🏢 Host: {os.getenv('MYSQL_HOST', 'NIE_USTAWIONY')}")
    print(f"👤 User: {os.getenv('MYSQL_USER', 'NIE_USTAWIONY')}")
    print(f"💾 Database: {os.getenv('MYSQL_DATABASE', 'NIE_USTAWIONY')}") 