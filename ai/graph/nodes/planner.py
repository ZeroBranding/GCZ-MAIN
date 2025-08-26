import re
from typing import Dict, List

from ai.graph.state import GraphState, PlanItem, UserRole
from core.logging import logger


class PlannerNode:
    """
    Erstellt ausführbare Pläne aus Benutzer-Goals.
    Parst Telegram-Commands und erstellt PlanItem-Sequenzen.
    """
    
    def __init__(self):
        self.command_patterns = {
            # Bild-Generierung
            r'^/img\s+(.+)': self._plan_image_generation,
            r'^/image\s+(.+)': self._plan_image_generation,
            
            # Animation
            r'^/anim\s+(.+)': self._plan_animation,
            r'^/video\s+(.+)': self._plan_animation,
            
            # Audio Processing  
            r'^/asr\s+(.+)': self._plan_speech_recognition,
            r'^/tts\s+(.+)': self._plan_text_to_speech,
            r'^/voice\s+(.+)': self._plan_text_to_speech,
            
            # Social Media Upload
            r'^/upload\s+(.+)': self._plan_upload,
            r'^/share\s+(.+)': self._plan_upload,
            
            # Kombinierte Workflows
            r'^/create\s+(.+)': self._plan_creative_workflow,
            r'^/complete\s+(.+)': self._plan_complete_workflow,
        }
        
        # Standard-Konfigurationen je Action-Type
        self.action_configs = {
            'txt2img': {
                'estimated_duration_s': 15,
                'max_retries': 2,
                'requires_gpu': True
            },
            'img2img': {
                'estimated_duration_s': 20,
                'max_retries': 2, 
                'requires_gpu': True
            },
            'upscale': {
                'estimated_duration_s': 30,
                'max_retries': 1,
                'requires_gpu': True
            },
            'anim': {
                'estimated_duration_s': 60,
                'max_retries': 1,
                'requires_gpu': True
            },
            'asr': {
                'estimated_duration_s': 10,
                'max_retries': 2,
                'requires_gpu': False
            },
            'tts': {
                'estimated_duration_s': 5,
                'max_retries': 2,
                'requires_gpu': False
            },
            'upload_youtube': {
                'estimated_duration_s': 45,
                'max_retries': 3,
                'requires_gpu': False
            },
            'upload_tiktok': {
                'estimated_duration_s': 30,
                'max_retries': 3,
                'requires_gpu': False
            }
        }

    def __call__(self, state: GraphState) -> Dict[str, any]:
        """
        LangGraph node entry point. Erstellt Plan aus state.goal.
        """
        logger.info(f"Planning for goal: {state.goal}")
        
        try:
            plan_items = self._create_plan(state.goal, state.user.role)
            
            # Plan validieren
            if not plan_items:
                state.add_error("No valid plan could be created from goal", step_id=None)
                return {"plan": []}
            
            # Dependencies auflösen
            resolved_plan = self._resolve_dependencies(plan_items)
            
            logger.info(f"Created plan with {len(resolved_plan)} steps")
            return {"plan": resolved_plan}
            
        except Exception as e:
            logger.error(f"Planning failed: {e}")
            state.add_error(f"Planning failed: {str(e)}", step_id=None)
            return {"plan": []}
    
    def _create_plan(self, goal: str, user_role: UserRole) -> List[PlanItem]:
        """Erstellt Plan basierend auf goal string."""
        
        # Command-Pattern matching
        for pattern, planner_func in self.command_patterns.items():
            match = re.match(pattern, goal.strip(), re.IGNORECASE)
            if match:
                prompt = match.group(1).strip()
                return planner_func(prompt, user_role)
        
        # Fallback: versuche intelligentes Parsing
        return self._plan_intelligent_fallback(goal, user_role)
    
    def _plan_image_generation(self, prompt: str, user_role: UserRole) -> List[PlanItem]:
        """Plant Bild-Generierung Workflow."""
        steps = []
        
        # 1. Text2Img
        steps.append(self._create_plan_item(
            action="txt2img",
            params={
                "prompt": prompt,
                "model": "sd15",
                "width": 512,
                "height": 512,
                "steps": 20,
                "cfg_scale": 7.0
            }
        ))
        
        # 2. Upscale (falls User/Admin)
        if user_role in [UserRole.USER, UserRole.ADMIN]:
            steps.append(self._create_plan_item(
                action="upscale",
                params={
                    "scale_factor": 2,
                    "model": "RealESRGAN_x2plus"
                },
                dependencies=[steps[0].id]
            ))
        
        return steps
    
    def _plan_animation(self, prompt: str, user_role: UserRole) -> List[PlanItem]:
        """Plant Animation-Generierung."""
        steps = []
        
        # Für Animation: erst img generieren, dann animieren
        steps.append(self._create_plan_item(
            action="txt2img",
            params={
                "prompt": prompt,
                "model": "sd15",
                "width": 512,
                "height": 512
            }
        ))
        
        steps.append(self._create_plan_item(
            action="anim",
            params={
                "animation_type": "video",
                "duration_s": 3,
                "fps": 24
            },
            dependencies=[steps[0].id]
        ))
        
        return steps
    
    def _plan_speech_recognition(self, audio_input: str, user_role: UserRole) -> List[PlanItem]:
        """Plant Speech-to-Text."""
        return [self._create_plan_item(
            action="asr",
            params={
                "audio_input": audio_input,
                "model": "whisper-base",
                "language": "de"
            }
        )]
    
    def _plan_text_to_speech(self, text: str, user_role: UserRole) -> List[PlanItem]:
        """Plant Text-to-Speech."""
        return [self._create_plan_item(
            action="tts",
            params={
                "text": text,
                "voice": "de-speaker",
                "speed": 1.0
            }
        )]
    
    def _plan_upload(self, content_desc: str, user_role: UserRole) -> List[PlanItem]:
        """Plant Social Media Upload."""
        # Parse für Platform-spezifische Uploads
        if 'youtube' in content_desc.lower():
            return [self._create_plan_item(
                action="upload_youtube",
                params={"description": content_desc}
            )]
        elif 'tiktok' in content_desc.lower():
            return [self._create_plan_item(
                action="upload_tiktok", 
                params={"description": content_desc}
            )]
        else:
            # Multi-Platform Upload
            return [
                self._create_plan_item(
                    action="upload_youtube",
                    params={"description": content_desc}
                ),
                self._create_plan_item(
                    action="upload_tiktok",
                    params={"description": content_desc}
                )
            ]
    
    def _plan_creative_workflow(self, prompt: str, user_role: UserRole) -> List[PlanItem]:
        """Plant kreativen End-to-End Workflow."""
        steps = []
        
        # 1. Bild generieren
        steps.append(self._create_plan_item(
            action="txt2img",
            params={"prompt": prompt, "model": "sd15"}
        ))
        
        # 2. Upscale
        steps.append(self._create_plan_item(
            action="upscale",
            params={"scale_factor": 2},
            dependencies=[steps[0].id]
        ))
        
        # 3. Animation
        steps.append(self._create_plan_item(
            action="anim",
            params={"animation_type": "video", "duration_s": 5},
            dependencies=[steps[1].id]
        ))
        
        # 4. Upload (nur für User/Admin)
        if user_role in [UserRole.USER, UserRole.ADMIN]:
            steps.append(self._create_plan_item(
                action="upload_youtube",
                params={"title": f"Generated: {prompt[:50]}"},
                dependencies=[steps[2].id]
            ))
        
        return steps
    
    def _plan_complete_workflow(self, description: str, user_role: UserRole) -> List[PlanItem]:
        """Plant kompletten Multi-Modal Workflow."""
        # Ähnlich wie creative, aber mit mehr Optionen
        return self._plan_creative_workflow(description, user_role)
    
    def _plan_intelligent_fallback(self, goal: str, user_role: UserRole) -> List[PlanItem]:
        """Intelligenter Fallback für unstrukturierte Goals."""
        
        # Einfache Keyword-basierte Erkennung
        goal_lower = goal.lower()
        
        if any(word in goal_lower for word in ['bild', 'image', 'foto', 'picture']):
            return self._plan_image_generation(goal, user_role)
        elif any(word in goal_lower for word in ['video', 'animation', 'anim']):
            return self._plan_animation(goal, user_role)
        elif any(word in goal_lower for word in ['sprache', 'voice', 'speak']):
            return self._plan_text_to_speech(goal, user_role)
        else:
            # Default: Bild-Generierung
            return self._plan_image_generation(goal, user_role)
    
    def _create_plan_item(self, action: str, params: Dict, dependencies: List[str] = None) -> PlanItem:
        """Erstellt PlanItem mit Standard-Konfiguration."""
        config = self.action_configs.get(action, {})
        
        return PlanItem(
            action=action,
            params=params,
            dependencies=dependencies or [],
            max_retries=config.get('max_retries', 2),
            estimated_duration_s=config.get('estimated_duration_s', 30)
        )
    
    def _resolve_dependencies(self, plan_items: List[PlanItem]) -> List[PlanItem]:
        """Löst Dependencies auf und sortiert Plan topologisch."""
        
        # Einfache topologische Sortierung
        resolved = []
        remaining = plan_items.copy()
        
        while remaining:
            # Finde Items ohne ungelöste Dependencies
            ready_items = []
            for item in remaining:
                if all(dep_id in [r.id for r in resolved] for dep_id in item.dependencies):
                    ready_items.append(item)
            
            if not ready_items:
                # Circular dependency oder orphaned dependency
                logger.warning("Could not resolve all dependencies, taking remaining items")
                ready_items = remaining
            
            # Füge ready items hinzu
            resolved.extend(ready_items)
            for item in ready_items:
                remaining.remove(item)
        
        return resolved