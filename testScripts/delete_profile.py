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

# Load keys from DB
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

# Fetch latest kind 0 event from DB (to get its ID for deletion)
cursor.execute(
    "SELECT content, signature, created_at FROM events WHERE kind=0 AND pubkey=? ORDER BY created_at DESC LIMIT 1",
    (pub_hex,)
)
profile_row = cursor.fetchone()
if not profile_row:
    print("No profile event found to delete.")
    conn.close()
    exit()

content, signature, created_at = profile_row

# Reconstruct the event to calculate its ID
event = Event(
    kind=0,
    content=content,
    pubkey=pub_hex,
    created_at=created_at  # Use stored timestamp
)
event.sig = signature  # Set signature to match original

# Create kind 5 deletion event
deletion_event = Event(
    kind=5,
    content="Deleting profile",
    pubkey=pub_hex,
    tags=[["e", event.id]]  # Reference the profile event ID
)
deletion_event.sign(private_key.hex())

# Store deletion event in DB
cursor.execute(
    "INSERT INTO events (kind, pubkey, content, signature) VALUES (?, ?, ?, ?)",
    (deletion_event.kind, deletion_event.pubkey, deletion_event.content, deletion_event.sig)
)
conn.commit()

print("Deletion event created and stored locally:")
print(deletion_event.to_dict())

# Publish to relays
relay_urls = ["wss://relay.damus.io", "wss://nos.lol", "wss://relay.snort.social"]
message_pool = MessagePool()
io_loop = IOLoop.current()

for url in relay_urls:
    relay = Relay(url, message_pool, io_loop)
    try:
        relay.connect()
        relay.publish(deletion_event)
        print(f"Deletion published to {url}")
        time.sleep(1)
    except Exception as e:
        print(f"Error publishing to {url}: {e}")
    finally:
        relay.close()

conn.close()
