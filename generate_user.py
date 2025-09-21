import sqlite3
from pynostr.key import PrivateKey
from cryptography.fernet import Fernet
import base64

# Paste the Fernet key you retrieved from setup_db.py
encryption_key_b64 = b'Copy/paste the Fenter key string created by your run of setup_db.py here'  # Replace with the key you copied
cipher = Fernet(encryption_key_b64)

# Generate keys
private_key = PrivateKey()  # Random private key
public_key = private_key.public_key

# Encrypt private key for storage (use .hex() and encode to bytes)
private_key_encrypted = cipher.encrypt(private_key.hex().encode()).decode()

# Connect to DB
conn = sqlite3.connect('nostr.db')
cursor = conn.cursor()

# Insert user (associate with a username for your reference)
username = input("Enter a username for this keypair: ")  # e.g., "my_nostr_user"
cursor.execute(
    "INSERT OR REPLACE INTO users (public_key, private_key_encrypted, name) VALUES (?, ?, ?)",
    (public_key.hex(), private_key_encrypted, username)
)
conn.commit()

# Output for you
print(f"Username (local): {username}")
print(f"Public Key (hex): {public_key.hex()}")
print(f"Public Key (npub, share this): {public_key.bech32()}")
print(f"Private Key (nsec, KEEP SECRET): {private_key.bech32()}")
print("Keys saved to DB. Use npub for logins on Nostr apps.")

conn.close()
