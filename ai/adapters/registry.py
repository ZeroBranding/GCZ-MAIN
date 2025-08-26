"""Schema Registry for tool definitions and conversions."""
import json
from typing import Dict, Any, Type, Optional, List, Tuple
from datetime import datetime
from pydantic import BaseModel, Field
from enum import Enum

from ai.adapters.providers import FunctionDef
from core.logging import logger


class SchemaVersion(BaseModel):
    """Version information for a schema."""
    version: str = Field(..., description="Semantic version (e.g., 1.0.0)")
    created_at: datetime = Field(default_factory=datetime.now)
    deprecated: bool = Field(default=False)
    description: Optional[str] = Field(None, description="Version description")
    

class RegisteredSchema(BaseModel):
    """A registered schema with metadata."""
    name: str
    model_class: Type[BaseModel]
    function_def: FunctionDef
    versions: List[SchemaVersion]
    current_version: str
    tags: List[str] = Field(default_factory=list)
    

class SchemaRegistry:
    """Registry for managing Pydantic models and their OpenAI function schemas."""
    
    def __init__(self):
        self._schemas: Dict[str, RegisteredSchema] = {}
        self._version_history: Dict[str, List[Tuple[str, FunctionDef]]] = {}
        
    def register(
        self,
        model_class: Type[BaseModel],
        name: Optional[str] = None,
        description: Optional[str] = None,
        version: str = "1.0.0",
        tags: Optional[List[str]] = None
    ) -> FunctionDef:
        """
        Register a Pydantic model and convert it to OpenAI function schema.
        
        Args:
            model_class: The Pydantic model class to register
            name: Optional function name (defaults to model class name)
            description: Optional function description
            version: Semantic version string
            tags: Optional list of tags for categorization
            
        Returns:
            FunctionDef object for use with providers
        """
        name = name or model_class.__name__.lower()
        description = description or model_class.__doc__ or f"Function for {name}"
        tags = tags or []
        
        # Convert Pydantic model to OpenAI function schema
        function_def = self._pydantic_to_function_def(model_class, name, description)
        
        # Create or update registered schema
        if name in self._schemas:
            # Add new version
            existing = self._schemas[name]
            version_info = SchemaVersion(
                version=version,
                description=f"Updated schema for {name}"
            )
            existing.versions.append(version_info)
            existing.current_version = version
            existing.function_def = function_def
            
            # Store in version history
            if name not in self._version_history:
                self._version_history[name] = []
            self._version_history[name].append((version, function_def))
            
            logger.info(f"Updated schema '{name}' to version {version}")
        else:
            # Register new schema
            registered = RegisteredSchema(
                name=name,
                model_class=model_class,
                function_def=function_def,
                versions=[SchemaVersion(version=version)],
                current_version=version,
                tags=tags
            )
            self._schemas[name] = registered
            self._version_history[name] = [(version, function_def)]
            
            logger.info(f"Registered new schema '{name}' version {version}")
            
        return function_def
        
    def get(self, name: str, version: Optional[str] = None) -> Optional[FunctionDef]:
        """
        Get a function definition by name and optional version.
        
        Args:
            name: Function name
            version: Optional version (defaults to current version)
            
        Returns:
            FunctionDef if found, None otherwise
        """
        if name not in self._schemas:
            return None
            
        if version is None:
            # Return current version
            return self._schemas[name].function_def
        else:
            # Look for specific version
            if name in self._version_history:
                for v, func_def in self._version_history[name]:
                    if v == version:
                        return func_def
            return None
            
    def get_by_tags(self, tags: List[str]) -> List[FunctionDef]:
        """
        Get all function definitions matching any of the given tags.
        
        Args:
            tags: List of tags to match
            
        Returns:
            List of matching FunctionDef objects
        """
        results = []
        for schema in self._schemas.values():
            if any(tag in schema.tags for tag in tags):
                results.append(schema.function_def)
        return results
        
    def list_schemas(self) -> List[str]:
        """List all registered schema names."""
        return list(self._schemas.keys())
        
    def get_schema_info(self, name: str) -> Optional[Dict[str, Any]]:
        """Get detailed information about a schema."""
        if name not in self._schemas:
            return None
            
        schema = self._schemas[name]
        return {
            "name": schema.name,
            "current_version": schema.current_version,
            "versions": [
                {
                    "version": v.version,
                    "created_at": v.created_at.isoformat(),
                    "deprecated": v.deprecated
                }
                for v in schema.versions
            ],
            "tags": schema.tags,
            "function_def": {
                "name": schema.function_def.name,
                "description": schema.function_def.description,
                "parameters": schema.function_def.parameters
            }
        }
        
    def deprecate_version(self, name: str, version: str):
        """Mark a specific version as deprecated."""
        if name in self._schemas:
            for v in self._schemas[name].versions:
                if v.version == version:
                    v.deprecated = True
                    logger.info(f"Deprecated schema '{name}' version {version}")
                    return True
        return False
        
    def _pydantic_to_function_def(
        self,
        model_class: Type[BaseModel],
        name: str,
        description: str
    ) -> FunctionDef:
        """
        Convert a Pydantic model to an OpenAI function definition.
        
        Args:
            model_class: Pydantic model class
            name: Function name
            description: Function description
            
        Returns:
            FunctionDef object
        """
        # Get the JSON schema from Pydantic
        schema = model_class.model_json_schema()
        
        # Convert to OpenAI function parameters format
        parameters = {
            "type": "object",
            "properties": {},
            "required": []
        }
        
        if "properties" in schema:
            parameters["properties"] = self._convert_properties(schema["properties"])
            
        if "required" in schema:
            parameters["required"] = schema["required"]
            
        # Add additional metadata if available
        if "description" in schema:
            parameters["description"] = schema["description"]
            
        return FunctionDef(
            name=name,
            description=description,
            parameters=parameters
        )
        
    def _convert_properties(self, properties: Dict[str, Any]) -> Dict[str, Any]:
        """Convert Pydantic properties to OpenAI format."""
        converted = {}
        
        for prop_name, prop_schema in properties.items():
            converted_prop = {}
            
            # Handle type
            if "type" in prop_schema:
                converted_prop["type"] = prop_schema["type"]
            elif "anyOf" in prop_schema:
                # Handle optional fields
                types = [t.get("type") for t in prop_schema["anyOf"] if "type" in t]
                if types:
                    converted_prop["type"] = types[0]
                    
            # Handle description
            if "description" in prop_schema:
                converted_prop["description"] = prop_schema["description"]
                
            # Handle enum
            if "enum" in prop_schema:
                converted_prop["enum"] = prop_schema["enum"]
                
            # Handle array items
            if prop_schema.get("type") == "array" and "items" in prop_schema:
                converted_prop["items"] = self._convert_schema_type(prop_schema["items"])
                
            # Handle nested objects
            if prop_schema.get("type") == "object" and "properties" in prop_schema:
                converted_prop["properties"] = self._convert_properties(prop_schema["properties"])
                if "required" in prop_schema:
                    converted_prop["required"] = prop_schema["required"]
                    
            # Handle numeric constraints
            for constraint in ["minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum"]:
                if constraint in prop_schema:
                    converted_prop[constraint] = prop_schema[constraint]
                    
            # Handle string constraints
            for constraint in ["minLength", "maxLength", "pattern"]:
                if constraint in prop_schema:
                    converted_prop[constraint] = prop_schema[constraint]
                    
            converted[prop_name] = converted_prop
            
        return converted
        
    def _convert_schema_type(self, schema: Dict[str, Any]) -> Dict[str, Any]:
        """Convert a schema type definition."""
        result = {}
        
        if "type" in schema:
            result["type"] = schema["type"]
        if "description" in schema:
            result["description"] = schema["description"]
        if "enum" in schema:
            result["enum"] = schema["enum"]
            
        # Handle nested properties
        if schema.get("type") == "object" and "properties" in schema:
            result["properties"] = self._convert_properties(schema["properties"])
            if "required" in schema:
                result["required"] = schema["required"]
                
        return result


# Global registry instance
_registry = SchemaRegistry()


def get_registry() -> SchemaRegistry:
    """Get the global schema registry instance."""
    return _registry


# Convenience functions
def register_model(
    model_class: Type[BaseModel],
    name: Optional[str] = None,
    description: Optional[str] = None,
    version: str = "1.0.0",
    tags: Optional[List[str]] = None
) -> FunctionDef:
    """Register a Pydantic model in the global registry."""
    return _registry.register(model_class, name, description, version, tags)


def get_function_def(name: str, version: Optional[str] = None) -> Optional[FunctionDef]:
    """Get a function definition from the global registry."""
    return _registry.get(name, version)


def get_functions_by_tags(tags: List[str]) -> List[FunctionDef]:
    """Get function definitions by tags from the global registry."""
    return _registry.get_by_tags(tags)


# Example models for testing
class ImageGenerationInput(BaseModel):
    """Input for image generation."""
    prompt: str = Field(..., description="Text prompt for image generation")
    width: int = Field(512, ge=128, le=2048, description="Image width")
    height: int = Field(512, ge=128, le=2048, description="Image height")
    style: Optional[str] = Field(None, description="Art style")


class TextAnalysisInput(BaseModel):
    """Input for text analysis."""
    text: str = Field(..., description="Text to analyze")
    language: str = Field("en", description="Language code")
    analysis_type: str = Field("sentiment", enum=["sentiment", "entities", "summary"])


class WebSearchInput(BaseModel):
    """Input for web search."""
    query: str = Field(..., description="Search query")
    max_results: int = Field(10, ge=1, le=100, description="Maximum number of results")
    region: Optional[str] = Field(None, description="Region code for localized results")