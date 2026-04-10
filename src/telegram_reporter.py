import requests
import logging
import config

logger = logging.getLogger(__name__)


def send_telegram_report(message):
    """
    Sends a Telegram message to all configured chat IDs.
    """
    if not config.TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN is not configured!")
        return [{"success": False, "error": "Bot token missing"}]
    
    if not config.TELEGRAM_CHAT_IDS:
        logger.error("TELEGRAM_CHAT_IDS is empty! No chat IDs configured.")
        return [{"success": False, "error": "No chat IDs configured"}]

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
            logger.info(f"Sending Telegram message to chat_id: {chat_id}")
            response = requests.post(url, json=payload, timeout=30)
            response.raise_for_status()
            logger.info(f"Telegram message sent successfully to {chat_id}")
            results.append({"chat_id": chat_id, "success": True})
        except Exception as e:
            logger.error(f"Failed to send Telegram report to {chat_id}: {e}")
            results.append({"chat_id": chat_id, "success": False, "error": str(e)})
    
    return results
