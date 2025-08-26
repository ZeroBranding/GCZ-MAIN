"""Workflow Engine - Bridge between LangGraph and service execution."""
import asyncio
import yaml
import json
from typing import Dict, Any, Optional, Union
from pathlib import Path
from datetime import datetime
import hashlib
import os
from core.logging import logger

class WorkflowEngine:
    """Simple workflow engine for executing service workflows."""
    
    def __init__(self):
        self.workflows: Dict[str, Dict] = {}
        self.executions: Dict[str, Dict] = {}
        
    async def submit(
        self, 
        workflow: Union[str, Dict], 
        correlation_id: Optional[str] = None,
        context: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Submit a workflow for execution.
        
        Args:
            workflow: Either a YAML string or a dict specification
            correlation_id: Unique ID for idempotent execution
            context: Additional context for the workflow
            
        Returns:
            Execution result with status and outputs
        """
        # Parse workflow if it's YAML
        if isinstance(workflow, str):
            try:
                spec = yaml.safe_load(workflow)
            except yaml.YAMLError as e:
                logger.error(f"Failed to parse YAML workflow: {e}")
                return {"status": "error", "error": str(e)}
        else:
            spec = workflow
            
        # Generate correlation ID if not provided
        if not correlation_id:
            correlation_id = hashlib.md5(
                f"{spec}{datetime.now().isoformat()}".encode()
            ).hexdigest()
            
        # Check for idempotent execution
        if correlation_id in self.executions:
            logger.info(f"Returning cached result for {correlation_id}")
            return self.executions[correlation_id]
            
        # Execute workflow
        result = await self._execute_workflow(spec, context or {})
        
        # Cache result
        self.executions[correlation_id] = result
        
        return result
        
    async def _execute_workflow(
        self, 
        spec: Dict[str, Any], 
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute a workflow specification."""
        logger.info(f"Executing workflow: {spec.get('name', 'unnamed')}")
        
        steps = spec.get("steps", [])
        outputs = {}
        
        # Get workspace path
        workspace_path = os.environ.get("WORKSPACE_PATH", "/workspace")
        artifacts_dir = Path(workspace_path) / "artifacts"
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        
        for step in steps:
            step_name = step.get("name", "unnamed_step")
            step_type = step.get("type")
            params = step.get("params", {})
            
            # Inject context into params
            params.update(context)
            
            logger.info(f"Executing step: {step_name} ({step_type})")
            
            try:
                # Simulate service execution
                # In real implementation, this would call actual services
                if step_type == "txt2img":
                    outputs[step_name] = {
                        "image_path": str(artifacts_dir / f"generated_{params.get('prompt', 'image')[:20].replace(' ', '_')}.png"),
                        "prompt": params.get("prompt")
                    }
                elif step_type == "upscale":
                    input_image = params.get("input", outputs.get(params.get("from_step", ""), {}).get("image_path"))
                    outputs[step_name] = {
                        "image_path": str(artifacts_dir / f"upscaled_{Path(input_image).stem if input_image else 'image'}.png"),
                        "scale": params.get("scale", 2)
                    }
                else:
                    outputs[step_name] = {"result": f"Executed {step_type}"}
                    
            except Exception as e:
                logger.error(f"Step {step_name} failed: {e}")
                return {
                    "status": "error",
                    "failed_step": step_name,
                    "error": str(e),
                    "partial_outputs": outputs
                }
                
        return {
            "status": "success",
            "outputs": outputs,
            "workflow": spec.get("name", "unnamed")
        }

# Global engine instance
_engine = WorkflowEngine()

async def submit(workflow: Union[str, Dict], correlation_id: Optional[str] = None, **kwargs) -> Dict[str, Any]:
    """Submit a workflow for execution."""
    return await _engine.submit(workflow, correlation_id, kwargs)