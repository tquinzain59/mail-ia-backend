import os
import httpx
from loguru import logger
from typing import List, Tuple

MAILGUN_DOMAIN = os.getenv("MAILGUN_DOMAIN", "")
MAILGUN_API_KEY = os.getenv("MAILGUN_API_KEY", "")
MAIL_FROM = os.getenv("MAIL_FROM", f"robot@{MAILGUN_DOMAIN}" if MAILGUN_DOMAIN else "robot@example.com")

async def send_email(to: str, subject: str, text: str, attachments: List[Tuple[str, bytes, str]]):
    """
    Envoi via Mailgun API (messages).
    attachments: liste de tuples (filename, data_bytes, mime)
    """
    if not MAILGUN_DOMAIN or not MAILGUN_API_KEY:
        logger.warning("Mailgun non configuré — simulation locale (log only).")
        logger.info(f"[SIMULATED EMAIL] to={to} subject={subject}\n{text}")
        return

    url = f"https://api.mailgun.net/v3/{MAILGUN_DOMAIN}/messages"
    files = []
    for (filename, data, mime) in attachments:
        files.append(("attachment", (filename, data, mime)))

    data = {
        "from": MAIL_FROM,
        "to": [to],
        "subject": subject,
        "text": text,
    }

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(url, auth=("api", MAILGUN_API_KEY), data=data, files=files or None)
        r.raise_for_status()