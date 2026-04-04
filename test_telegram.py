import sys
import os
import requests

# Set path to import from config
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_IDS

def get_recent_chat_ids(bot_token):
    """
    Fetches recent updates from the bot to automatically detect chat IDs 
    (from private messages and groups).
    """
    url = f"https://api.telegram.org/bot{bot_token}/getUpdates"
    discovered_ids = set()
    
    try:
        response = requests.get(url)
        response.raise_for_status()
        updates = response.json().get('result', [])
        
        for update in updates:
            if 'message' in update:
                chat = update['message']['chat']
                discovered_ids.add((chat['id'], chat['type'], chat.get('title') or chat.get('username') or chat.get('first_name')))
    except Exception as e:
        print(f"Error fetching updates: {e}")
        
    return discovered_ids

def test_telegram():
    if not TELEGRAM_BOT_TOKEN:
        print("Error: Please set TELEGRAM_BOT_TOKEN in .env first.")
        return
        
    print(f"Using Bot Token: {TELEGRAM_BOT_TOKEN[:10]}...")
    
    chat_ids_to_message = set(TELEGRAM_CHAT_IDS)
    
    print("\nChecking for recent messages to auto-discover Chat IDs...")
    discovered = get_recent_chat_ids(TELEGRAM_BOT_TOKEN)
    
    if discovered:
        print("Found the following recent chats:")
        for cid, ctype, cname in discovered:
            print(f" - {ctype} ({cname}): {cid}")
            chat_ids_to_message.add(str(cid))
    else:
        print("No recent messages found. (Make sure you sent a message to the bot or added it to a group first, then ran this command)")

    if not chat_ids_to_message:
        print("Error: No chat IDs found in config, and no recent activity detected via getUpdates.")
        print("To fix this:")
        print("1. Send a message to your bot on Telegram.")
        print("2. Add the bot to your group and send a message there.")
        print("3. Run this script again.")
        return

    print("\nSending test messages...")
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    
    for chat_id in chat_ids_to_message:
        print(f"➡️ Sending to {chat_id}...")
        payload = {
            "chat_id": chat_id,
            "text": "🤖 Hello! This is a test message from your Video Automation Agent."
        }
        
        try:
            response = requests.post(url, json=payload)
            response.raise_for_status()
            print(f"✅ Success sending to {chat_id}!")
        except Exception as e:
            print(f"❌ Failed to send to {chat_id}. Error: {e}")
            if hasattr(e, 'response') and getattr(e, 'response') is not None:
                print(e.response.text)

if __name__ == "__main__":
    test_telegram()
