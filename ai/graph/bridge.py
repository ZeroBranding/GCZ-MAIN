"""Bridge between LangGraph and Workflow Engine.

This module provides the translation layer between AI tool calls
and workflow engine step specifications.
"""
import asyncio
import hashlib
import json
from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass, asdict
from datetime import datetime
import yaml

from ai.adapters.providers import ToolCall
from ai.tools.bindings import ToolResult, ArtifactResult
from core.workflow_engine import WorkflowEngine
from core.logging import logger


@dataclass
class StepSpec:
    """Specification for a workflow step."""
    name: str
    type: str
    params: Dict[str, Any]
    depends_on: Optional[List[str]] = None
    outputs: Optional[Dict[str, str]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for workflow engine."""
        result = {
            "name": self.name,
            "type": self.type,
            "params": self.params
        }
        if self.depends_on:
            result["depends_on"] = self.depends_on
        if self.outputs:
            result["outputs"] = self.outputs
        return result


@dataclass
class WorkflowSpec:
    """Complete workflow specification."""
    name: str
    steps: List[StepSpec]
    context: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for workflow engine."""
        return {
            "name": self.name,
            "steps": [step.to_dict() for step in self.steps],
            "context": self.context or {}
        }
    
    def to_yaml(self) -> str:
        """Convert to YAML string."""
        return yaml.dump(self.to_dict(), default_flow_style=False)


class GraphEngineBridge:
    """Bridge between LangGraph tool calls and Workflow Engine."""
    
    def __init__(self, engine: Optional[WorkflowEngine] = None):
        """Initialize bridge with optional engine instance."""
        self.engine = engine or WorkflowEngine()
        self._step_mappings = self._initialize_mappings()
        
    def _initialize_mappings(self) -> Dict[str, callable]:
        """Initialize tool to step conversion mappings."""
        return {
            "sd_generate": self._sd_generate_to_steps,
            "upscale_image": self._upscale_to_steps,
            "generate_animation": self._animation_to_steps,
            "transcribe_audio": self._asr_to_steps,
            "synthesize_speech": self._tts_to_steps,
            "upload_file": self._upload_to_steps,
        }
    
    def tool_call_to_steps(self, tool_call: ToolCall) -> List[StepSpec]:
        """
        Convert a tool call to workflow step specifications.
        
        Args:
            tool_call: The tool call to convert
            
        Returns:
            List of step specifications in deterministic order
        """
        # Get the appropriate converter
        converter = self._step_mappings.get(tool_call.name)
        if not converter:
            # Default single-step conversion
            return self._default_to_steps(tool_call)
            
        # Convert using specific mapper
        steps = converter(tool_call)
        
        # Ensure deterministic ordering by sorting by step name
        steps.sort(key=lambda s: s.name)
        
        logger.info(f"Converted tool call '{tool_call.name}' to {len(steps)} steps")
        return steps
    
    def _default_to_steps(self, tool_call: ToolCall) -> List[StepSpec]:
        """Default conversion for unknown tools."""
        return [
            StepSpec(
                name=f"{tool_call.name}_step",
                type=tool_call.name,
                params=tool_call.arguments or {}
            )
        ]
    
    def _sd_generate_to_steps(self, tool_call: ToolCall) -> List[StepSpec]:
        """Convert SD generation tool call to steps."""
        args = tool_call.arguments or {}
        
        steps = []
        
        # Step 1: Generate image
        steps.append(StepSpec(
            name="generate_image",
            type="txt2img",
            params={
                "prompt": args.get("prompt", ""),
                "negative_prompt": args.get("negative_prompt", ""),
                "width": args.get("width", 512),
                "height": args.get("height", 512),
                "steps": args.get("steps", 20),
                "seed": args.get("seed"),
            },
            outputs={"image_path": "generated_image"}
        ))
        
        # Step 2: Save artifact (if requested)
        if args.get("save_artifact", True):
            steps.append(StepSpec(
                name="save_artifact",
                type="save_artifact",
                params={
                    "input": "${generate_image.image_path}",
                    "output_dir": "/artifacts/images"
                },
                depends_on=["generate_image"]
            ))
            
        return steps
    
    def _upscale_to_steps(self, tool_call: ToolCall) -> List[StepSpec]:
        """Convert upscale tool call to steps."""
        args = tool_call.arguments or {}
        
        steps = []
        
        # Step 1: Load image (if path provided)
        if args.get("image_path"):
            steps.append(StepSpec(
                name="load_image",
                type="load_image",
                params={
                    "path": args["image_path"]
                },
                outputs={"image": "loaded_image"}
            ))
            
        # Step 2: Upscale
        steps.append(StepSpec(
            name="upscale_image",
            type="upscale",
            params={
                "input": "${load_image.image}" if args.get("image_path") else args.get("input"),
                "scale": args.get("scale", 2),
                "model": args.get("model")
            },
            depends_on=["load_image"] if args.get("image_path") else None,
            outputs={"image_path": "upscaled_image"}
        ))
        
        # Step 3: Save result
        steps.append(StepSpec(
            name="save_upscaled",
            type="save_artifact",
            params={
                "input": "${upscale_image.image_path}",
                "output_dir": "/artifacts/upscaled"
            },
            depends_on=["upscale_image"]
        ))
        
        return steps
    
    def _animation_to_steps(self, tool_call: ToolCall) -> List[StepSpec]:
        """Convert animation tool call to steps."""
        args = tool_call.arguments or {}
        
        steps = []
        
        # Step 1: Generate keyframes
        steps.append(StepSpec(
            name="generate_keyframes",
            type="generate_keyframes",
            params={
                "prompt": args.get("prompt", ""),
                "duration": args.get("duration", 3.0),
                "fps": args.get("fps", 30)
            },
            outputs={"frames": "keyframes"}
        ))
        
        # Step 2: Interpolate frames
        steps.append(StepSpec(
            name="interpolate_frames",
            type="interpolate",
            params={
                "keyframes": "${generate_keyframes.frames}",
                "style": args.get("style", "default")
            },
            depends_on=["generate_keyframes"],
            outputs={"frames": "interpolated_frames"}
        ))
        
        # Step 3: Render animation
        steps.append(StepSpec(
            name="render_animation",
            type="render_video",
            params={
                "frames": "${interpolate_frames.frames}",
                "output_format": "mp4",
                "codec": "h264"
            },
            depends_on=["interpolate_frames"],
            outputs={"video_path": "animation"}
        ))
        
        return steps
    
    def _asr_to_steps(self, tool_call: ToolCall) -> List[StepSpec]:
        """Convert ASR tool call to steps."""
        args = tool_call.arguments or {}
        
        steps = []
        
        # Step 1: Load audio
        steps.append(StepSpec(
            name="load_audio",
            type="load_audio",
            params={
                "path": args.get("audio_path", "")
            },
            outputs={"audio": "audio_data"}
        ))
        
        # Step 2: Transcribe
        steps.append(StepSpec(
            name="transcribe_audio",
            type="asr",
            params={
                "audio": "${load_audio.audio}",
                "language": args.get("language", "de"),
                "model": args.get("model", "whisper")
            },
            depends_on=["load_audio"],
            outputs={"text": "transcription", "segments": "segments"}
        ))
        
        # Step 3: Format output
        if args.get("format") == "segments":
            steps.append(StepSpec(
                name="format_segments",
                type="format_output",
                params={
                    "segments": "${transcribe_audio.segments}",
                    "format": "json"
                },
                depends_on=["transcribe_audio"]
            ))
            
        return steps
    
    def _tts_to_steps(self, tool_call: ToolCall) -> List[StepSpec]:
        """Convert TTS tool call to steps."""
        args = tool_call.arguments or {}
        
        steps = []
        
        # Step 1: Prepare text
        steps.append(StepSpec(
            name="prepare_text",
            type="text_preprocessing",
            params={
                "text": args.get("text", ""),
                "language": args.get("language", "de"),
                "normalize": True
            },
            outputs={"processed_text": "text"}
        ))
        
        # Step 2: Synthesize
        steps.append(StepSpec(
            name="synthesize_speech",
            type="tts",
            params={
                "text": "${prepare_text.processed_text}",
                "voice": args.get("voice_profile", "default"),
                "backend": args.get("backend", "openvoice")
            },
            depends_on=["prepare_text"],
            outputs={"audio_path": "synthesized_audio"}
        ))
        
        # Step 3: Save audio
        steps.append(StepSpec(
            name="save_audio",
            type="save_artifact",
            params={
                "input": "${synthesize_speech.audio_path}",
                "output_dir": "/artifacts/audio"
            },
            depends_on=["synthesize_speech"]
        ))
        
        return steps
    
    def _upload_to_steps(self, tool_call: ToolCall) -> List[StepSpec]:
        """Convert upload tool call to steps."""
        args = tool_call.arguments or {}
        
        destination = args.get("destination", "local")
        
        if destination == "telegram":
            return [
                StepSpec(
                    name="upload_telegram",
                    type="telegram_upload",
                    params={
                        "file_path": args.get("file_path", ""),
                        "chat_id": args.get("chat_id", ""),
                        "caption": args.get("caption", "")
                    }
                )
            ]
        else:
            return [
                StepSpec(
                    name="upload_local",
                    type="local_upload",
                    params={
                        "file_path": args.get("file_path", ""),
                        "destination": "/artifacts/uploads"
                    }
                )
            ]
    
    async def submit_and_wait(
        self,
        spec: Union[WorkflowSpec, List[StepSpec], Dict[str, Any]],
        correlation_id: Optional[str] = None,
        timeout: float = 120.0
    ) -> ToolResult:
        """
        Submit a workflow specification and wait for completion.
        
        Args:
            spec: Workflow specification, list of steps, or dict
            correlation_id: Unique ID for idempotent execution
            timeout: Maximum time to wait for completion
            
        Returns:
            ToolResult with execution outcome
        """
        try:
            # Convert spec to workflow dict
            if isinstance(spec, WorkflowSpec):
                workflow_dict = spec.to_dict()
            elif isinstance(spec, list):
                # List of StepSpecs
                workflow_dict = {
                    "name": "tool_workflow",
                    "steps": [s.to_dict() if isinstance(s, StepSpec) else s for s in spec]
                }
            else:
                workflow_dict = spec
                
            # Generate correlation ID if not provided
            if not correlation_id:
                # Create deterministic ID from spec
                spec_str = json.dumps(workflow_dict, sort_keys=True)
                correlation_id = hashlib.md5(spec_str.encode()).hexdigest()
                
            logger.info(f"Submitting workflow with correlation_id: {correlation_id}")
            
            # Submit to engine with timeout
            result = await asyncio.wait_for(
                self.engine.submit(
                    workflow=workflow_dict,
                    correlation_id=correlation_id
                ),
                timeout=timeout
            )
            
            # Convert engine result to ToolResult
            if result.get("status") == "completed":
                # Check for artifacts
                outputs = result.get("outputs", {})
                artifact_path = None
                artifact_type = None
                
                # Look for common artifact outputs
                for step_outputs in outputs.values():
                    if isinstance(step_outputs, dict):
                        if "image_path" in step_outputs:
                            artifact_path = step_outputs["image_path"]
                            artifact_type = "image/png"
                            break
                        elif "video_path" in step_outputs:
                            artifact_path = step_outputs["video_path"]
                            artifact_type = "video/mp4"
                            break
                        elif "audio_path" in step_outputs:
                            artifact_path = step_outputs["audio_path"]
                            artifact_type = "audio/wav"
                            break
                            
                if artifact_path:
                    return ArtifactResult(
                        success=True,
                        artifact_path=artifact_path,
                        artifact_type=artifact_type,
                        data=outputs,
                        metadata={
                            "correlation_id": correlation_id,
                            "workflow": workflow_dict.get("name", "unknown")
                        }
                    )
                else:
                    return ToolResult(
                        success=True,
                        data=outputs,
                        metadata={
                            "correlation_id": correlation_id,
                            "workflow": workflow_dict.get("name", "unknown")
                        }
                    )
            else:
                # Execution failed
                return ToolResult(
                    success=False,
                    error=result.get("error", "Workflow execution failed"),
                    metadata={
                        "correlation_id": correlation_id,
                        "status": result.get("status"),
                        "workflow": workflow_dict.get("name", "unknown")
                    }
                )
                
        except asyncio.TimeoutError:
            logger.error(f"Workflow execution timed out after {timeout}s")
            return ToolResult(
                success=False,
                error=f"Workflow execution timed out after {timeout} seconds",
                metadata={"correlation_id": correlation_id}
            )
        except Exception as e:
            logger.error(f"Error submitting workflow: {e}")
            return ToolResult(
                success=False,
                error=str(e),
                metadata={"correlation_id": correlation_id}
            )


# Global bridge instance
_bridge: Optional[GraphEngineBridge] = None


def get_bridge() -> GraphEngineBridge:
    """Get or create the global bridge instance."""
    global _bridge
    if _bridge is None:
        _bridge = GraphEngineBridge()
    return _bridge


async def tool_call_to_workflow(
    tool_call: ToolCall,
    correlation_id: Optional[str] = None
) -> ToolResult:
    """
    Convert a tool call to workflow and execute it.
    
    Args:
        tool_call: The tool call to execute
        correlation_id: Optional correlation ID for idempotency
        
    Returns:
        ToolResult with execution outcome
    """
    bridge = get_bridge()
    
    # Convert to steps
    steps = bridge.tool_call_to_steps(tool_call)
    
    # Submit and wait
    return await bridge.submit_and_wait(
        spec=steps,
        correlation_id=correlation_id or f"{tool_call.id}:{tool_call.name}"
    )