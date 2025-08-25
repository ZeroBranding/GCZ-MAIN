import asyncio
import random
from typing import Any, Dict, List, Optional

import yaml
from pathlib import Path

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from services.document_service import DocumentService
from core.workflows.types import Step, StepType, DocumentStepConfig
from core.errors import WorkflowError


class WorkflowEngine:
    def __init__(self, workflow_path: Path):
        self.workflow_path = workflow_path
        self.workflow: Workflow = self._load_workflow()
        self.scheduler = AsyncIOScheduler()
        self.scheduled_jobs = {}
        self.document_service = DocumentService()

    def _load_workflow(self) -> Workflow:
        with open(self.workflow_path, 'r') as f:
            data = yaml.safe_load(f)
        return Workflow(**data)

    def _resolve_variables(self, command: List[str]) -> List[str]:
        resolved_command = []
        for part in command:
            for var_name, var_value in self.workflow.variables.items():
                part = part.replace(f'${{{var_name}}}', str(var_value))
            resolved_command.append(part)
        return resolved_command

    def _validate_dependencies(self):
        step_names = {step.name for step in self.workflow.steps}
        for step in self.workflow.steps:
            if step.dependencies:
                for dep in step.dependencies:
                    if dep not in step_names:
                        raise ValueError(f"Dependency '{dep}' for step '{step.name}' not found.")

    def plan(self) -> List[Dict[str, Any]]:
        self._validate_dependencies()

        # Simple topological sort (for now, assumes no cycles)
        planned_steps = []
        steps_to_plan = self.workflow.steps.copy()

        while steps_to_plan:
            planned_this_round = []
            for step in steps_to_plan:
                dependencies_met = all(
                    dep.name in [p['name'] for p in planned_steps]
                    for dep_name in (step.dependencies or [])
                    for dep in self.workflow.steps if dep.name == dep_name
                )

                if not step.dependencies or dependencies_met:
                    resolved_command = self._resolve_variables(step.command)
                    planned_steps.append({
                        "name": step.name,
                        "command": resolved_command,
                        "artifacts_in": [self._resolve_variables([p])[0] for p in step.artifacts_in],
                        "artifacts_out": [self._resolve_variables([p])[0] for p in step.artifacts_out],
                    })
                    planned_this_round.append(step)

            if not planned_this_round:
                raise ValueError("Circular dependency detected in workflow.")

            for step in planned_this_round:
                steps_to_plan.remove(step)

        return planned_steps

    async def execute_with_retry(
        self,
        workflow_id: str,
        max_retries: int = 3,
        initial_delay: float = 1.0
    ) -> Optional[dict]:
        """Führt Workflow mit automatischen Retries aus"""
        attempt = 0
        while attempt < max_retries:
            try:
                result = await self.execute_workflow(workflow_id)
                return result
            except Exception as e:
                attempt += 1
                if attempt == max_retries:
                    raise
                
                # Exponential Backoff mit Jitter
                delay = initial_delay * (2 ** attempt) + random.uniform(0, 0.1)
                await asyncio.sleep(delay)
                
                # Logging
                self.logger.warning(
                    f"Workflow {workflow_id} failed (attempt {attempt}/{max_retries}): {str(e)}"
                )

        return None

    async def execute_step(self, step: Step) -> dict:
        """Führt einen einzelnen Workflow-Schritt aus."""
        if step.type == StepType.DOCUMENT_EXTRACT:
            config = DocumentStepConfig(**step.config)
            text = self.document_service.extract_text_from_pdf(config.input_path)
            metadata = self.document_service.extract_metadata(config.input_path)
            return {"text": text, "metadata": metadata}
            
        elif step.type == StepType.DOCUMENT_CONVERT:
            # Hier könnte Logik stehen, um z.B. PDF in Bilder umzuwandeln
            config = DocumentStepConfig(**step.config)
            # Beispiel: self.document_service.convert_pdf_to_images(...)
            return {"status": "conversion_placeholder"}
            
        # Fügen Sie hier weitere Step-Handler hinzu
        
        # Fallback für unbekannte Typen
        raise ValueError(f"Unbekannter Step-Typ: {step.type}")

    async def schedule_workflow(
        self, 
        workflow_id: str, 
        cron_expression: str,
        max_retries: int = 3
    ) -> str:
        """Plant regelmäßige Workflow-Ausführung"""
        job_id = f"{workflow_id}_{cron_expression}"
        
        if job_id in self.scheduled_jobs:
            raise ValueError(f"Job {job_id} bereits geplant")
        
        trigger = CronTrigger.from_crontab(cron_expression)
        job = self.scheduler.add_job(
            self.execute_with_retry,
            trigger,
            args=[workflow_id, max_retries]
        )
        
        self.scheduled_jobs[job_id] = job
        return job_id

    async def cancel_scheduled_workflow(self, job_id: str) -> bool:
        """Beendet geplanten Workflow"""
        if job_id not in self.scheduled_jobs:
            return False
            
        self.scheduled_jobs[job_id].remove()
        del self.scheduled_jobs[job_id]
        return True
