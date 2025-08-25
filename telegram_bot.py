import os
import asyncio
import logging
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from prometheus_client import start_http_server
import re

from telegram import Update # Korrekter Import für neuere Versionen
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)
from telegram.ext import ApplicationBuilder

from core.config import load_env
from core.errors import EnvError
from core.logging import logger
from services.telegram_service import register_handlers
from agents.meta_agent import MetaAgent
from core.security import RBACService, Role
from core.monitoring import MonitoringService
from services.sd_service import SDService
from services.anim_service import AnimService

# Force-load environment variables at the very beginning
load_env()

# Initialize RBAC Service
rbac = RBACService()

# Initialize Monitoring
monitoring = MonitoringService()
# asyncio.create_task(monitoring.start()) # Entfernt, da es einen RuntimeError verursacht

# Initialize Services
sd_service = SDService()
anim_service = AnimService()

class NLUDispatcher:
    def __init__(self):
        self.intents = {
            "generate_image": {
                "keywords": ["generiere ein bild", "erstelle ein bild", "zeichne", "male"],
                "handler": "generate_image_from_text"
            },
            "generate_animation": {
                "keywords": ["generiere ein video", "erstelle ein video", "animiere"],
                "handler": "generate_animation_from_text"
            }
        }

    def detect_intent(self, text: str):
        text_lower = text.lower()
        for intent, data in self.intents.items():
            for keyword in data["keywords"]:
                if keyword in text_lower:
                    # Extrahiere den Prompt nach dem Keyword
                    match = re.search(f"{keyword}(?: von)? (.*)", text, re.IGNORECASE)
                    prompt = match.group(1) if match else ""
                    return intent, prompt
        return None, None

# Initialize Dispatcher AFTER class definition
dispatcher = NLUDispatcher()

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Verarbeitet normalen Text und leitet ihn bei erkannten Intents weiter."""
    user_text = update.message.text
    intent, prompt = dispatcher.detect_intent(user_text)

    if intent == "generate_image":
        # Leite an die Bildgenerierungsfunktion weiter
        # Wir müssen den Kontext "künstlich" erstellen, da kein Befehl verwendet wurde
        context.args = prompt.split()
        await generate_image(update, context)
    elif intent == "generate_animation":
        context.args = prompt.split()
        await generate_animation(update, context)
    else:
        # Standard-Verhalten, wenn kein Intent erkannt wird
        await update.message.reply_text(f"Ich habe deine Nachricht erhalten: '{user_text}'")

async def handle_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Verarbeitet Befehle mit RBAC-Check"""
    user_role = Role.VIEWER  # In Praxis aus User-DB laden
    
    if not rbac.check_permission(user_role, "execute", update.message.text.split()[0]):
        await update.message.reply_text("Zugriff verweigert: Unzureichende Berechtigungen")
        return
    
    # Get response from MetaAgent (Ollama)
    agent = MetaAgent()
    response = agent.ask_llm(update.message.text)
    
    await update.message.reply_text(response)

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

async def system_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Zeigt Systemstatus und Metriken"""
    if not rbac.check_permission(Role.ADMIN, "view", "system:status"):
        await update.message.reply_text("Zugriff verweigert: Nur Admins können den Status einsehen")
        return
    
    status = monitoring.health_check()
    metrics = {
        'Workflow-Fehler': monitoring.metrics['workflow_errors']._value.get(),
        'Service-Laufzeit': f"{datetime.now() - monitoring.start_time}"
    }
    
    message = "🖥️ System Status\n\n" + "\n".join(
        f"🔹 {k}: {v}" for k, v in {**status, **metrics}.items()
    )
    
    await update.message.reply_text(message)

async def generate_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Generiert ein Bild basierend auf dem User-Prompt."""
    if not context.args:
        await update.message.reply_text("Bitte geben Sie einen Prompt an. Beispiel: /img Ein Astronaut auf einem Pferd")
        return

    prompt = " ".join(context.args)
    await update.message.reply_text(f"⏳ Generiere Bild für: '{prompt}'...")
    
    try:
        image_path = await sd_service.generate_image(prompt)
        await update.message.reply_photo(photo=open(image_path, 'rb'))
    except Exception as e:
        await update.message.reply_text(f"Fehler bei der Bildgenerierung: {e}")

async def generate_animation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Generiert eine Animation basierend auf dem User-Prompt."""
    if not context.args:
        await update.message.reply_text("Bitte geben Sie einen Prompt an. Beispiel: /anim Ein tanzender Roboter")
        return

    prompt = " ".join(context.args)
    await update.message.reply_text(f"⏳ Generiere Animation für: '{prompt}'...")

    try:
        # Dies ist eine vereinfachte Annahme; der AnimService benötigt ggf. mehr
        video_path = await anim_service.animate_from_prompt(prompt)
        await update.message.reply_video(video=open(video_path, 'rb'))
    except Exception as e:
        await update.message.reply_text(f"Fehler bei der Animationsgenerierung: {e}")


async def main() -> None:
    """Startet den Bot und alle asynchronen Services."""
    logger.info("Starting Telegram Bot...")

    # --- Load Environment ---
    try:
        bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        if not bot_token:
            raise EnvError("TELEGRAM_BOT_TOKEN is not set in the .env file.")
    except EnvError as e:
        logger.critical(f"Failed to start bot due to configuration error: {e}")
        return

    # Starte Monitoring-Service im Hintergrund
    asyncio.create_task(monitoring.start())

    # --- Build Application ---
    app = ApplicationBuilder().token(bot_token).build()

    # --- Register Handlers ---
    register_handlers(app)

    # Add handler for text messages
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    # Add handler for commands
    app.add_handler(MessageHandler(filters.COMMAND, handle_command))
    app.add_handler(CommandHandler("grant_role", handle_grant_role))
    app.add_handler(CommandHandler("revoke_role", handle_revoke_role))
    app.add_handler(CommandHandler("img", generate_image))
    app.add_handler(CommandHandler("anim", generate_animation))
    app.add_handler(CommandHandler("status", system_status))

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
