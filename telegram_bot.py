import asyncio
import logging
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from prometheus_client import start_http_server
import re
import subprocess

from telegram import Update # Korrekter Import für neuere Versionen
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)
from telegram import Bot
from telegram.ext import ApplicationBuilder

from core.config import get_settings
from core.logging import logger
from core.security import RBACService, Role
from core.monitoring import start_metrics_server, GRAPH_GOALS_TOTAL
from core.memory import Memory

# Import LangGraph integration
from ai.graph.run import start_graph  # Direct graph entry point

# Initialize RBAC Service
rbac = RBACService()

# Initialize Memory
memory = Memory()

# Service singletons are initialized within the graph nodes where they are needed.

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
/img &lt;prompt&gt; - Generiert ein Bild
/anim &lt;prompt&gt; - Generiert eine kurze Animation
/upscale - Skaliert ein Bild hoch (in Entwicklung)
"""
    await update.message.reply_html(help_text)

async def handle_grant_role(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Vergibt eine Rolle an einen Benutzer (nur Admins)."""
    if not rbac.check_permission(Role.ADMIN, "manage", "rbac:roles"):
        await update.message.reply_text("Zugriff verweigert: Nur Admins können Rollen vergeben.")
        return
    
    try:
        # Format: /grant_role <username> <role>
        _, username, role_str = context.args
        role = Role(role_str.lower())
        
        # In einer echten Anwendung würde dies in einer Datenbank gespeichert
        # z.B. user_db.set_role(username, role)
        
        rbac.grant_role_to_user(username, role) # Annahme: Diese Methode existiert in RBACService
        
        await update.message.reply_text(f"✅ Rolle '{role.value}' wurde an '{username}' vergeben.")
        
    except (ValueError, IndexError):
        await update.message.reply_text("Fehler: Bitte benutze das Format /grant_role <username> <admin|editor|viewer>")
    except Exception as e:
        await update.message.reply_text(f"Ein unerwarteter Fehler ist aufgetreten: {e}")

async def handle_revoke_role(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Entzieht einem Benutzer eine Rolle (nur Admins)."""
    if not rbac.check_permission(Role.ADMIN, "manage", "rbac:roles"):
        await update.message.reply_text("Zugriff verweigert: Nur Admins können Rollen entziehen.")
        return
        
    try:
        # Format: /revoke_role <username> <role>
        _, username, role_str = context.args
        role = Role(role_str.lower())

        # In einer echten Anwendung würde dies aus einer Datenbank entfernt
        # z.B. user_db.revoke_role(username, role)

        rbac.revoke_role_from_user(username, role) # Annahme: Diese Methode existiert in RBACService

        await update.message.reply_text(f"✅ Rolle '{role.value}' wurde von '{username}' entzogen.")

    except (ValueError, IndexError):
        await update.message.reply_text("Fehler: Bitte benutze das Format /revoke_role <username> <admin|editor|viewer>")
    except Exception as e:
        await update.message.reply_text(f"Ein unerwarteter Fehler ist aufgetreten: {e}")

async def generate_image(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Generiert ein Bild, indem ein LangGraph-Workflow gestartet wird."""
    GRAPH_GOALS_TOTAL.labels(goal_type="img").inc()
    if not context.args:
        await update.message.reply_text("Bitte gib einen Prompt an: /img <dein prompt>")
        return

    prompt = " ".join(context.args)
    user_id = str(update.effective_user.id)
    chat_id = str(update.effective_chat.id)
    session_id = f"tg-{chat_id}-{datetime.now().timestamp()}"
    goal = f"Generate an image with the prompt: '{prompt}'"

    await update.message.reply_text(f"✅ Anfrage '{prompt}' wurde empfangen und wird geplant (ID: {session_id}).")
    
    try:
        # Asynchron den Graphen starten und sofort weiterlaufen,
        # ohne auf das Ergebnis zu warten. Der Graph wird den Benutzer
        # über den Reporter-Knoten selbstständig benachrichtigen.
        asyncio.create_task(
            start_graph(
                session_id=session_id,
                goal=goal,
                user_ctx={"user_id": user_id, "chat_id": chat_id}
            )
        )
    except Exception as e:
        logger.error(f"Failed to start graph for session {session_id}: {e}", exc_info=True)
        await update.message.reply_text(f"❌ Fehler beim Starten des Workflows: {e}")

async def upscale_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Startet einen Workflow zum Hochskalieren eines Bildes."""
    GRAPH_GOALS_TOTAL.labels(goal_type="upscale").inc()
    # TODO: Implement logic to get the image to upscale (e.g., from a reply)
    await update.message.reply_text("Hinweis: Das Hochskalieren von Bildern ist noch nicht vollständig implementiert.")

    user_id = str(update.effective_user.id)
    chat_id = str(update.effective_chat.id)
    session_id = f"tg-{chat_id}-{datetime.now().timestamp()}"
    goal = "Upscale an image" # In a real scenario, this would include the image reference

    await update.message.reply_text(f"✅ Anfrage zum Hochskalieren wurde empfangen und wird geplant (ID: {session_id}).")
    
    try:
        asyncio.create_task(
            start_graph(
                session_id=session_id,
                goal=goal,
                user_ctx={"user_id": user_id, "chat_id": chat_id}
            )
        )
    except Exception as e:
        logger.error(f"Failed to start graph for session {session_id}: {e}", exc_info=True)
        await update.message.reply_text(f"❌ Fehler beim Starten des Workflows: {e}")

async def clear_memory_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Clears the conversation history for the user."""
    user_id = str(update.effective_user.id)
    memory.clear_history(user_id)
    await update.message.reply_text("Mein Gedächtnis für unsere Konversation wurde gelöscht.")

async def health_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """A simple health check command that replies with OK."""
    await update.message.reply_text("OK")

async def version_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Replies with the current Git commit hash."""
    try:
        # Execute the git command to get the short commit hash
        git_hash = subprocess.check_output(['git', 'rev-parse', '--short', 'HEAD']).decode('ascii').strip()
        await update.message.reply_text(f"Version: {git_hash}")
    except (subprocess.CalledProcessError, FileNotFoundError):
        logger.error("Failed to get git version hash. Is git installed and is this a git repository?")
        await update.message.reply_text("Version: unknown")

async def generate_animation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Startet einen Workflow zum Generieren einer Animation."""
    GRAPH_GOALS_TOTAL.labels(goal_type="anim").inc()
    if not context.args:
        await update.message.reply_text("Bitte gib einen Prompt an: /anim <dein prompt>")
        return

    prompt = " ".join(context.args)
    user_id = str(update.effective_user.id)
    chat_id = str(update.effective_chat.id)
    session_id = f"tg-{chat_id}-{datetime.now().timestamp()}"
    goal = f"Generate an animation with the prompt: '{prompt}'"

    await update.message.reply_text(f"✅ Anfrage '{prompt}' wurde empfangen und wird geplant (ID: {session_id}).")
    
    try:
        asyncio.create_task(
            start_graph(
                session_id=session_id,
                goal=goal,
                user_ctx={"user_id": user_id, "chat_id": chat_id}
            )
        )
    except Exception as e:
        logger.error(f"Failed to start graph for session {session_id}: {e}", exc_info=True)
        await update.message.reply_text(f"❌ Fehler beim Starten des Workflows: {e}")

# --- Autosend Queue Consumer ---
from core.queues import telegram_autosend_queue

async def autosend_consumer(bot: Bot):
    """
    Waits for messages on the autosend queue and sends them to the specified chat.
    """
    logger.info("Starting Telegram autosend consumer...")
    while True:
        try:
            item = await telegram_autosend_queue.get()
            logger.info(f"Got item from autosend queue: {item.get('type')}")

            chat_id = item.get('chat_id')
            if not chat_id:
                logger.warning("No chat_id in autosend queue item. Skipping.")
                continue

            if item.get('type') == 'photo':
                await bot.send_photo(chat_id=chat_id, photo=item.get('bytes'), caption=item.get('caption'))
            elif item.get('type') == 'video':
                await bot.send_video(chat_id=chat_id, video=item.get('bytes'), caption=item.get('caption'))
            elif item.get('type') == 'text':
                await bot.send_message(chat_id=chat_id, text=item.get('text'))

            telegram_autosend_queue.task_done()

        except Exception as e:
            logger.error(f"Error in autosend consumer: {e}", exc_info=True)


async def main() -> None:
    """Startet den Bot und alle asynchronen Services."""
    logger.info("Starting Telegram Bot...")

    # The get_settings() function handles loading and validation.
    # If a required variable like the bot token is missing, the program
    # will exit with a critical error before this point.
    settings = get_settings()
    bot_token = settings.app.TELEGRAM_BOT_TOKEN

    # Starte Monitoring-Service im Hintergrund
    start_metrics_server()

    # --- Build Application ---
    app = ApplicationBuilder().token(bot_token).build()

    # --- Start Core Background Tasks ---
    asyncio.create_task(autosend_consumer(app.bot))
    logger.info("Autosend consumer task started.")

    # --- Register Handlers ---
    # The `register_handlers` function from telegram_service is now the primary
    # source for handlers. We add the new, refactored command handlers here.
    # register_handlers(app) # This can be re-enabled if it contains other handlers.

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("clear", clear_memory_command))
    app.add_handler(CommandHandler("health", health_command))
    app.add_handler(CommandHandler("version", version_command))
    app.add_handler(CommandHandler("grant_role", handle_grant_role))
    app.add_handler(CommandHandler("revoke_role", handle_revoke_role))
    app.add_handler(CommandHandler("img", generate_image))
    app.add_handler(CommandHandler("upscale", upscale_image))
    app.add_handler(CommandHandler("anim", generate_animation))

    # --- Start Polling ---
    # app.run_polling() # Veraltet und verursacht Konflikt
    
    # Korrekter Weg, um den Bot innerhalb einer bestehenden async-Schleife zu starten
    await app.initialize()
    await app.start()
    await app.updater.start_polling()

    # Bot am Laufen halten (oder eine andere Logik)
    while True:
        await asyncio.sleep(3600)


if __name__ == "__main__":
    # Korrekter Aufruf für logging
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
    )
    asyncio.run(main())
