import sqlite3
import os
import time
import uuid
import json
from pynostr.relay_manager import RelayManager
from pynostr.filters import FiltersList, Filters
from pynostr.event import Event, EventKind
from pynostr.key import PrivateKey
from pynostr.relay import Relay
from pynostr.message_pool import MessagePool
from tornado.ioloop import IOLoop
from cryptography.fernet import Fernet

# Suppress warnings (WebSocket ping, etc.)
import logging
logging.getLogger('tornado').setLevel(logging.CRITICAL)
import warnings
warnings.filterwarnings("ignore", message="websocket_ping_timeout")

# Paste the Fernet key (same as used in generate_user.py)
encryption_key_b64 = b'Copy/paste the Fenter key printed by the generate_user.py here'  # Replace with your saved key
cipher = Fernet(encryption_key_b64)

def load_user_keys(username):
    conn = sqlite3.connect('nostr.db')
    cursor = conn.cursor()
    cursor.execute("SELECT public_key, private_key_encrypted FROM users WHERE name=?", (username,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        print(f"User '{username}' not found. Run generate_user.py first.")
        return None
    pub_hex, priv_enc = row
    private_key = PrivateKey.from_hex(cipher.decrypt(priv_enc.encode()).decode())
    return pub_hex, private_key, username

def discover_feed(pub_hex, private_key, username):
    conn = sqlite3.connect('nostr.db')
    cursor = conn.cursor()
    relay_manager = RelayManager(timeout=60)
    relay_manager.add_relay("wss://relay.damus.io")
    relay_manager.add_relay("wss://nos.lol")
    relay_manager.add_relay("wss://relay.snort.social")
    limit = 10
    next_key = None
    running = True
    while running:
        filters = FiltersList([Filters(kinds=[EventKind.TEXT_NOTE], limit=limit)])
        if next_key:
            filters[0].since = int(next_key)
        subscription_id = uuid.uuid1().hex
        relay_manager.add_subscription_on_all_relays(subscription_id, filters)
        relay_manager.run_sync()
        time.sleep(2)
        fetched = 0
        authors = set()
        posts = []
        while relay_manager.message_pool.has_events():
            event_msg = relay_manager.message_pool.get_event()
            event = event_msg.event
            if event.kind == EventKind.TEXT_NOTE:
                cursor.execute(
                    "INSERT OR IGNORE INTO events (kind, pubkey, content, signature, created_at) VALUES (?, ?, ?, ?, ?)",
                    (event.kind, event.pubkey, event.content, event.sig, event.created_at)
                )
                posts.append((event.pubkey, event.content, event.created_at))
                authors.add(event.pubkey)
                fetched += 1
        conn.commit()
        if authors:
            profile_filters = FiltersList([Filters(authors=list(authors), kinds=[EventKind.SET_METADATA], limit=len(authors))])
            profile_subscription_id = uuid.uuid1().hex
            relay_manager.add_subscription_on_all_relays(profile_subscription_id, profile_filters)
            relay_manager.run_sync()
            time.sleep(2)
            while relay_manager.message_pool.has_events():
                event_msg = relay_manager.message_pool.get_event()
                event = event_msg.event
                if event.kind == EventKind.SET_METADATA:
                    try:
                        profile_data = json.loads(event.content)
                        name = profile_data.get("name", "")
                        cursor.execute(
                            "INSERT OR REPLACE INTO contacts (pubkey, name, followed) VALUES (?, ?, 0)",
                            (event.pubkey, name)
                        )
                    except json.JSONDecodeError:
                        pass
            conn.commit()
        if posts:
            os.system('clear' if os.name == 'posix' else 'cls')
            print("\nGeneral feed:")
            for i, (pubkey, content, created_at) in enumerate(posts, 1):
                cursor.execute("SELECT name FROM contacts WHERE pubkey=?", (pubkey,))
                name_row = cursor.fetchone()
                name = name_row[0] if name_row and name_row[0] else pubkey[:10] + "..."
                print(f"{i}. From: {name} ({pubkey[:10]}...), Content: {content}, Created: {created_at}")
                print("---")
            print(f"Showing {len(posts)} posts. Remaining in queue: {max(0, fetched - len(posts))}")
            next_key = posts[-1][2]
            print(f"Next key: {next_key}")
        else:
            print("\nNo new posts fetched.")
        follow_input = input("\nEnter pubkey to follow (or Enter to load more, 'q' to quit): ").strip()
        if follow_input.lower() == 'q':
            running = False
        elif follow_input == '':
            continue
        else:
            follow = follow_input
            cursor.execute("SELECT name FROM contacts WHERE pubkey=?", (follow,))
            name_row = cursor.fetchone()
            name = name_row[0] if name_row else input("Enter a name (optional): ").strip()
            cursor.execute(
                "INSERT OR REPLACE INTO contacts (pubkey, name, followed) VALUES (?, ?, 1)",
                (follow, name)
            )
            conn.commit()
            print(f"Followed {name or follow[:10] + '...'}")
            # Update kind 3
            cursor.execute("SELECT pubkey FROM contacts WHERE followed=1")
            followed_pubkeys = [r[0] for r in cursor.fetchall()]
            tags = [["p", pk] for pk in followed_pubkeys]
            event = Event(kind=3, content="", pubkey=pub_hex, tags=tags)
            event.sign(private_key.hex())
            cursor.execute(
                "INSERT INTO events (kind, pubkey, content, signature) VALUES (?, ?, ?, ?)",
                (event.kind, event.pubkey, event.content, event.sig)
            )
            conn.commit()
            for url in ["wss://relay.damus.io", "wss://nos.lol", "wss://relay.snort.social"]:
                relay = Relay(url, MessagePool(), IOLoop.current())
                try:
                    relay.connect()
                    relay.publish(event)
                    print(f"Updated contact list published to {url}")
                    time.sleep(1)
                except Exception as e:
                    print(f"Error publishing to {url}: {e}")
                finally:
                    relay.close()
    relay_manager.close_all_relay_connections()
    conn.close()

def read_feed(pub_hex, private_key, username):
    conn = sqlite3.connect('nostr.db')
    cursor = conn.cursor()
    cursor.execute("SELECT pubkey FROM contacts WHERE followed=1")
    authors = [r[0] for r in cursor.fetchall()]
    if not authors:
        print("No followed users.")
        conn.close()
        return
    relay_manager = RelayManager(timeout=60)
    relay_manager.add_relay("wss://relay.damus.io")
    relay_manager.add_relay("wss://nos.lol")
    relay_manager.add_relay("wss://relay.snort.social")
    limit = 10
    next_key = input("Enter next key (since timestamp, leave blank for latest): ") or None
    filters = FiltersList([Filters(authors=authors, kinds=[EventKind.TEXT_NOTE], limit=limit)])
    if next_key:
        filters[0].since = int(next_key)
    subscription_id = uuid.uuid1().hex
    relay_manager.add_subscription_on_all_relays(subscription_id, filters)
    relay_manager.run_sync()
    time.sleep(2)
    fetched = 0
    while relay_manager.message_pool.has_events():
        event_msg = relay_manager.message_pool.get_event()
        event = event_msg.event
        cursor.execute(
            "INSERT OR IGNORE INTO events (kind, pubkey, content, signature, created_at) VALUES (?, ?, ?, ?, ?)",
            (event.kind, event.pubkey, event.content, event.sig, event.created_at)
        )
        fetched += 1
    conn.commit()
    cursor.execute(
        "SELECT pubkey, content, created_at FROM events WHERE kind=1 AND pubkey IN ({}) ORDER BY created_at DESC LIMIT {}".format(
            ','.join('?' for _ in authors), limit
        ), authors
    )
    posts = cursor.fetchall()
    if posts:
        os.system('clear' if os.name == 'posix' else 'cls')
        print("Followed feed:")
        for i, (pubkey, content, created_at) in enumerate(posts, 1):
            cursor.execute("SELECT name FROM contacts WHERE pubkey=?", (pubkey,))
            name_row = cursor.fetchone()
            name = name_row[0] if name_row else pubkey[:10] + "..."
            print(f"{i}. From: {name} ({pubkey[:10]}...), Content: {content}, Created: {created_at}")
        print(f"Showing {len(posts)} posts. Remaining in queue: {max(0, fetched - len(posts))}")
        next_key = posts[-1][2]
        print(f"Next key: {next_key}")
    else:
        print("No posts fetched.")
    relay_manager.close_all_relay_connections()
    conn.close()

def post_note(pub_hex, private_key, username):
    content = input("Enter your post content: ")
    conn = sqlite3.connect('nostr.db')
    cursor = conn.cursor()
    event = Event(kind=1, content=content, pubkey=pub_hex)
    event.sign(private_key.hex())
    cursor.execute(
        "INSERT INTO events (kind, pubkey, content, signature, created_at) VALUES (?, ?, ?, ?, ?)",
        (event.kind, event.pubkey, event.content, event.sig, event.created_at)
    )
    conn.commit()
    print("Post created and stored locally:")
    print(event.to_dict())
    relay_urls = ["wss://relay.damus.io", "wss://nos.lol", "wss://relay.snort.social"]
    for url in relay_urls:
        relay = Relay(url, MessagePool(), IOLoop.current())
        try:
            relay.connect()
            relay.publish(event)
            print(f"Post published to {url}")
            time.sleep(1)
        except Exception as e:
            print(f"Error publishing to {url}: {e}")
        finally:
            relay.close()
    conn.close()

def follow_user(pub_hex, private_key, username):
    conn = sqlite3.connect('nostr.db')
    cursor = conn.cursor()
    followed_pubkey = input("Enter the pubkey (hex) to follow: ")
    followed_name = input("Enter a name for this user (optional): ")
    cursor.execute(
        "INSERT OR REPLACE INTO contacts (pubkey, name, followed) VALUES (?, ?, 1)",
        (followed_pubkey, followed_name)
    )
    conn.commit()
    cursor.execute("SELECT pubkey FROM contacts WHERE followed=1")
    followed_pubkeys = [r[0] for r in cursor.fetchall()]
    tags = [["p", pk] for pk in followed_pubkeys]
    event = Event(kind=3, content="", pubkey=pub_hex, tags=tags)
    event.sign(private_key.hex())
    cursor.execute(
        "INSERT INTO events (kind, pubkey, content, signature) VALUES (?, ?, ?, ?)",
        (event.kind, event.pubkey, event.content, event.sig)
    )
    conn.commit()
    print("Follow list created and stored locally:")
    print(event.to_dict())
    relay_urls = ["wss://relay.damus.io", "wss://nos.lol", "wss://relay.snort.social"]
    for url in relay_urls:
        relay = Relay(url, MessagePool(), IOLoop.current())
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

def get_follows(pub_hex, private_key, username):
    conn = sqlite3.connect('nostr.db')
    cursor = conn.cursor()
    cursor.execute("SELECT pubkey, name FROM contacts WHERE followed=1")
    follows = cursor.fetchall()
    if not follows:
        print("No followed users.")
    else:
        print(f"Followed users for '{username}':")
        for pubkey, name in follows:
            print(f"Pubkey: {pubkey}, Name: {name or 'Unknown'}")
    conn.close()

def delete_profile(pub_hex, private_key, username):
    conn = sqlite3.connect('nostr.db')
    cursor = conn.cursor()
    cursor.execute(
        "SELECT content, signature, created_at FROM events WHERE kind=0 AND pubkey=? ORDER BY created_at DESC LIMIT 1",
        (pub_hex,)
    )
    profile_row = cursor.fetchone()
    if not profile_row:
        print("No profile event found to delete.")
        conn.close()
        return
    content, signature, created_at = profile_row
    event = Event(kind=0, content=content, pubkey=pub_hex, created_at=created_at)
    event.sig = signature
    deletion_event = Event(kind=5, content="Deleting profile", pubkey=pub_hex, tags=[["e", event.id]])
    deletion_event.sign(private_key.hex())
    cursor.execute(
        "INSERT INTO events (kind, pubkey, content, signature) VALUES (?, ?, ?, ?)",
        (deletion_event.kind, deletion_event.pubkey, deletion_event.content, deletion_event.sig)
    )
    conn.commit()
    print("Deletion event created and stored locally:")
    print(deletion_event.to_dict())
    relay_urls = ["wss://relay.damus.io", "wss://nos.lol", "wss://relay.snort.social"]
    for url in relay_urls:
        relay = Relay(url, MessagePool(), IOLoop.current())
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

def update_profile(pub_hex, private_key, username):
    profile_data = {
        "name": input("Enter display name: "),
        "about": input("Enter bio: "),
        "picture": input("Enter picture URL (or blank): ")
    }
    content = json.dumps(profile_data)
    conn = sqlite3.connect('nostr.db')
    cursor = conn.cursor()
    event = Event(kind=0, content=content, pubkey=pub_hex)
    event.sign(private_key.hex())
    cursor.execute(
        "INSERT INTO events (kind, pubkey, content, signature, created_at) VALUES (?, ?, ?, ?, ?)",
        (event.kind, event.pubkey, event.content, event.sig, event.created_at)
    )
    conn.commit()
    print("Profile updated and stored locally:")
    print(event.to_dict())
    relay_urls = ["wss://relay.damus.io", "wss://nos.lol", "wss://relay.snort.social"]
    for url in relay_urls:
        relay = Relay(url, MessagePool(), IOLoop.current())
        try:
            relay.connect()
            relay.publish(event)
            print(f"Profile published to {url}")
            time.sleep(1)
        except Exception as e:
            print(f"Error publishing to {url}: {e}")
        finally:
            relay.close()
    conn.close()

# Main menu
def main():
    while True:
        print("\n--- Nostr CLI ---")
        print("1. Discover Feed (general posts)")
        print("2. Read Feed (followed users)")
        print("3. Post Note")
        print("4. Follow User")
        print("5. List Follows")
        print("6. Delete Profile")
        print("7. Update Profile")
        print("8. Quit")
        choice = input("Choose an option (1-8): ").strip()
        if choice == '8':
            print("Goodbye!")
            break
        username = input("Enter your username: ")
        pub_hex, private_key, _ = load_user_keys(username)
        if not pub_hex:
            continue
        if choice == '1':
            discover_feed(pub_hex, private_key, username)
        elif choice == '2':
            read_feed(pub_hex, private_key, username)
        elif choice == '3':
            post_note(pub_hex, private_key, username)
        elif choice == '4':
            follow_user(pub_hex, private_key, username)
        elif choice == '5':
            get_follows(pub_hex, private_key, username)
        elif choice == '6':
            delete_profile(pub_hex, private_key, username)
        elif choice == '7':
            update_profile(pub_hex, private_key, username)
        else:
            print("Invalid choice. Try again.")

if __name__ == "__main__":
    main()
