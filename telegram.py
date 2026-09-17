import os
import httpx
from dotenv import load_dotenv

load_dotenv()


def notify(text: str) -> None:
    """Envoie un message au chat Telegram configuré. Best-effort, ne lève pas."""
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        httpx.post(
            url,
            json={
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            },
            timeout=5.0,
        )
    except Exception:
        # on ne bloque jamais l'authentification parce que Telegram est down
        pass