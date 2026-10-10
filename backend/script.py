import sqlite3
conn = sqlite3.connect('supplyiq.db')
cursor = conn.cursor()
cursor.execute('SELECT company_id, original_filename, stored_path, row_count FROM dataset_uploads;')
for r in cursor.fetchall():
  if r[1] == 'data.csv':
    print(r)
