from typing import Dict, List, Any


def get_tool_schemas() -> List[Dict[str, Any]]:
    """
    Gibt OpenAI Functions-kompatible Tool-Schemas zurück.
    Für LangGraph Tool-Integration und zukünftige LLM-basierte Planning.
    """
    
    return [
        # === Image Generation Tools ===
        {
            "type": "function",
            "function": {
                "name": "sd_txt2img",
                "description": "Generiert ein Bild aus einem Text-Prompt mit Stable Diffusion",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "prompt": {
                            "type": "string",
                            "description": "Der Text-Prompt für die Bildgenerierung"
                        },
                        "model": {
                            "type": "string",
                            "description": "Das zu verwendende Stable Diffusion Modell",
                            "enum": ["sd15", "sd21", "sdxl"],
                            "default": "sd15"
                        },
                        "width": {
                            "type": "integer",
                            "description": "Bildbreite in Pixeln",
                            "minimum": 256,
                            "maximum": 1024,
                            "default": 512
                        },
                        "height": {
                            "type": "integer", 
                            "description": "Bildhöhe in Pixeln",
                            "minimum": 256,
                            "maximum": 1024,
                            "default": 512
                        },
                        "steps": {
                            "type": "integer",
                            "description": "Anzahl der Inference-Steps",
                            "minimum": 10,
                            "maximum": 50,
                            "default": 20
                        },
                        "cfg_scale": {
                            "type": "number",
                            "description": "CFG Scale für Prompt-Adherence",
                            "minimum": 1.0,
                            "maximum": 20.0,
                            "default": 7.0
                        }
                    },
                    "required": ["prompt"]
                }
            }
        },
        
        {
            "type": "function",
            "function": {
                "name": "sd_img2img",
                "description": "Modifiziert ein existierendes Bild basierend auf einem Text-Prompt",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "image_path": {
                            "type": "string",
                            "description": "Pfad zum Eingangsbild"
                        },
                        "prompt": {
                            "type": "string",
                            "description": "Text-Prompt für die Bildmodifikation"
                        },
                        "strength": {
                            "type": "number",
                            "description": "Stärke der Transformation (0.0-1.0)",
                            "minimum": 0.0,
                            "maximum": 1.0,
                            "default": 0.8
                        },
                        "model": {
                            "type": "string",
                            "description": "Stable Diffusion Modell",
                            "enum": ["sd15", "sd21", "sdxl"],
                            "default": "sd15"
                        }
                    },
                    "required": ["image_path", "prompt"]
                }
            }
        },
        
        # === Image Enhancement Tools ===
        {
            "type": "function",
            "function": {
                "name": "upscale_image",
                "description": "Skaliert ein Bild mit KI-basierten Methoden hoch",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "image_path": {
                            "type": "string",
                            "description": "Pfad zum zu skalierenden Bild"
                        },
                        "scale_factor": {
                            "type": "integer",
                            "description": "Skalierungsfaktor",
                            "enum": [2, 4],
                            "default": 2
                        },
                        "model": {
                            "type": "string",
                            "description": "Upscaling-Modell",
                            "enum": ["RealESRGAN_x2plus", "RealESRGAN_x4plus", "ESRGAN_x4"],
                            "default": "RealESRGAN_x2plus"
                        }
                    },
                    "required": ["image_path"]
                }
            }
        },
        
        # === Video/Animation Tools ===
        {
            "type": "function",
            "function": {
                "name": "create_animation",
                "description": "Erstellt eine Animation oder ein Video aus einem Bild",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "image_path": {
                            "type": "string",
                            "description": "Pfad zum Quellbild"
                        },
                        "animation_type": {
                            "type": "string",
                            "description": "Art der Animation",
                            "enum": ["video", "gif", "zoom", "pan"],
                            "default": "video"
                        },
                        "duration_s": {
                            "type": "integer",
                            "description": "Dauer in Sekunden",
                            "minimum": 1,
                            "maximum": 30,
                            "default": 3
                        },
                        "fps": {
                            "type": "integer",
                            "description": "Frames per Second",
                            "enum": [12, 24, 30, 60],
                            "default": 24
                        }
                    },
                    "required": ["image_path"]
                }
            }
        },
        
        # === Audio Processing Tools ===
        {
            "type": "function", 
            "function": {
                "name": "speech_to_text",
                "description": "Konvertiert Audio zu Text mit Whisper",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "audio_path": {
                            "type": "string",
                            "description": "Pfad zur Audio-Datei"
                        },
                        "language": {
                            "type": "string",
                            "description": "Sprache der Audio-Datei",
                            "enum": ["de", "en", "fr", "es", "auto"],
                            "default": "de"
                        },
                        "model": {
                            "type": "string",
                            "description": "Whisper-Modell",
                            "enum": ["tiny", "base", "small", "medium", "large"],
                            "default": "base"
                        }
                    },
                    "required": ["audio_path"]
                }
            }
        },
        
        {
            "type": "function",
            "function": {
                "name": "text_to_speech",
                "description": "Konvertiert Text zu Sprache mit XTTS",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "text": {
                            "type": "string",
                            "description": "Der zu sprechende Text"
                        },
                        "voice": {
                            "type": "string", 
                            "description": "Stimme/Speaker",
                            "enum": ["de-speaker", "en-speaker", "female", "male"],
                            "default": "de-speaker"
                        },
                        "speed": {
                            "type": "number",
                            "description": "Sprechgeschwindigkeit",
                            "minimum": 0.5,
                            "maximum": 2.0,
                            "default": 1.0
                        },
                        "emotion": {
                            "type": "string",
                            "description": "Emotionaler Ton",
                            "enum": ["neutral", "happy", "sad", "angry", "excited"],
                            "default": "neutral"
                        }
                    },
                    "required": ["text"]
                }
            }
        },
        
        # === Social Media Upload Tools ===
        {
            "type": "function",
            "function": {
                "name": "upload_youtube",
                "description": "Lädt ein Video auf YouTube hoch",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "video_path": {
                            "type": "string",
                            "description": "Pfad zur Video-Datei"
                        },
                        "title": {
                            "type": "string",
                            "description": "Video-Titel",
                            "maxLength": 100
                        },
                        "description": {
                            "type": "string",
                            "description": "Video-Beschreibung",
                            "maxLength": 5000,
                            "default": ""
                        },
                        "tags": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Video-Tags",
                            "maxItems": 500
                        },
                        "privacy": {
                            "type": "string",
                            "description": "Privatsphäre-Einstellung",
                            "enum": ["private", "unlisted", "public"],
                            "default": "unlisted"
                        }
                    },
                    "required": ["video_path", "title"]
                }
            }
        },
        
        {
            "type": "function",
            "function": {
                "name": "upload_tiktok",
                "description": "Lädt ein Video auf TikTok hoch",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "video_path": {
                            "type": "string",
                            "description": "Pfad zur Video-Datei"
                        },
                        "description": {
                            "type": "string",
                            "description": "Video-Beschreibung/Caption",
                            "maxLength": 300
                        },
                        "hashtags": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Hashtags für das Video",
                            "maxItems": 100
                        },
                        "privacy": {
                            "type": "string",
                            "description": "Privatsphäre-Einstellung",
                            "enum": ["public", "friends", "private"],
                            "default": "public"
                        }
                    },
                    "required": ["video_path"]
                }
            }
        },
        
        {
            "type": "function",
            "function": {
                "name": "upload_instagram",
                "description": "Lädt ein Bild oder Video auf Instagram hoch",
                "parameters": {
                    "type": "object", 
                    "properties": {
                        "media_path": {
                            "type": "string",
                            "description": "Pfad zur Medien-Datei (Bild oder Video)"
                        },
                        "caption": {
                            "type": "string",
                            "description": "Post-Caption",
                            "maxLength": 2200,
                            "default": ""
                        },
                        "hashtags": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Hashtags für den Post",
                            "maxItems": 30
                        },
                        "location": {
                            "type": "string",
                            "description": "Standort-Tag",
                            "default": ""
                        }
                    },
                    "required": ["media_path"]
                }
            }
        },
        
        # === Utility Tools ===
        {
            "type": "function",
            "function": {
                "name": "analyze_image",
                "description": "Analysiert ein Bild und gibt Metadaten zurück",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "image_path": {
                            "type": "string",
                            "description": "Pfad zum zu analysierenden Bild"
                        },
                        "analysis_type": {
                            "type": "string",
                            "description": "Art der Analyse",
                            "enum": ["basic", "detailed", "content", "quality"],
                            "default": "basic"
                        }
                    },
                    "required": ["image_path"]
                }
            }
        },
        
        {
            "type": "function",
            "function": {
                "name": "combine_media",
                "description": "Kombiniert mehrere Medien-Dateien",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "media_paths": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Liste der zu kombinierenden Medien-Pfade",
                            "minItems": 2
                        },
                        "output_type": {
                            "type": "string",
                            "description": "Ausgabeformat",
                            "enum": ["video", "gif", "collage", "slideshow"],
                            "default": "video"
                        },
                        "transition": {
                            "type": "string",
                            "description": "Übergangseffekt",
                            "enum": ["fade", "slide", "zoom", "none"],
                            "default": "fade"
                        }
                    },
                    "required": ["media_paths"]
                }
            }
        }
    ]


def get_tool_by_name(tool_name: str) -> Dict[str, Any]:
    """Gibt Tool-Schema nach Namen zurück."""
    
    schemas = get_tool_schemas()
    for schema in schemas:
        if schema["function"]["name"] == tool_name:
            return schema
    
    raise ValueError(f"Tool '{tool_name}' not found")


def validate_tool_parameters(tool_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validiert Tool-Parameter gegen das Schema.
    Returns: Validierte/bereinigte Parameter.
    """
    
    schema = get_tool_by_name(tool_name)
    param_schema = schema["function"]["parameters"]
    
    # Basis-Validierung
    validated = {}
    required_fields = param_schema.get("required", [])
    properties = param_schema.get("properties", {})
    
    # Required fields prüfen
    for field in required_fields:
        if field not in parameters:
            raise ValueError(f"Required parameter '{field}' missing for tool '{tool_name}'")
        validated[field] = parameters[field]
    
    # Optional fields mit Defaults
    for field, field_schema in properties.items():
        if field not in validated and field in parameters:
            validated[field] = parameters[field]
        elif field not in validated and "default" in field_schema:
            validated[field] = field_schema["default"]
    
    return validated


def get_tools_for_action_type(action_type: str) -> List[str]:
    """Gibt passende Tool-Namen für einen Action-Type zurück."""
    
    action_mappings = {
        'image_generation': ['sd_txt2img', 'sd_img2img'],
        'image_enhancement': ['upscale_image'],
        'video_creation': ['create_animation'],
        'audio_processing': ['speech_to_text', 'text_to_speech'],
        'social_media': ['upload_youtube', 'upload_tiktok', 'upload_instagram'],
        'analysis': ['analyze_image'],
        'media_editing': ['combine_media']
    }
    
    return action_mappings.get(action_type, [])