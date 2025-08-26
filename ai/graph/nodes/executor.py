"""Executor node - Bridge between LangGraph and the workflow engine."""
import asyncio
import yaml
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime
import hashlib
import os

from core.workflow_engine import submit
from core.logging import logger

# Get workspace path
workspace_path = os.environ.get("WORKSPACE_PATH", "/workspace")
artifacts_dir = f"{workspace_path}/artifacts"

# Workflow templates for different step types
WORKFLOW_TEMPLATES = {
    "generate_image": """
name: generate_image
steps:
  - name: txt2img
    type: txt2img
    params:
      prompt: "{prompt}"
      model: "stable-diffusion"
      width: 512
      height: 512
""",
    "upscale_image": """
name: upscale_image
steps:
  - name: upscale
    type: upscale
    params:
      input: "{input_path}"
      scale: 2
      model: "esrgan"
""",
    "save_artifact": f"""
name: save_artifact
steps:
  - name: save
    type: save_artifact
    params:
      input: "{{input_path}}"
      output_dir: "{artifacts_dir}"
""",
}

class WorkflowExecutor:
    """Manages workflow execution with idempotency."""
    
    def __init__(self):
        self.execution_cache: Dict[str, Dict] = {}
        
    async def execute_step(
        self,
        step_name: str,
        correlation_id: str,
        context: Dict[str, Any],
        previous_results: List[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Execute a workflow step with idempotency.
        
        Args:
            step_name: Name of the step to execute
            correlation_id: Unique ID for idempotent execution
            context: Execution context
            previous_results: Results from previous steps
            
        Returns:
            Execution result dictionary
        """
        # Check cache for idempotency
        if correlation_id in self.execution_cache:
            logger.info(f"Returning cached result for {correlation_id}")
            return self.execution_cache[correlation_id]
            
        # Prepare workflow based on step type
        workflow = await self._prepare_workflow(step_name, context, previous_results)
        
        if not workflow:
            # For unknown steps, create a simple workflow
            workflow = {
                "name": step_name,
                "steps": [
                    {
                        "name": step_name,
                        "type": "generic",
                        "params": context
                    }
                ]
            }
            
        # Submit to engine with correlation ID
        logger.info(f"Submitting workflow for step: {step_name} (correlation_id: {correlation_id})")
        
        try:
            result = await submit(
                workflow=workflow,
                correlation_id=correlation_id,
                **context
            )
            
            # Process result
            processed_result = self._process_result(step_name, result)
            
            # Cache result
            self.execution_cache[correlation_id] = processed_result
            
            return processed_result
            
        except Exception as e:
            logger.error(f"Workflow execution failed for {step_name}: {e}")
            error_result = {
                "step": step_name,
                "status": "error",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
            self.execution_cache[correlation_id] = error_result
            raise
            
    async def _prepare_workflow(
        self,
        step_name: str,
        context: Dict[str, Any],
        previous_results: List[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """Prepare workflow specification for a step."""
        
        # Get template if available
        template = WORKFLOW_TEMPLATES.get(step_name)
        
        if not template:
            # Check if there's a workflow file
            workflow_file = Path("flows") / f"{step_name}.yml"
            if workflow_file.exists():
                with open(workflow_file) as f:
                    return yaml.safe_load(f)
            return None
            
        # Format template with context
        format_params = dict(context)
        
        # Add results from previous steps
        if previous_results:
            for i, result in enumerate(previous_results):
                if result.get("artifact_path"):
                    format_params[f"prev_artifact_{i}"] = result["artifact_path"]
                if result.get("outputs"):
                    for key, value in result["outputs"].items():
                        if isinstance(value, dict) and "image_path" in value:
                            format_params["input_path"] = value["image_path"]
                            
        # Handle specific step types
        if step_name == "generate_image":
            format_params["prompt"] = context.get("prompt", context.get("goal", "a beautiful landscape"))
        elif step_name == "upscale_image" and previous_results:
            # Find the last image artifact
            for result in reversed(previous_results):
                if result.get("outputs"):
                    for output in result["outputs"].values():
                        if isinstance(output, dict) and "image_path" in output:
                            format_params["input_path"] = output["image_path"]
                            break
                            
        # Format the template
        try:
            workflow_yaml = template.format(**format_params)
            return yaml.safe_load(workflow_yaml)
        except KeyError as e:
            logger.warning(f"Missing parameter for workflow template: {e}")
            return None
            
    def _process_result(self, step_name: str, result: Dict[str, Any]) -> Dict[str, Any]:
        """Process and normalize workflow execution result."""
        processed = {
            "step": step_name,
            "status": result.get("status", "unknown"),
            "timestamp": datetime.now().isoformat(),
            "outputs": result.get("outputs", {})
        }
        
        # Extract artifact paths
        artifact_paths = []
        if result.get("outputs"):
            for output in result["outputs"].values():
                if isinstance(output, dict):
                    if "image_path" in output:
                        artifact_paths.append(output["image_path"])
                    elif "artifact_path" in output:
                        artifact_paths.append(output["artifact_path"])
                        
        if artifact_paths:
            processed["artifact_path"] = artifact_paths[0]  # Use first artifact as primary
            processed["all_artifacts"] = artifact_paths
            
        # Add error info if present
        if result.get("error"):
            processed["error"] = result["error"]
            
        return processed

# Global executor instance
_executor = WorkflowExecutor()

async def execute_workflow_step(
    step_name: str,
    session_id: str,
    context: Dict[str, Any],
    previous_results: List[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Execute a workflow step with idempotency based on session and step.
    
    Args:
        step_name: Name of the step to execute
        session_id: Session identifier
        context: Execution context
        previous_results: Results from previous steps
        
    Returns:
        Execution result dictionary
    """
    # Generate correlation ID for idempotency
    step_index = len(previous_results) if previous_results else 0
    correlation_id = f"{session_id}:{step_name}:{step_index}"
    
    # Add session context
    full_context = {
        "session_id": session_id,
        "step_name": step_name,
        **context
    }
    
    return await _executor.execute_step(
        step_name=step_name,
        correlation_id=correlation_id,
        context=full_context,
        previous_results=previous_results
    )