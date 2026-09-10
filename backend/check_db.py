import sqlite3
conn = sqlite3.connect("supplyiq.db")
cur = conn.cursor()
cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
print("Tables:", [r[0] for r in cur.fetchall()])
cur.execute("SELECT id,company_id,model_type,model_source,status,model_path FROM model_registry ORDER BY training_date DESC LIMIT 10")
rows = cur.fetchall()
if rows:
    for r in rows:
        print(r)
else:
    print("No model registry rows found")
conn.close()
