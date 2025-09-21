import sqlite3
from cryptography.fernet import Fernet  # For basic private key encryption (install if needed)
import base64

cipher = Fernet('p3pf6lfyx_udB5HmZfYifuJE-sZ2DEcF08ngv-hWaCg=')

# Connect/create DB
conn = sqlite3.connect('nostr.db')
cursor = conn.cursor()

cursor.execute('''
CREATE TABLE IF NOT EXISTS contacts (
    pubkey TEXT PRIMARY KEY,
    name TEXT,
    followed BOOLEAN DEFAULT 1
);
''')

conn.commit()
conn.close()
print("Database 'nostr.db' changed successfully!")
