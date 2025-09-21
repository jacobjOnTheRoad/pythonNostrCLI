import sqlite3
from pynostr.event import Event
from pynostr.key import PrivateKey
from pynostr.relay import Relay
from pynostr.message_pool import MessagePool
from cryptography.fernet import Fernet
from tornado.ioloop import IOLoop
import time

# Paste the Fernet key (same as used in generate_user.py)
encryption_key_b64 = b'paste fenter key string here'  # Replace with your saved key
cipher = Fernet(encryption_key_b64)

# Load keys from DB
conn = sqlite3.connect('nostr.db')
cursor = conn.cursor()
username = input("Enter your username: ")
cursor.execute("SELECT public_key, private_key_encrypted FROM users WHERE name=?", (username,))
row = cursor.fetchone()
if not row:
    print(f"User '{username}' not found in database. Run generate_user.py first.")
    conn.close()
    exit()

pub_hex, priv_enc = row
private_key_bytes = cipher.decrypt(priv_enc.encode()).decode()  # Decrypt to hex string
private_key = PrivateKey.from_hex(private_key_bytes)  # Reconstruct PrivateKey

# Create text note event (kind 1)
content = input("Enter your post content: ")  # e.g., "Hello, Nostr!"
event = Event(
    kind=1,
    content=content,
    pubkey=pub_hex
)
event.sign(private_key.hex())  # Sign with hex string

# Store in DB (add event_id if you update the schema; see note below)
cursor.execute(
    "INSERT INTO events (kind, pubkey, content, signature) VALUES (?, ?, ?, ?)",
    (event.kind, event.pubkey, event.content, event.sig)
)
conn.commit()

print("Post created and stored locally:")
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
        print(f"Post published to {url}")
        time.sleep(1)  # Brief pause to ensure event is sent
    except Exception as e:
        print(f"Error publishing to {url}: {e}")
    finally:
        relay.close()

conn.close()
