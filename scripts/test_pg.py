import os
import psycopg2
url=os.getenv('DATABASE_URL','postgresql+asyncpg://postgres:postgres@localhost:5433/ai_sales')
sync=url.replace('+asyncpg','')
print('connect to',sync)
try:
    conn=psycopg2.connect(sync)
    print('connected')
    conn.close()
except Exception as e:
    print('ERR',type(e),e)
