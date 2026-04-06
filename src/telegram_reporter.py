import requests
import config


def send_telegram_report(message):
    """
    Sends a Telegram message to all configured chat IDs.
    """
    if not config.TELEGRAM_BOT_TOKEN or not config.TELEGRAM_CHAT_IDS:
        # print("Warning: Telegram configuration missing. Skipping report.")
        return

    url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage"

    for chat_id in config.TELEGRAM_CHAT_IDS:
        payload = {
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }

        try:
            response = requests.post(url, json=payload, timeout=10)
            # print(f"Telegram response for {chat_id}: {response.status_code} - {response.text}")
            response.raise_for_status()
            # print(f"Telegram report sent to {chat_id}")
            return response.json()
        except Exception as e:
            # print(f"Failed to send Telegram report to {chat_id}: {e}")
            return str(e)
