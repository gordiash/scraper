import pymysql
import os
from dotenv import load_dotenv

load_dotenv()

DB_SERVERNAME = os.getenv('DB_SERVERNAME')
DB_USERNAME = os.getenv('DB_USERNAME')
DB_PASSWORD = os.getenv('DB_PASSWORD')
DB_NAME = os.getenv('DB_NAME')
DB_PORT = int(os.getenv('DB_PORT', 3306))

print(f"Próba połączenia z bazą: host={DB_SERVERNAME}, port={DB_PORT}, user={DB_USERNAME}, db={DB_NAME}")

try:
    conn = pymysql.connect(
        host=DB_SERVERNAME,
        user=DB_USERNAME,
        password=DB_PASSWORD,
        database=DB_NAME,
        port=DB_PORT,
        charset='utf8mb4'
    )
    print("Połączenie OK!")
    conn.close()
except Exception as e:
    print(f"Błąd połączenia: {e}") 