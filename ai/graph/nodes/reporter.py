from pathlib import Path
from typing import Dict, List

from ai.graph.state import GraphState, ArtifactInfo, StepStatus
from core.logging import logger


class ReporterNode:
    """
    Sendet finale Ergebnisse an den Telegram Service.
    Bereitet Artifacts und Status-Nachrichten für die Ausgabe vor.
    """
    
    def __init__(self):
        # Lazy import um zirkuläre Dependencies zu vermeiden
        self._telegram_service = None
        
        # Konfiguration für verschiedene Report-Types
        self.report_config = {
            'max_artifacts_per_message': 5,
            'max_message_length': 4000,
            'include_execution_stats': True,
            'include_error_summary': True
        }
    
    def __call__(self, state: GraphState) -> Dict[str, any]:
        """
        LangGraph node entry point. Sendet finale Ergebnisse.
        """
        logger.info(f"Reporting results for session {state.session_id}")
        
        try:
            # Report-Daten vorbereiten
            report_data = self._prepare_report(state)
            
            # An Telegram senden
            if state.user.telegram_chat_id:
                sent_messages = self._send_telegram_report(
                    chat_id=state.user.telegram_chat_id,
                    report_data=report_data,
                    state=state
                )
                
                logger.info(f"Sent {len(sent_messages)} messages to Telegram")
                return {
                    "report_sent": True,
                    "messages_sent": len(sent_messages),
                    "artifacts_shared": len(report_data['artifacts'])
                }
            else:
                logger.warning("No Telegram chat_id available for reporting")
                return {
                    "report_sent": False,
                    "error": "No Telegram chat_id available"
                }
                
        except Exception as e:
            logger.error(f"Failed to send report: {e}")
            return {
                "report_sent": False,
                "error": str(e)
            }
    
    def _prepare_report(self, state: GraphState) -> Dict:
        """Bereitet Report-Daten vor."""
        
        # Artifacts gruppieren
        artifacts_by_type = self._group_artifacts_by_type(state.artifacts)
        
        # Execution-Statistiken
        completed_steps = [item for item in state.plan if item.status == StepStatus.COMPLETED]
        failed_steps = [item for item in state.plan if item.status == StepStatus.FAILED]
        
        total_execution_time = sum(
            (item.completed_at - item.started_at).total_seconds()
            for item in completed_steps
            if item.started_at and item.completed_at
        )
        
        # Status-Nachricht erstellen
        status_message = self._create_status_message(state, completed_steps, failed_steps, total_execution_time)
        
        return {
            'status_message': status_message,
            'artifacts': state.artifacts,
            'artifacts_by_type': artifacts_by_type,
            'execution_stats': {
                'total_steps': len(state.plan),
                'completed_steps': len(completed_steps),
                'failed_steps': len(failed_steps),
                'total_execution_time_s': total_execution_time,
                'retry_count': state.used_retries
            },
            'errors': state.errors
        }
    
    def _create_status_message(self, state: GraphState, completed_steps: List, failed_steps: List, total_time: float) -> str:
        """Erstellt die Status-Nachricht."""
        
        # Header mit Goal
        message_lines = [
            f"🎯 **Aufgabe abgeschlossen**",
            f"Goal: `{state.goal}`",
            ""
        ]
        
        # Success/Failure Status
        if state.is_completed and not failed_steps:
            message_lines.append("✅ **Status: Erfolgreich**")
        elif failed_steps:
            message_lines.append("⚠️ **Status: Teilweise erfolgreich**")
        else:
            message_lines.append("❌ **Status: Fehlgeschlagen**")
        
        message_lines.append("")
        
        # Execution Stats
        if self.report_config.get('include_execution_stats', True):
            message_lines.extend([
                "📊 **Statistiken:**",
                f"• Steps: {len(completed_steps)}/{len(state.plan)} abgeschlossen",
                f"• Zeit: {total_time:.1f}s",
                f"• Retries: {state.used_retries}"
            ])
            
            if state.artifacts:
                artifacts_summary = self._create_artifacts_summary(state.artifacts)
                message_lines.extend(["• Artifacts:"] + artifacts_summary)
            
            message_lines.append("")
        
        # Error Summary
        if failed_steps and self.report_config.get('include_error_summary', True):
            message_lines.extend([
                "⚠️ **Probleme:**"
            ])
            
            for step in failed_steps[-3:]:  # Zeige nur die letzten 3 Fehler
                step_errors = [e for e in state.errors if e.step_id == step.id]
                if step_errors:
                    error_msg = step_errors[-1].message[:100]  # Kurze Fehlermeldung
                    message_lines.append(f"• {step.action}: {error_msg}")
            
            message_lines.append("")
        
        # Session Info
        message_lines.extend([
            f"🔗 Session: `{state.session_id[:8]}...`",
            f"⏱️ Erstellt: {state.created_at.strftime('%H:%M:%S')}"
        ])
        
        return "\n".join(message_lines)
    
    def _create_artifacts_summary(self, artifacts: List[ArtifactInfo]) -> List[str]:
        """Erstellt Zusammenfassung der Artifacts."""
        
        by_type = self._group_artifacts_by_type(artifacts)
        summary = []
        
        for artifact_type, items in by_type.items():
            if artifact_type == 'image':
                summary.append(f"  📸 {len(items)} Bilder")
            elif artifact_type == 'video':
                summary.append(f"  🎥 {len(items)} Videos")
            elif artifact_type == 'audio':
                summary.append(f"  🎵 {len(items)} Audio-Dateien")
            elif artifact_type == 'document':
                summary.append(f"  📄 {len(items)} Dokumente")
            else:
                summary.append(f"  📁 {len(items)} {artifact_type}")
        
        return summary
    
    def _group_artifacts_by_type(self, artifacts: List[ArtifactInfo]) -> Dict[str, List[ArtifactInfo]]:
        """Gruppiert Artifacts nach Typ."""
        
        by_type = {}
        for artifact in artifacts:
            if artifact.type not in by_type:
                by_type[artifact.type] = []
            by_type[artifact.type].append(artifact)
        
        return by_type
    
    def _send_telegram_report(self, chat_id: int, report_data: Dict, state: GraphState) -> List[str]:
        """Sendet Report an Telegram."""
        
        sent_messages = []
        
        try:
            # Lazy load telegram service
            if self._telegram_service is None:
                from services.telegram_service import send_message, send_media_group
                self._send_message = send_message
                self._send_media_group = send_media_group
            
            # 1. Status-Nachricht senden
            if report_data['status_message']:
                message_id = self._send_message(
                    chat_id=chat_id,
                    text=report_data['status_message'],
                    parse_mode='Markdown'
                )
                sent_messages.append(f"status_{message_id}")
            
            # 2. Artifacts senden (gruppiert nach Typ)
            artifacts_sent = self._send_artifacts(chat_id, report_data['artifacts_by_type'])
            sent_messages.extend(artifacts_sent)
            
            # 3. Fehler-Details senden (falls vorhanden und nicht zu lang)
            if report_data['errors'] and len(report_data['errors']) <= 3:
                error_message = self._create_error_details_message(report_data['errors'])
                if error_message and len(error_message) < self.report_config['max_message_length']:
                    message_id = self._send_message(
                        chat_id=chat_id,
                        text=error_message,
                        parse_mode='Markdown'
                    )
                    sent_messages.append(f"errors_{message_id}")
            
            return sent_messages
            
        except Exception as e:
            logger.error(f"Failed to send Telegram report: {e}")
            # Fallback: Minimale Nachricht
            try:
                message_id = self._send_message(
                    chat_id=chat_id,
                    text=f"❌ Fehler beim Senden des Reports: {str(e)[:200]}"
                )
                return [f"error_{message_id}"]
            except:
                return []
    
    def _send_artifacts(self, chat_id: int, artifacts_by_type: Dict) -> List[str]:
        """Sendet Artifacts gruppiert nach Typ."""
        
        sent_messages = []
        
        # Bilder als Media Group senden
        if 'image' in artifacts_by_type:
            image_groups = self._chunk_artifacts(
                artifacts_by_type['image'], 
                self.report_config['max_artifacts_per_message']
            )
            
            for group in image_groups:
                media_paths = [str(artifact.path) for artifact in group if artifact.path.exists()]
                if media_paths:
                    try:
                        message_id = self._send_media_group(
                            chat_id=chat_id,
                            media_paths=media_paths,
                            media_type='photo'
                        )
                        sent_messages.append(f"images_{message_id}")
                    except Exception as e:
                        logger.error(f"Failed to send image group: {e}")
        
        # Videos einzeln senden (meist zu groß für Media Groups)
        if 'video' in artifacts_by_type:
            for artifact in artifacts_by_type['video']:
                if artifact.path.exists():
                    try:
                        message_id = self._send_message(
                            chat_id=chat_id,
                            video=str(artifact.path),
                            caption=f"🎥 {artifact.path.name}"
                        )
                        sent_messages.append(f"video_{message_id}")
                    except Exception as e:
                        logger.error(f"Failed to send video {artifact.path}: {e}")
        
        # Audio-Dateien
        if 'audio' in artifacts_by_type:
            for artifact in artifacts_by_type['audio']:
                if artifact.path.exists():
                    try:
                        message_id = self._send_message(
                            chat_id=chat_id,
                            audio=str(artifact.path),
                            caption=f"🎵 {artifact.path.name}"
                        )
                        sent_messages.append(f"audio_{message_id}")
                    except Exception as e:
                        logger.error(f"Failed to send audio {artifact.path}: {e}")
        
        # Dokumente
        if 'document' in artifacts_by_type:
            for artifact in artifacts_by_type['document']:
                if artifact.path.exists() and artifact.path.stat().st_size < 50_000_000:  # 50MB limit
                    try:
                        message_id = self._send_message(
                            chat_id=chat_id,
                            document=str(artifact.path),
                            caption=f"📄 {artifact.path.name}"
                        )
                        sent_messages.append(f"document_{message_id}")
                    except Exception as e:
                        logger.error(f"Failed to send document {artifact.path}: {e}")
        
        return sent_messages
    
    def _chunk_artifacts(self, artifacts: List[ArtifactInfo], chunk_size: int) -> List[List[ArtifactInfo]]:
        """Teilt Artifacts in Chunks auf."""
        
        chunks = []
        for i in range(0, len(artifacts), chunk_size):
            chunks.append(artifacts[i:i + chunk_size])
        
        return chunks
    
    def _create_error_details_message(self, errors: List) -> str:
        """Erstellt detaillierte Fehlermeldung."""
        
        if not errors:
            return ""
        
        message_lines = [
            "🔍 **Fehler-Details:**",
            ""
        ]
        
        for error in errors[-5:]:  # Zeige nur die letzten 5 Fehler
            timestamp = error.timestamp.strftime('%H:%M:%S')
            severity_emoji = {
                'warning': '⚠️',
                'error': '❌', 
                'critical': '🚨'
            }.get(error.severity.value, '❓')
            
            message_lines.extend([
                f"{severity_emoji} **{timestamp}** - {error.message[:200]}",
                ""
            ])
        
        return "\n".join(message_lines)