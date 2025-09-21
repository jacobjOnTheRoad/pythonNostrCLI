import sqlite3
from cryptography.fernet import Fernet  # For basic private key encryption (install if needed)
import base64

# Generate a key for encryption (in real use, derive from user password)
encryption_key = Fernet.generate_key()
cipher = Fernet(encryption_key)
print(f"Save this encryption key securely: {encryption_key.decode()}")  # Store this separately!

# Connect/create DB
conn = sqlite3.connect('nostr.db')
cursor = conn.cursor()

# Table for user keys (one row per user)
cursor.execute('''
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_key TEXT UNIQUE NOT NULL,
    private_key_encrypted TEXT NOT NULL,
    name TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
''')

# Table for events (posts, profiles, etc.)
cursor.execute('''
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kind INTEGER NOT NULL,
    pubkey TEXT NOT NULL,
    content TEXT NOT NULL,
    signature TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (pubkey) REFERENCES users (public_key)
)
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS contacts (
    pubkey TEXT PRIMARY KEY,
    name TEXT,
    followed BOOLEAN DEFAULT 1
);
''')

conn.commit()
conn.close()
print("Database 'nostr.db' created successfully!")
