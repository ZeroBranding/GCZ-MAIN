from typing import Dict, Optional

from ai.graph.state import GraphState, PlanItem, StepStatus, ErrorSeverity
from core.config import load_config, GraphConfig
from core.logging import logger


class DeciderNode:
    """
    Entscheidet welcher Step als nächstes ausgeführt werden soll.
    Berücksichtigt Dependencies, Retry-Logic, Ressourcen und Policies.
    """
    
    def __init__(self):
        try:
            self.config = load_config('graph', GraphConfig)
        except Exception as e:
            logger.warning(f"Could not load graph config: {e}, using defaults")
            self.config = None
        
        # Fallback-Konfiguration
        self.max_steps = getattr(self.config, 'max_steps', 20) if self.config else 20
        self.max_parallel_gpu_tasks = getattr(self.config, 'max_parallel_gpu_tasks', 1) if self.config else 1
        self.retry_budget = getattr(self.config, 'retry_budget', 10) if self.config else 10
    
    def __call__(self, state: GraphState) -> Dict[str, any]:
        """
        LangGraph node entry point. Entscheidet nächsten Step.
        
        Returns:
            - "next_step": PlanItem oder None
            - "should_continue": bool 
            - "reason": str (für Debugging)
        """
        logger.info(f"Deciding next step for session {state.session_id}")
        
        # 1. Prüfe globale Completion-Bedingungen
        completion_check = self._check_completion(state)
        if completion_check['completed']:
            return {
                "next_step": None,
                "should_continue": False,
                "reason": completion_check['reason']
            }
        
        # 2. Prüfe Fehler-Bedingungen
        error_check = self._check_error_conditions(state)
        if error_check['should_stop']:
            return {
                "next_step": None,
                "should_continue": False,
                "reason": error_check['reason']
            }
        
        # 3. Wähle nächsten ausführbaren Step
        next_step = self._select_next_step(state)
        if next_step is None:
            return {
                "next_step": None,
                "should_continue": False,
                "reason": "No executable steps remaining"
            }
        
        # 4. Prüfe Ressourcen-Verfügbarkeit
        resource_check = self._check_resources(next_step, state)
        if not resource_check['available']:
            return {
                "next_step": None,
                "should_continue": True,
                "reason": f"Resources not available: {resource_check['reason']}"
            }
        
        logger.info(f"Selected next step: {next_step.action} (id: {next_step.id})")
        return {
            "next_step": next_step,
            "should_continue": True,
            "reason": f"Executing {next_step.action}"
        }
    
    def _check_completion(self, state: GraphState) -> Dict[str, any]:
        """Prüft ob der Workflow abgeschlossen ist."""
        
        # Bereits als completed markiert
        if state.is_completed:
            return {"completed": True, "reason": "Workflow marked as completed"}
        
        # Alle Steps completed
        if state.plan:
            completed_steps = [item for item in state.plan if item.status == StepStatus.COMPLETED]
            if len(completed_steps) == len(state.plan):
                return {"completed": True, "reason": "All plan items completed"}
        
        # Keine Steps im Plan
        if not state.plan:
            return {"completed": True, "reason": "No plan items to execute"}
        
        # Max steps erreicht (Sicherheit gegen Endlos-Loops)
        if state.current_step >= self.max_steps:
            return {"completed": True, "reason": f"Maximum steps ({self.max_steps}) reached"}
        
        return {"completed": False, "reason": "Workflow not yet completed"}
    
    def _check_error_conditions(self, state: GraphState) -> Dict[str, any]:
        """Prüft ob der Workflow wegen Fehlern gestoppt werden sollte."""
        
        # Bereits als failed markiert
        if state.is_failed:
            return {"should_stop": True, "reason": "Workflow marked as failed"}
        
        # Kritische Fehler
        if state.has_critical_errors():
            return {"should_stop": True, "reason": "Critical errors present"}
        
        # Retry-Budget aufgebraucht
        if not state.can_retry():
            return {"should_stop": True, "reason": "Retry budget exhausted"}
        
        # Zu viele fehlgeschlagene Steps
        failed_steps = state.get_failed_steps()
        if len(failed_steps) > len(state.plan) * 0.5:  # Mehr als 50% failed
            return {"should_stop": True, "reason": "Too many failed steps"}
        
        return {"should_stop": False, "reason": "No error conditions detected"}
    
    def _select_next_step(self, state: GraphState) -> Optional[PlanItem]:
        """Wählt den nächsten ausführbaren Step aus."""
        
        # 1. Prüfe auf Retry-kandidaten (Failed steps mit verfügbaren Retries)
        for item in state.plan:
            if (item.status == StepStatus.FAILED and 
                item.retry_count < item.max_retries):
                logger.info(f"Retrying failed step: {item.action} (attempt {item.retry_count + 1})")
                return item
        
        # 2. Finde nächsten PENDING step dessen Dependencies erfüllt sind
        for item in state.plan:
            if item.status == StepStatus.PENDING:
                if self._dependencies_satisfied(item, state):
                    return item
        
        # 3. Keine ausführbaren Steps gefunden
        return None
    
    def _dependencies_satisfied(self, item: PlanItem, state: GraphState) -> bool:
        """Prüft ob alle Dependencies eines Steps erfüllt sind."""
        
        if not item.dependencies:
            return True
        
        # Alle Dependency-Steps müssen COMPLETED sein
        completed_step_ids = {
            step.id for step in state.plan 
            if step.status == StepStatus.COMPLETED
        }
        
        return all(dep_id in completed_step_ids for dep_id in item.dependencies)
    
    def _check_resources(self, step: PlanItem, state: GraphState) -> Dict[str, any]:
        """Prüft Ressourcen-Verfügbarkeit für einen Step."""
        
        # GPU-Ressourcen prüfen
        if self._requires_gpu(step):
            running_gpu_tasks = sum(
                1 for item in state.plan 
                if item.status == StepStatus.RUNNING and self._requires_gpu(item)
            )
            
            if running_gpu_tasks >= self.max_parallel_gpu_tasks:
                return {
                    "available": False,
                    "reason": f"GPU slots full ({running_gpu_tasks}/{self.max_parallel_gpu_tasks})"
                }
        
        # Weitere Ressourcen-Checks können hier hinzugefügt werden
        # - Disk space
        # - Memory
        # - Network bandwidth
        # - API rate limits
        
        return {"available": True, "reason": "Resources available"}
    
    def _requires_gpu(self, step: PlanItem) -> bool:
        """Prüft ob ein Step GPU-Ressourcen benötigt."""
        gpu_actions = {
            'txt2img', 'img2img', 'upscale', 'anim', 
            'avatar', 'style_transfer'
        }
        return step.action in gpu_actions
    
    def _get_step_priority(self, step: PlanItem) -> int:
        """Gibt Priorität eines Steps zurück (niedrigere Zahl = höhere Priorität)."""
        
        # Basis-Prioritäten nach Action-Type
        action_priorities = {
            'txt2img': 1,
            'img2img': 1, 
            'upscale': 2,
            'anim': 3,
            'asr': 1,
            'tts': 1,
            'upload_youtube': 4,
            'upload_tiktok': 4,
            'upload_instagram': 4
        }
        
        base_priority = action_priorities.get(step.action, 5)
        
        # Retry-Penalty: höhere retry_count = niedrigere Priorität
        retry_penalty = step.retry_count * 2
        
        return base_priority + retry_penalty
    
    def should_run_in_parallel(self, step: PlanItem, state: GraphState) -> bool:
        """
        Entscheidet ob ein Step parallel zu anderen laufen kann.
        Future: für parallele Execution von unabhängigen Steps.
        """
        
        # GPU-Tasks sollten nicht parallel laufen (Ressourcen-Konflikte)
        if self._requires_gpu(step):
            return False
        
        # Upload-Tasks können parallel laufen
        if step.action.startswith('upload_'):
            return True
        
        # Audio-Processing kann parallel laufen
        if step.action in ['asr', 'tts']:
            return True
        
        # Default: sequenziell
        return False