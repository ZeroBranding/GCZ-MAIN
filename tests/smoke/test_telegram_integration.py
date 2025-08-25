import pytest
from unittest.mock import AsyncMock, patch
from telegram_bot import handle_command, rbac
from core.security import Role

@pytest.mark.asyncio
async def test_telegram_rbac_denies_access():
    """Testet, ob RBAC den Zugriff für nicht-autorisierte Befehle verweigert."""
    update = AsyncMock()
    update.message.text = "/grant_role testuser editor"
    
    # Simuliere einen 'viewer'
    with patch.object(rbac, 'check_permission', return_value=False) as mock_check:
        await handle_command(update, AsyncMock())
        
        # Stelle sicher, dass die Berechtigungsprüfung aufgerufen wurde
        mock_check.assert_called_with(Role.VIEWER, "execute", "/grant_role")
        
        # Stelle sicher, dass eine "Zugriff verweigert"-Nachricht gesendet wurde
        update.message.reply_text.assert_called_with("Zugriff verweigert: Unzureichende Berechtigungen")

@pytest.mark.asyncio
async def test_telegram_rbac_allows_access():
    """Testet, ob RBAC den Zugriff für autorisierte Befehle erlaubt."""
    update = AsyncMock()
    update.message.text = "/status" # Ein Befehl, den jeder ausführen darf
    
    # Simuliere einen 'viewer', der diesen Befehl ausführen darf
    with patch.object(rbac, 'check_permission', return_value=True) as mock_check:
        # Mocke den MetaAgent, um nicht wirklich eine LLM-Anfrage zu senden
        with patch('telegram_bot.MetaAgent') as mock_agent:
            mock_agent.return_value.ask_llm.return_value = "Systemstatus ist OK."
            await handle_command(update, AsyncMock())
            
            mock_check.assert_called_with(Role.VIEWER, "execute", "/status")
            update.message.reply_text.assert_called_with("Systemstatus ist OK.")
