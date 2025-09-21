import sqlite3
from pynostr.event import Event
from pynostr.key import PrivateKey
from pynostr.relay import Relay
from pynostr.message_pool import MessagePool
from cryptography.fernet import Fernet
from tornado.ioloop import IOLoop
import time

# Paste the Fernet key
encryption_key_b64 = b'paste fenter key string here'  # Replace with your saved key
cipher = Fernet(encryption_key_b64)

# Load keys
conn = sqlite3.connect('nostr.db')
cursor = conn.cursor()
username = input("Enter your username: ")
cursor.execute("SELECT public_key, private_key_encrypted FROM users WHERE name=?", (username,))
row = cursor.fetchone()
if not row:
    print(f"User '{username}' not found.")
    conn.close()
    exit()

pub_hex, priv_enc = row
private_key = PrivateKey.from_hex(cipher.decrypt(priv_enc.encode()).decode())

# Add followed user
followed_pubkey = input("Enter the pubkey (hex) to follow: ")
followed_name = input("Enter a name for this user (optional): ")
cursor.execute(
    "INSERT OR REPLACE INTO contacts (pubkey, name, followed) VALUES (?, ?, 1)",
    (followed_pubkey, followed_name)
)
conn.commit()

# Get all followed pubkeys for kind 3 event
cursor.execute("SELECT pubkey FROM contacts WHERE followed=1")
followed_pubkeys = [r[0] for r in cursor.fetchall()]
tags = [["p", pk] for pk in followed_pubkeys]

# Create kind 3 event
event = Event(kind=3, content="", pubkey=pub_hex, tags=tags)
event.sign(private_key.hex())

# Store in DB
cursor.execute(
    "INSERT INTO events (kind, pubkey, content, signature) VALUES (?, ?, ?, ?)",
    (event.kind, event.pubkey, event.content, event.sig)
)
conn.commit()

print("Follow list created and stored locally:")
print(event.to_dict())

# Publish to relays
relay_urls = ["wss://relay.damus.io", "wss://nos.lol", "wss://relay.snort.social"]
message_pool = MessagePool()
io_loop = IOLoop.current()

for url in relay_urls:
    relay = Relay(url, message_pool, io_loop)
    try:
        relay.connect()
        relay.publish(event)
        print(f"Follow list published to {url}")
        time.sleep(1)
    except Exception as e:
        print(f"Error publishing to {url}: {e}")
    finally:
        relay.close()

conn.close()
