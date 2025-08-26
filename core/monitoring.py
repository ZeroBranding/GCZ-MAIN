
import logging
from datetime import datetime
import prometheus_client as prom
from fastapi import FastAPI
from prometheus_client import start_http_server
from typing import Dict, Any, List
from enum import Enum
import asyncio
import psutil # benötigt: pip install psutil

class MonitoringService:
    def __init__(self):
        self.app = FastAPI()
        self.start_time = datetime.now()
        self.metrics = {
            'workflow_errors': prom.Counter('workflow_errors_total', 'Total failed workflows'),
            'service_health': prom.Gauge('service_health', 'Service health status', ['service_name']),
            'telegram_commands': prom.Counter('telegram_commands', 'Processed commands', ['command'])
        }
        
    async def start(self):
        """Startet den Monitoring-Server"""
        # Bind to 127.0.0.1 to ensure the port is not exposed externally.
        start_http_server(9090, addr='127.0.0.1')
        logging.info("Monitoring-Service gestartet auf Port 9090 (localhost)")

    def log_error(self, service: str):
        """Protokolliert einen Service-Fehler"""
        self.metrics['workflow_errors'].inc()
        self.metrics['service_health'].labels(service_name=service).set(0)

    def log_command(self, command: str):
        """Protokolliert verarbeitete Telegram-Befehle"""
        self.metrics['telegram_commands'].labels(command=command).inc()

    def health_check(self) -> Dict[str, Any]:
        """Gibt Systemhealth-Status zurück"""
        return {
            'status': 'OK',
            'services': ['telegram', 'email', 'sd']
        }

class AlertLevel(Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"

class AlertSystem:
    def __init__(self, telegram_service, admin_chat_id: int):
        self.telegram_service = telegram_service
        self.admin_chat_id = admin_chat_id
        self.alert_rules = {
            "high_cpu": {"threshold": 90, "level": AlertLevel.CRITICAL, "active": False},
            "high_memory": {"threshold": 90, "level": AlertLevel.CRITICAL, "active": False},
            "workflow_failed": {"retries": 3, "level": AlertLevel.WARNING, "active": False}
        }
    
    async def check_system_metrics(self):
        """Überwacht Systemmetriken und löst bei Bedarf Alerts aus."""
        while True:
            cpu_percent = psutil.cpu_percent(interval=1)
            memory_percent = psutil.virtual_memory().percent
            
            await self._check_and_alert("high_cpu", cpu_percent)
            await self._check_and_alert("high_memory", memory_percent)
            
            await asyncio.sleep(60) # Alle 60 Sekunden prüfen

    async def trigger_workflow_alert(self, workflow_id: str, attempt: int):
        """Löst einen Alert für einen fehlgeschlagenen Workflow aus."""
        await self._check_and_alert("workflow_failed", attempt, workflow_id=workflow_id)

    async def _check_and_alert(self, metric: str, value: Any, **kwargs):
        rule = self.alert_rules.get(metric)
        if not rule:
            return

        should_alert = False
        message = ""

        if "threshold" in rule and value > rule["threshold"]:
            should_alert = True
            message = f"🚨 {rule['level'].value}: {metric.replace('_', ' ').title()} hat Schwellenwert überschritten: {value:.1f}%"
        elif "retries" in rule and value >= rule["retries"]:
            should_alert = True
            workflow_id = kwargs.get("workflow_id", "Unbekannt")
            message = f"⚠️ {rule['level'].value}: Workflow '{workflow_id}' ist nach {value} Versuchen fehlgeschlagen."

        # Alert nur senden, wenn er nicht bereits aktiv ist, um Spam zu vermeiden
        if should_alert and not rule["active"]:
            await self.telegram_service.send_message(self.admin_chat_id, message)
            rule["active"] = True
        elif not should_alert and rule["active"]:
            # Zustand zurücksetzen, wenn das Problem behoben ist
            rule["active"] = False
