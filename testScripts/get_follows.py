import sqlite3

conn = sqlite3.connect('nostr.db')
cursor = conn.cursor()
username = input("Enter your username: ")
cursor.execute("SELECT public_key FROM users WHERE name=?", (username,))
row = cursor.fetchone()
if not row:
    print(f"User '{username}' not found.")
    conn.close()
    exit()

pubkey = row[0]

# Get followed users
cursor.execute("SELECT pubkey, name FROM contacts WHERE followed=1")
follows = cursor.fetchall()

if not follows:
    print("No followed users.")
else:
    print(f"Followed users for '{username}' (pubkey: {pubkey}):")
    for pubkey, name in follows:
        print(f"Pubkey: {pubkey}, Name: {name or 'Unknown'}")

conn.close()
