import sqlite3
conn = sqlite3.connect('nostr.db')
cursor = conn.cursor()
cursor.execute("SELECT name FROM users")
print("Stored usernames:", cursor.fetchall())
conn.close()
