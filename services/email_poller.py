import asyncio
import os
import time
from typing import Dict

from telegram import Bot
from telegram.constants import ParseMode
from telegram.error import TelegramError

from agent.agent import Agent
from core.config import get_settings
from core.logging import logger
from services.email_service import EmailService

# --- Globals ---
PROCESSED_EMAILS_FILE = "data/processed_emails.log"
POLL_INTERVAL_SECONDS = 5  # Check for new emails every 5 seconds

def load_processed_emails() -> set:
    """Loads the set of processed email IDs from a log file."""
    if not os.path.exists(PROCESSED_EMAILS_FILE):
        return set()
    with open(PROCESSED_EMAILS_FILE, "r") as f:
        return {line.strip() for line in f}

def save_processed_email(email_id: str):
    """Appends a new processed email ID to the log file."""
    with open(PROCESSED_EMAILS_FILE, "a") as f:
        f.write(f"{email_id}\n")

async def notify_user(bot: Bot, user_id: int, email: Dict, draft: Dict):
    """Sends a formatted notification with the draft to the user in Telegram."""
    subject = email.get('subject', 'N/A')
    sender = email.get('from', 'N/A')
    draft_subject = draft.get('subject', 'N/A')
    draft_body = draft.get('body_text', 'N/A')
    draft_id = draft.get('id')

    message = f"""
📬 <b>Neue E-Mail erhalten!</b>

<b>Von:</b> {sender}
<b>Betreff:</b> {subject}
---
📄 <b>Antwortentwurf (ID: <code>{draft_id}</code>):</b>

<b>Betreff:</b> {draft_subject}

{draft_body}
---
<i>Antworten Sie auf diese Nachricht, um den Entwurf zu bearbeiten, oder senden Sie <code>/confirm {draft_id}</code> zum Senden.</i>
    """
    try:
        await bot.send_message(chat_id=user_id, text=message, parse_mode=ParseMode.HTML)
        logger.info(f"Successfully sent notification for email {email['id']} to user {user_id}.")
    except TelegramError as e:
        logger.error(f"Failed to send Telegram notification to {user_id}: {e}")

async def main():
    """Main polling loop to check for emails and trigger the workflow."""
    logger.info("Starting Email Poller Service...")

    # --- Initialization ---
    try:
        settings = get_settings()
        if not settings.telegram.admin_ids:
            logger.critical("No admin_ids found in the configuration. Cannot send notifications.")
            return
        
        notification_user_id = settings.telegram.admin_ids[0]
        bot_token = settings.app.TELEGRAM_BOT_TOKEN
        if not bot_token:
            raise ValueError("TELEGRAM_BOT_TOKEN not set.")

        bot = Bot(token=bot_token)
        email_service = EmailService('gmail')
        agent = Agent() # The agent will be used for drafting replies
        
    except Exception as e:
        logger.critical(f"Email Poller failed to initialize: {e}")
        return

    processed_emails = load_processed_emails()
    logger.info(f"Loaded {len(processed_emails)} previously processed email IDs.")

    # --- Polling Loop ---
    while True:
        try:
            logger.debug("Checking for unread emails...")
            unread_emails = await asyncio.to_thread(email_service.list_unread_emails)

            new_emails = [email for email in unread_emails if email['id'] not in processed_emails]

            if new_emails:
                logger.info(f"Found {len(new_emails)} new email(s).")
                for email in new_emails:
                    email_id = email['id']
                    logger.info(f"Processing new email with ID: {email_id}")
                    
                    # Generate draft using the agent
                    draft_id = await email_service.draft_reply(
                        original_email_id=email_id,
                        agent=agent
                    )
                    draft_content = email_service.get_draft(draft_id)
                    if not draft_content:
                        logger.error(f"Could not retrieve draft content for {draft_id}")
                        continue
                    
                    draft_content['id'] = draft_id # Add id for the notification

                    # Send notification to Telegram
                    await notify_user(bot, notification_user_id, email, draft_content)

                    # Mark as processed
                    processed_emails.add(email_id)
                    save_processed_email(email_id)
            else:
                logger.debug("No new emails found.")

        except Exception as e:
            logger.error(f"An error occurred in the polling loop: {e}", exc_info=True)

        await asyncio.sleep(POLL_INTERVAL_SECONDS)

if __name__ == "__main__":
    asyncio.run(main())
