import os
import requests

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not BOT_TOKEN:
    BOT_TOKEN = "8730709075:AAGZWmuo0Bn0jI6Dzw36kqhEtYgw3zahJ5Q"

url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"

try:
    response = requests.get(url, timeout=10)
    data = response.json()

    if data.get("ok"):
        updates = data.get("result", [])
        if updates:
            print("Recent updates (last 5):")
            print("=" * 50)
            for update in updates[-5:]:
                msg = update.get("message", {})
                chat = msg.get("chat", {})
                chat_id = chat.get("id")
                title = chat.get("title", "Private")
                username = chat.get("username", "")
                print(f"Chat ID: {chat_id}")
                print(f"Title: {title}")
                print(f"Username: @{username}")
                print("-" * 30)
        else:
            print("No updates found. Send a message to the bot first!")
    else:
        print(f"Error: {data}")
except Exception as e:
    print(f"Error: {e}")
