import sqlite3

conn = sqlite3.connect("database.db")
cursor = conn.cursor()

print("\n Columns in 'claims' table:\n")
cursor.execute("PRAGMA table_info(claims);")
for col in cursor.fetchall():
    print(f"- {col[1]} ({col[2]})")

conn.close()
