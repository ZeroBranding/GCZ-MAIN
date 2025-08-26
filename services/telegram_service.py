import asyncio
import re
from pathlib import Path

import core.env
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from agent.agent import Agent
from core.logging import logger
from core.memory import Memory
from services.anim_service import AnimService
from services.email_service import EmailService
from services.sd_service import SDService

# Import other services as needed...

# --- Paths ---
BASE_DIR = Path(__file__).resolve().parent.parent
ARTIFACTS_DIR = BASE_DIR / "artifacts"

# --- Service Initialization ---
# Initialize services that will be used by the handlers.
# Use a try-except block to handle potential init errors gracefully.
try:
    email_service = EmailService('gmail')
except Exception as e:
    logger.error(f"Failed to initialize EmailService: {e}")
    email_service = None

try:
    sd_service = SDService()
except Exception as e:
    logger.error(f"Failed to initialize SDService: {e}")
    sd_service = None

try:
    anim_service = AnimService()
except Exception as e:
    logger.error(f"Failed to initialize AnimService: {e}")
    anim_service = None

try:
    agent = Agent()
except Exception as e:
    logger.error(f"Failed to initialize Agent: {e}")
    agent = None

memory = Memory()

# --- Command Handlers ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a welcome message."""
    await update.message.reply_html(
        rf"Willkommen zum German Code Zero AI Bot, {update.effective_user.mention_html()}!",
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a help message."""
    help_text = """
<b>Verfügbare Befehle:</b>
/start - Startet den Bot
/help - Zeigt diese Hilfe an
/clear - Löscht den Konversationsverlauf

<b>E-Mail:</b>
/mail_list - Listet ungelesene E-Mails auf
/reply &lt;email_id&gt; - Erstellt einen Antwortentwurf
/confirm &lt;draft_id&gt; - Sendet einen E-Mail-Entwurf

<b>Inhaltserstellung:</b>
/img &lt;prompt&gt; - Generiert ein Bild
/anim &lt;prompt&gt; - Generiert eine kurze Animation
    """
    await update.message.reply_html(help_text)

async def clear_memory_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Clears the conversation history for the user."""
    user_id = str(update.effective_user.id)
    memory.clear_history(user_id)
    await update.message.reply_text("Mein Gedächtnis für unsere Konversation wurde gelöscht.")


# --- Email Command Handlers ---

async def mail_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Lists unread emails."""
    if not email_service:
        await update.message.reply_text("E-Mail-Dienst ist nicht verfügbar.")
        return

    await update.message.reply_text("Suche nach ungelesenen E-Mails...")
    try:
        unread_emails = await asyncio.to_thread(email_service.list_unread_emails)
        if not unread_emails:
            await update.message.reply_text("Keine ungelesenen E-Mails gefunden.")
            return

        message = "<b>Ungelesene E-Mails:</b>\n"
        for email in unread_emails[:10]:
            message += (
                f"- ID: <code>{email['id']}</code> | Von: {email['from']} | "
                f"Betreff: {email['subject']}\n"
            )
        await update.message.reply_html(message)
    except Exception as e:
        logger.error(f"Error listing emails: {e}")
        await update.message.reply_text("Fehler beim Abrufen der E-Mails.")

async def reply_to_email(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Creates a reply draft for an email."""
    if not email_service:
        await update.message.reply_text("E-Mail-Dienst ist nicht verfügbar.")
        return

    if not context.args or len(context.args) != 1:
        await update.message.reply_text("Verwendung: /reply <email_id>")
        return

    email_id = context.args[0]
    await update.message.reply_text(
        f"Erstelle Antwortentwurf für E-Mail-ID: {email_id}..."
    )
    try:
        draft_id = await asyncio.to_thread(email_service.draft_reply, email_id)
        reply = (f"Antwortentwurf erstellt mit ID: <code>{draft_id}</code>\n"
                 f"Verwenden Sie <code>/confirm {draft_id}</code> zum Senden.")
        await update.message.reply_html(reply)
    except Exception as e:
        logger.error(f"Error drafting reply: {e}")
        await update.message.reply_text(f"Fehler beim Erstellen des Entwurfs: {e}")

async def confirm_email_send(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Confirms and sends an email draft."""
    if not email_service:
        await update.message.reply_text("E-Mail-Dienst ist nicht verfügbar.")
        return

    if not context.args or len(context.args) != 1:
        await update.message.reply_text("Verwendung: /confirm <draft_id>")
        return

    draft_id = context.args[0]
    await update.message.reply_text(f"Sende E-Mail-Entwurf: {draft_id}...")
    try:
        result = await asyncio.to_thread(
            email_service.confirm_and_send, draft_id
        )
        if result == "OK":
            await update.message.reply_text(
                f"E-Mail-Entwurf {draft_id} wurde erfolgreich gesendet."
            )
        else:
            await update.message.reply_text(
                f"Problem beim Senden des Entwurfs: {result}"
            )
    except Exception as e:
        logger.error(f"Error sending email: {e}")
        await update.message.reply_text(f"Fehler beim Senden der E-Mail: {e}")

# --- Media Generation Handlers ---

async def img_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Generates an image from a prompt."""
    if not sd_service:
        await update.message.reply_text("Bildgenerierungs-Dienst ist nicht verfügbar.")
        return

    prompt = " ".join(context.args)
    if not prompt:
        await update.message.reply_text("Verwendung: /img <prompt>")
        return

    await update.message.reply_text(f"Generiere Bild für: '{prompt}'...")
    try:
        image_path_str = await asyncio.to_thread(sd_service.txt2img, prompt=prompt)
        await update.message.reply_photo(photo=Path(image_path_str))
    except Exception as e:
        logger.error(f"Error in /img command: {e}", exc_info=True)
        await update.message.reply_text(f"Fehler bei der Bildgenerierung: {e}")

async def anim_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Generates an animation from a prompt."""
    if not anim_service:
        await update.message.reply_text("Animations-Dienst ist nicht verfügbar.")
        return

    prompt = " ".join(context.args)
    if not prompt:
        await update.message.reply_text("Verwendung: /anim <prompt>")
        return

    await update.message.reply_text(f"Generiere Animation für: '{prompt}'...")
    try:
        plan = anim_service.plan_animation(prompt=prompt)
        video_path_str = await asyncio.to_thread(
            anim_service.render_animation, plan=plan
        )
        await update.message.reply_video(video=Path(video_path_str))
    except Exception as e:
        logger.error(f"Error in /anim command: {e}", exc_info=True)
        await update.message.reply_text(f"Fehler bei der Animationsgenerierung: {e}")


# --- Generic Message Handler ---

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles generic text messages and uses the agent for a conversational response."""
    # Check if the message is a reply to a draft notification
    if update.message.reply_to_message and "📄 <b>Antwortentwurf (ID:" in update.message.reply_to_message.text:
        await handle_draft_edit(update, context)
        return
        
    if not agent:
        await update.message.reply_text("Der Kern-Agent ist nicht verfügbar.")
        return

    user_id = str(update.effective_user.id)
    prompt = update.message.text

    # 1. Save user message to memory
    memory.add_message(user_id, "user", prompt)

    # 2. Get response from agent
    await update.message.chat.send_action(action="typing")
    try:
        # Pass the full history to the agent
        history = memory.get_history(user_id)
        response_text = await agent.execute_prompt(history) # aGENT expects history now

        # 3. Save agent response to memory
        memory.add_message(user_id, "assistant", response_text)

        # 4. Send response to user
        await update.message.reply_text(response_text)

    except Exception as e:
        logger.error(f"Error handling message: {e}", exc_info=True)
        await update.message.reply_text("Es ist ein Fehler aufgetreten. Bitte versuchen Sie es später erneut.")


async def handle_draft_edit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles user edits to an email draft."""
    if not email_service or not agent:
        await update.message.reply_text("E-Mail-Dienst oder Agent ist nicht verfügbar.")
        return

    original_bot_message = update.message.reply_to_message.text
    user_instruction = update.message.text

    # Extract draft_id from the original message text using regex
    match = re.search(r"ID: <code>(draft_[^<]+)</code>", original_bot_message)
    if not match:
        await update.message.reply_text("Konnte die Entwurfs-ID nicht finden, auf die Sie antworten.")
        return
    
    draft_id = match.group(1)
    await update.message.reply_text(f"Bearbeite Entwurf {draft_id} mit Ihrer Anweisung: '{user_instruction}'...")

    try:
        # This function needs to be created in EmailService
        new_draft_id = await email_service.edit_draft(
            original_draft_id=draft_id,
            edit_instruction=user_instruction,
            agent=agent
        )
        
        # Notify user with the new draft (similar to the poller's notification)
        # This would require fetching the original email details again, or storing them.
        # For now, we just send the new draft.
        new_draft_content = email_service.get_draft(new_draft_id)
        if new_draft_content:
            new_draft_content['id'] = new_draft_id
            message = f"""
✅ <b>Entwurf aktualisiert! (Neue ID: <code>{new_draft_id}</code>)</b>

{new_draft_content.get('body_text', '')}
---
<i>Antworten Sie erneut zum Bearbeiten, oder senden Sie <code>/confirm {new_draft_id}</code> zum Senden.</i>
            """
            await update.message.reply_html(message)
        else:
            await update.message.reply_text("Fehler beim Abrufen des neuen Entwurfs.")

    except Exception as e:
        logger.error(f"Error editing draft {draft_id}: {e}", exc_info=True)
        await update.message.reply_text(f"Fehler beim Bearbeiten des Entwurfs: {e}")


# --- Function to register all handlers ---
def register_handlers(app: Application):
    """Registers all command handlers with the Telegram application."""
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("clear", clear_memory_command))

    # Email handlers
    app.add_handler(CommandHandler("mail_list", mail_list))
    app.add_handler(CommandHandler("reply", reply_to_email))
    app.add_handler(CommandHandler("confirm", confirm_email_send))

    # Media handlers
    app.add_handler(CommandHandler("img", img_command))
    app.add_handler(CommandHandler("anim", anim_command))

    # Generic message handler - must be last
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("All Telegram handlers have been registered.")
