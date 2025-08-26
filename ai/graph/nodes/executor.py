import asyncio
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

from ai.graph.state import GraphState, PlanItem, StepStatus, StepResult, ErrorSeverity, ArtifactInfo
from core.logging import logger


class StepSpec:
    """Spezifikation für einen Step zur Übergabe an die Workflow Engine."""
    
    def __init__(self, step_id: str, action: str, params: Dict, context: Dict = None):
        self.step_id = step_id
        self.action = action
        self.params = params
        self.context = context or {}


class ExecutorNode:
    """
    Führt Steps über die bestehende Workflow Engine aus.
    Wandelt PlanItems in StepSpecs um und wartet auf Results.
    """
    
    def __init__(self):
        # Import hier um zirkuläre Abhängigkeiten zu vermeiden
        # Die Workflow Engine wird lazy geladen
        self._workflow_engine = None
        
        # Service-Mappings für direkte Service-Aufrufe
        self.service_mappings = {
            'txt2img': self._execute_sd_txt2img,
            'img2img': self._execute_sd_img2img,
            'upscale': self._execute_upscale,
            'anim': self._execute_animation,
            'asr': self._execute_speech_recognition,
            'tts': self._execute_text_to_speech,
            'upload_youtube': self._execute_youtube_upload,
            'upload_tiktok': self._execute_tiktok_upload,
            'upload_instagram': self._execute_instagram_upload
        }
    
    def __call__(self, state: GraphState) -> Dict[str, any]:
        """
        LangGraph node entry point. Führt den aktuellen Step aus.
        """
        current_item = state.get_current_plan_item()
        if current_item is None:
            return {"execution_result": None, "error": "No current plan item"}
        
        logger.info(f"Executing step: {current_item.action} (id: {current_item.id})")
        
        try:
            # Step als RUNNING markieren
            current_item.status = StepStatus.RUNNING
            current_item.started_at = datetime.utcnow()
            state.update_timestamp()
            
            # Execution-Timer starten
            start_time = time.time()
            
            # Step ausführen
            result = self._execute_step(current_item, state)
            
            # Execution-Zeit berechnen
            execution_time = time.time() - start_time
            
            # Result verarbeiten
            if result and result.get('success', False):
                current_item.status = StepStatus.COMPLETED
                current_item.completed_at = datetime.utcnow()
                
                # Artifacts hinzufügen
                artifacts = result.get('artifacts', [])
                for artifact_path in artifacts:
                    if isinstance(artifact_path, (str, Path)):
                        artifact_type = self._infer_artifact_type(Path(artifact_path))
                        state.add_artifact(
                            path=Path(artifact_path),
                            artifact_type=artifact_type,
                            step_id=current_item.id,
                            execution_time_s=execution_time
                        )
                
                # StepResult erstellen
                step_result = StepResult(
                    step_id=current_item.id,
                    status=StepStatus.COMPLETED,
                    artifacts=[
                        ArtifactInfo(
                            path=Path(path),
                            type=self._infer_artifact_type(Path(path)),
                            step_id=current_item.id
                        ) for path in artifacts
                    ],
                    output_data=result.get('output_data', {}),
                    execution_time_s=execution_time
                )
                
                logger.info(f"Step {current_item.action} completed successfully in {execution_time:.2f}s")
                return {"execution_result": step_result}
                
            else:
                # Step fehlgeschlagen
                error_msg = result.get('error', 'Unknown execution error')
                current_item.status = StepStatus.FAILED
                current_item.retry_count += 1
                state.used_retries += 1
                
                error_info = state.add_error(
                    message=error_msg,
                    severity=ErrorSeverity.ERROR,
                    step_id=current_item.id,
                    execution_time_s=execution_time
                )
                
                step_result = StepResult(
                    step_id=current_item.id,
                    status=StepStatus.FAILED,
                    execution_time_s=execution_time,
                    error=error_info
                )
                
                logger.error(f"Step {current_item.action} failed: {error_msg}")
                return {"execution_result": step_result, "error": error_msg}
                
        except Exception as e:
            # Unerwarteter Fehler
            current_item.status = StepStatus.FAILED
            current_item.retry_count += 1
            state.used_retries += 1
            
            error_msg = f"Unexpected error executing {current_item.action}: {str(e)}"
            error_info = state.add_error(
                message=error_msg,
                severity=ErrorSeverity.CRITICAL,
                step_id=current_item.id,
                exception_type=type(e).__name__
            )
            
            logger.error(f"Critical error in executor: {e}", exc_info=True)
            return {"execution_result": None, "error": error_msg}
    
    def _execute_step(self, step_item: PlanItem, state: GraphState) -> Dict:
        """Führt einen einzelnen Step aus."""
        
        # 1. Versuche direkte Service-Ausführung
        if step_item.action in self.service_mappings:
            return self.service_mappings[step_item.action](step_item, state)
        
        # 2. Fallback: Workflow Engine API
        return self._execute_via_workflow_engine(step_item, state)
    
    def _execute_via_workflow_engine(self, step_item: PlanItem, state: GraphState) -> Dict:
        """Führt Step über die bestehende Workflow Engine aus."""
        
        try:
            # Lazy load workflow engine
            if self._workflow_engine is None:
                from core.workflow_engine import WorkflowEngine
                self._workflow_engine = WorkflowEngine()
            
            # StepSpec erstellen
            spec = StepSpec(
                step_id=step_item.id,
                action=step_item.action,
                params=step_item.params,
                context=state.context
            )
            
            # Engine aufrufen
            result = self._workflow_engine.submit_step(spec)
            
            return {
                'success': True,
                'artifacts': result.get('artifacts', []),
                'output_data': result.get('output_data', {})
            }
            
        except Exception as e:
            logger.error(f"Workflow engine execution failed: {e}")
            return {
                'success': False,
                'error': f"Workflow engine error: {str(e)}"
            }
    
    # === Direct Service Implementations ===
    
    def _execute_sd_txt2img(self, step_item: PlanItem, state: GraphState) -> Dict:
        """Führt Stable Diffusion Text2Img aus."""
        try:
            from services.sd_service import SDService
            
            sd_service = SDService()
            params = step_item.params
            
            image_path = sd_service.txt2img(
                prompt=params.get('prompt', ''),
                model=params.get('model', 'sd15'),
                width=params.get('width', 512),
                height=params.get('height', 512),
                steps=params.get('steps', 20),
                cfg_scale=params.get('cfg_scale', 7.0)
            )
            
            return {
                'success': True,
                'artifacts': [image_path],
                'output_data': {'image_path': str(image_path)}
            }
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _execute_sd_img2img(self, step_item: PlanItem, state: GraphState) -> Dict:
        """Führt Stable Diffusion Img2Img aus."""
        try:
            from services.sd_service import SDService
            
            sd_service = SDService()
            params = step_item.params
            
            # Input-Image aus vorherigen Steps finden
            input_image = self._find_input_artifact(step_item, state, 'image')
            if not input_image:
                return {'success': False, 'error': 'No input image found'}
            
            image_path = sd_service.img2img(
                image_path=str(input_image),
                prompt=params.get('prompt', ''),
                strength=params.get('strength', 0.8)
            )
            
            return {
                'success': True,
                'artifacts': [image_path],
                'output_data': {'image_path': str(image_path)}
            }
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _execute_upscale(self, step_item: PlanItem, state: GraphState) -> Dict:
        """Führt Image Upscaling aus."""
        try:
            from services.sd_service import SDService
            
            sd_service = SDService()
            params = step_item.params
            
            # Input-Image finden
            input_image = self._find_input_artifact(step_item, state, 'image')
            if not input_image:
                return {'success': False, 'error': 'No input image found'}
            
            upscaled_path = sd_service.upscale(
                image_path=str(input_image),
                model=params.get('model', 'RealESRGAN_x2plus')
            )
            
            return {
                'success': True,
                'artifacts': [upscaled_path],
                'output_data': {'upscaled_path': str(upscaled_path)}
            }
            
        except NotImplementedError:
            return {'success': False, 'error': 'Upscale functionality not yet implemented'}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _execute_animation(self, step_item: PlanItem, state: GraphState) -> Dict:
        """Führt Animation/Video-Generierung aus."""
        try:
            from services.anim_service import AnimService
            
            anim_service = AnimService()
            params = step_item.params
            
            # Input-Image finden
            input_image = self._find_input_artifact(step_item, state, 'image')
            if not input_image:
                return {'success': False, 'error': 'No input image found'}
            
            video_path = anim_service.create_animation(
                image_path=str(input_image),
                animation_type=params.get('animation_type', 'video'),
                duration_s=params.get('duration_s', 3),
                fps=params.get('fps', 24)
            )
            
            return {
                'success': True,
                'artifacts': [video_path],
                'output_data': {'video_path': str(video_path)}
            }
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _execute_speech_recognition(self, step_item: PlanItem, state: GraphState) -> Dict:
        """Führt Speech-to-Text aus."""
        try:
            from services.asr_service import ASRService
            
            asr_service = ASRService()
            params = step_item.params
            
            text = asr_service.transcribe(
                audio_path=params.get('audio_input'),
                model=params.get('model', 'whisper-base'),
                language=params.get('language', 'de')
            )
            
            return {
                'success': True,
                'artifacts': [],
                'output_data': {'transcribed_text': text}
            }
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _execute_text_to_speech(self, step_item: PlanItem, state: GraphState) -> Dict:
        """Führt Text-to-Speech aus."""
        try:
            from services.voice_service import VoiceService
            
            voice_service = VoiceService()
            params = step_item.params
            
            audio_path = voice_service.text_to_speech(
                text=params.get('text', ''),
                voice=params.get('voice', 'de-speaker'),
                speed=params.get('speed', 1.0)
            )
            
            return {
                'success': True,
                'artifacts': [audio_path],
                'output_data': {'audio_path': str(audio_path)}
            }
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _execute_youtube_upload(self, step_item: PlanItem, state: GraphState) -> Dict:
        """Führt YouTube Upload aus."""
        try:
            from services.youtube_service import YouTubeService
            
            youtube_service = YouTubeService()
            params = step_item.params
            
            # Video-Artefakt finden
            video_artifact = self._find_input_artifact(step_item, state, 'video')
            if not video_artifact:
                return {'success': False, 'error': 'No video artifact found'}
            
            upload_result = youtube_service.upload_video(
                video_path=str(video_artifact),
                title=params.get('title', 'Generated Content'),
                description=params.get('description', '')
            )
            
            return {
                'success': True,
                'artifacts': [],
                'output_data': upload_result
            }
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _execute_tiktok_upload(self, step_item: PlanItem, state: GraphState) -> Dict:
        """Führt TikTok Upload aus."""
        try:
            from services.tiktok_service import TikTokService
            
            tiktok_service = TikTokService()
            params = step_item.params
            
            # Video-Artefakt finden
            video_artifact = self._find_input_artifact(step_item, state, 'video')
            if not video_artifact:
                return {'success': False, 'error': 'No video artifact found'}
            
            upload_result = tiktok_service.upload_video(
                video_path=str(video_artifact),
                description=params.get('description', '')
            )
            
            return {
                'success': True,
                'artifacts': [],
                'output_data': upload_result
            }
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _execute_instagram_upload(self, step_item: PlanItem, state: GraphState) -> Dict:
        """Führt Instagram Upload aus."""
        try:
            from services.instagram_service import InstagramService
            
            instagram_service = InstagramService()
            params = step_item.params
            
            # Media-Artefakt finden
            media_artifact = self._find_input_artifact(step_item, state, ['image', 'video'])
            if not media_artifact:
                return {'success': False, 'error': 'No media artifact found'}
            
            upload_result = instagram_service.upload_media(
                media_path=str(media_artifact),
                caption=params.get('caption', '')
            )
            
            return {
                'success': True,
                'artifacts': [],
                'output_data': upload_result
            }
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    # === Helper Methods ===
    
    def _find_input_artifact(self, step_item: PlanItem, state: GraphState, artifact_types) -> Optional[Path]:
        """Findet Eingabe-Artefakt für einen Step basierend auf Dependencies."""
        
        if isinstance(artifact_types, str):
            artifact_types = [artifact_types]
        
        # Finde Artefakte von Dependency-Steps
        for dep_id in step_item.dependencies:
            for artifact in state.artifacts:
                if (artifact.step_id == dep_id and 
                    artifact.type in artifact_types and
                    artifact.path.exists()):
                    return artifact.path
        
        # Fallback: letztes Artefakt des passenden Typs
        for artifact in reversed(state.artifacts):
            if (artifact.type in artifact_types and 
                artifact.path.exists()):
                return artifact.path
        
        return None
    
    def _infer_artifact_type(self, path: Path) -> str:
        """Leitet Artefakt-Typ aus Dateiendung ab."""
        
        suffix = path.suffix.lower()
        
        if suffix in ['.jpg', '.jpeg', '.png', '.bmp', '.tiff']:
            return 'image'
        elif suffix in ['.mp4', '.avi', '.mov', '.mkv', '.webm']:
            return 'video'
        elif suffix in ['.mp3', '.wav', '.flac', '.ogg']:
            return 'audio'
        elif suffix in ['.pdf', '.txt', '.md', '.docx']:
            return 'document'
        else:
            return 'unknown'