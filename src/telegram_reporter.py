import requests
import logging
import config

logger = logging.getLogger(__name__)


def send_telegram_report(message):
    """
    Sends a Telegram message to all configured chat IDs.
    """
    if not config.TELEGRAM_BOT_TOKEN or not config.TELEGRAM_CHAT_IDS:
        # print("Warning: Telegram configuration missing. Skipping report.")
        return

    url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage"

    results = []
    for chat_id in config.TELEGRAM_CHAT_IDS:
        payload = {
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }

        try:
            response = requests.post(url, json=payload, timeout=10)
            response.raise_for_status()
            results.append({"chat_id": chat_id, "success": True})
        except Exception as e:
            logger.error(f"Failed to send Telegram report to {chat_id}: {e}")
            results.append({"chat_id": chat_id, "success": False, "error": str(e)})
    
    return results
