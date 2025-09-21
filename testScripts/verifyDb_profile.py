import sqlite3
conn = sqlite3.connect('nostr.db')
cursor = conn.cursor()
cursor.execute("SELECT kind, pubkey, content, signature FROM events WHERE kind=0")
print("Profile events:", cursor.fetchall())
conn.close()
