import psycopg2
import traceback

try:
    conn = psycopg2.connect(host='127.0.0.1', port=5433, dbname='ai_sales', user='postgres', password='postgres')
    print('connected OK')
    conn.close()
except Exception:
    traceback.print_exc()
