import sqlite3
from pynostr.event import Event
from pynostr.key import PrivateKey
from cryptography.fernet import Fernet
import json
from pynostr.relay import Relay
from pynostr.message_pool import MessagePool
from tornado.ioloop import IOLoop

# Paste the Fernet key
encryption_key_b64 = b'paste fenter key string here'  # Same key as generate_user.py
cipher = Fernet(encryption_key_b64)

# Load keys from DB
conn = sqlite3.connect('nostr.db')
cursor = conn.cursor()
username = input("Enter your username: ")
cursor.execute("SELECT public_key, private_key_encrypted FROM users WHERE name=?", (username,))
row = cursor.fetchone()
if not row:
    print("User not found. Run generate_user.py first.")
    exit()

pub_hex, priv_enc = row
private_key_bytes = cipher.decrypt(priv_enc.encode()).decode()  # Decrypt to hex string
private_key = PrivateKey.from_hex(private_key_bytes)  # Reconstruct PrivateKey

# Create profile event (kind 0)
# To delete a profile on relays that honor deletes, publish this with all blank fields
profile_data = {
    "name": "justanotheruserterran",
    "about": "This is a test profile, making my own cmd line nostr client setup",
    "picture": ""
}
content = json.dumps(profile_data)

event = Event(
    kind=0,
    content=content,
    pubkey=pub_hex
)
event.sign(private_key.hex())

# Store in DB
cursor.execute(
    "INSERT INTO events (kind, pubkey, content, signature) VALUES (?, ?, ?, ?)",
    (event.kind, event.pubkey, event.content, event.sig)  # Use event.sig instead of event.signature
)
conn.commit()

print("Profile event created and stored:")
print(event.to_dict())
#print("To publish: Connect to a relay (see Step 5 in original guide).")

# Publish to relays
relay_urls = ["wss://relay.damus.io", "wss://nos.lol", "wss://relay.snort.social"]
message_pool = MessagePool()
io_loop = IOLoop.current()

for url in relay_urls:
    relay = Relay(url, message_pool, io_loop)
    try:
        relay.connect()
        relay.publish(event)
        print(f"Profile published to {url}")
        time.sleep(1)  # Brief pause to ensure event is sent
    except Exception as e:
        print(f"Error publishing to {url}: {e}")
    finally:
        relay.close()

conn.close()
