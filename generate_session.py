#!/usr/bin/env python3
from pyrogram import Client

print("=== Telegram Session Generator ===\n")

api_id = input("31963776").strip()
api_hash = input("d352f599aff861566030a3cbba3a0f75").strip()

print("\n⚠️  Make sure you're logged into your ASSISTANT account (not bot account)")
print("This will be used for joining voice chats\n")

with Client(":memory:", api_id=int(api_id), api_hash=api_hash) as app:
    session_string = app.export_session_string()
    
    print("\n" + "="*50)
    print("✅ SESSION STRING GENERATED!")
    print("="*50)
    print(f"\nYour session string:\n")
    print(session_string)
    print(f"\n\nAdd this to your .env file as:")
    print(f"SESSION_STRING={session_string}")
    print("\n" + "="*50)
