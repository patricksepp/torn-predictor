"""
Käivita: python setup_db.py
Nõuab: DB_PASSWORD env muutujat või .env faili DATABASE_URL välja
"""
import os
import sys

DB_PASSWORD = os.getenv("DB_PASSWORD")
if not DB_PASSWORD:
    print("VIGA: DB_PASSWORD env muutuja puudub")
    print("Kasutus: DB_PASSWORD=xxx python setup_db.py")
    sys.exit(1)

try:
    import psycopg2
except ImportError:
    print("Installi psycopg2: pip install psycopg2-binary")
    sys.exit(1)

SCHEMA_FILE = os.path.join(os.path.dirname(__file__), "db", "schema.sql")
PROJECT_REF = "mpoadoylswgdjifrvcve"

conn_str = (
    f"postgresql://postgres.{PROJECT_REF}:{DB_PASSWORD}"
    f"@aws-0-eu-central-1.pooler.supabase.com:6543/postgres"
)

print("Ühendun Supabase PostgreSQL-iga...")
conn = psycopg2.connect(conn_str)
conn.autocommit = True
cur = conn.cursor()

with open(SCHEMA_FILE, "r", encoding="utf-8") as f:
    sql = f.read()

print("Käivitan schema.sql...")
cur.execute(sql)
print("Tabelid loodud!")

cur.execute("""
    SELECT table_name FROM information_schema.tables
    WHERE table_schema = 'public'
    ORDER BY table_name;
""")
tables = [row[0] for row in cur.fetchall()]
print("Tabelid andmebaasis:", tables)

cur.close()
conn.close()
