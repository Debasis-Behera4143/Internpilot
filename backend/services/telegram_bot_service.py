"""Telegram bot notification service for instant opportunity match alerts."""

import requests
from backend.utils.config import settings
from backend.utils.logger import get_logger

logger = get_logger("telegram_bot_service")

BOT_TOKEN = settings.TELEGRAM_BOT_TOKEN
CHAT_ID = settings.TELEGRAM_CHAT_ID


def send_job_alert(job, score):
    """Send Telegram message for relevant internship/job match.
    Supports both legacy dict and Opportunity model.
    """
    bot_token = settings.TELEGRAM_BOT_TOKEN or BOT_TOKEN
    chat_id = settings.TELEGRAM_CHAT_ID or CHAT_ID

    if not bot_token or not chat_id:
        logger.info("Telegram notification skipped: TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not configured in .env.")
        return False

    title = getattr(job, "title", None) or job.get("title", "Opportunity")
    opp_type = getattr(job, "opportunity_type", None) or job.get("type", job.get("opportunity_type", "Internship"))
    link = getattr(job, "apply_url", None) or job.get("link", job.get("apply_url", ""))

    message = f"""
🔥 Student Opportunity Match Found

💼 Role:
{title}

🏷 Type:
{opp_type}

📊 Match Score:
{round(score, 2)}%

🔗 Link:
{link}
"""

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message.strip()
    }

    try:
        response = requests.post(url, data=payload, timeout=10)
        if response.status_code == 200:
            logger.info(f"Telegram alert sent successfully for: {title}")
            return True
        else:
            logger.warning(f"Telegram API responded with code {response.status_code}: {response.text}")
            return False
    except Exception as e:
        logger.warning(f"Failed to deliver Telegram alert: {e}")
        return False


__all__ = ["send_job_alert"]
