# Model Provider Adapter Specification

## Overview

Minimal-invasive Abstraction für verschiedene LLM-Provider ohne Vendor-Lock. Ermöglicht nahtlosen Wechsel zwischen OpenAI, Anthropic, Ollama und anderen Anbietern.

## Core Interfaces

### ChatLLM Base Interface

```python
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Union
from dataclasses import dataclass
from enum import Enum

class ModelRole(str, Enum):
    PLANNER = "planner"
    EXECUTOR = "executor" 
    REVIEWER = "reviewer"
    EMBEDDER = "embedder"

@dataclass
class ModelResponse:
    """Unified response envelope für alle Provider."""
    content: str
    usage: Dict[str, int]  # tokens_input, tokens_output, tokens_total
    model: str
    provider: str
    latency_ms: int
    cost_usd: Optional[float] = None
    metadata: Dict[str, Any] = None

@dataclass
class ModelRequest:
    """Unified request format."""
    messages: List[Dict[str, str]]  # [{"role": "user", "content": "..."}]
    max_tokens: Optional[int] = None
    temperature: Optional[float] = None
    tools: Optional[List[Dict]] = None
    model_override: Optional[str] = None

class ChatLLM(ABC):
    """Base interface für Chat-LLMs."""
    
    @abstractmethod
    async def plan(self, request: ModelRequest) -> ModelResponse:
        """Planning-optimierte LLM-Calls (hohe Reasoning-Qualität)."""
        pass
    
    @abstractmethod 
    async def execute(self, request: ModelRequest) -> ModelResponse:
        """Execution-optimierte LLM-Calls (Speed vs. Quality Balance)."""
        pass
    
    @abstractmethod
    async def review(self, request: ModelRequest) -> ModelResponse:
        """Review-optimierte LLM-Calls (Kritische Evaluation)."""
        pass
    
    @abstractmethod
    def get_capabilities(self) -> Dict[str, Any]:
        """Provider capabilities (max_tokens, tools, vision, etc.)."""
        pass
    
    @abstractmethod
    async def health_check(self) -> bool:
        """Provider health status."""
        pass
```

### Embedding Interface

```python
@dataclass
class EmbeddingRequest:
    texts: List[str]
    model_override: Optional[str] = None

@dataclass  
class EmbeddingResponse:
    embeddings: List[List[float]]
    model: str
    provider: str
    usage: Dict[str, int]
    latency_ms: int
    cost_usd: Optional[float] = None

class EmbeddingProvider(ABC):
    """Interface für Embedding-Modelle."""
    
    @abstractmethod
    async def embed_texts(self, request: EmbeddingRequest) -> EmbeddingResponse:
        """Text zu Embeddings konvertieren."""
        pass
    
    @abstractmethod
    async def embed_query(self, query: str) -> List[float]:
        """Einzelne Query einbetten (convenience method)."""
        pass
```

### Vision Interface (Optional)

```python
@dataclass
class VisionRequest:
    image_paths: List[str]
    prompt: str
    model_override: Optional[str] = None

@dataclass
class VisionResponse:
    description: str
    confidence: Optional[float]
    model: str
    provider: str
    usage: Dict[str, int]
    latency_ms: int
    cost_usd: Optional[float] = None

class VisionProvider(ABC):
    """Interface für Vision-Modelle (Optional)."""
    
    @abstractmethod
    async def analyze_images(self, request: VisionRequest) -> VisionResponse:
        """Bilder analysieren und beschreiben."""
        pass
```

## Provider Implementations

### Provider Factory Pattern

```python
class ModelProviderFactory:
    """Factory für verschiedene Provider-Implementierungen."""
    
    @staticmethod
    def create_chat_llm(provider: str, config: Dict[str, Any]) -> ChatLLM:
        """
        Erstellt ChatLLM-Provider basierend auf Konfiguration.
        
        Supported Providers:
        - "openai": OpenAI GPT-4, GPT-3.5
        - "anthropic": Claude Sonnet, Claude Opus
        - "ollama": Lokale Modelle (Llama, Mistral, etc.)
        - "azure": Azure OpenAI Service
        - "google": Gemini Pro/Ultra
        """
        pass
    
    @staticmethod
    def create_embedding_provider(provider: str, config: Dict[str, Any]) -> EmbeddingProvider:
        """Erstellt Embedding-Provider."""
        pass
        
    @staticmethod  
    def create_vision_provider(provider: str, config: Dict[str, Any]) -> VisionProvider:
        """Erstellt Vision-Provider."""
        pass
```

## Backend-Specific Configurations

### OpenAI Backend

```yaml
openai:
  api_key: "${OPENAI_API_KEY}"
  base_url: "https://api.openai.com/v1"
  organization: "${OPENAI_ORG_ID}"
  
  models:
    planner: "gpt-4-turbo-preview"
    executor: "gpt-4" 
    reviewer: "gpt-4"
    embedder: "text-embedding-3-large"
    vision: "gpt-4-vision-preview"
    
  limits:
    max_tokens: 4096
    timeout_s: 60
    rate_limit_rpm: 3500
    max_retries: 3
    
  cost_tracking:
    enable: true
    daily_limit_usd: 50.0
    alert_threshold_usd: 40.0
```

### Anthropic Backend

```yaml
anthropic:
  api_key: "${ANTHROPIC_API_KEY}"
  base_url: "https://api.anthropic.com"
  
  models:
    planner: "claude-3-sonnet-20240229"
    executor: "claude-3-opus-20240229" 
    reviewer: "claude-3-haiku-20240307"
    
  limits:
    max_tokens: 4096
    timeout_s: 90
    rate_limit_rpm: 1000
    max_retries: 3
    
  cost_tracking:
    enable: true
    daily_limit_usd: 100.0
    alert_threshold_usd: 80.0
```

### Ollama Backend

```yaml
ollama:
  base_url: "${OLLAMA_HOST}/v1"
  
  models:
    planner: "llama3.1:70b"
    executor: "llama3.1:8b"
    reviewer: "llama3.1:70b" 
    embedder: "nomic-embed-text"
    
  limits:
    max_tokens: 8192
    timeout_s: 300
    rate_limit_rpm: 60  # GPU-limitiert
    max_retries: 2
    
  cost_tracking:
    enable: false  # Lokale Modelle
    
  performance:
    batch_size: 1  # Lokale GPU-Limits
    gpu_memory_threshold: 0.8
```

## Error Handling & Resilience

### Retry Strategy

```python
@dataclass
class RetryConfig:
    max_retries: int = 3
    base_delay_s: float = 1.0
    max_delay_s: float = 60.0
    exponential_base: float = 2.0
    jitter: bool = True
    
    retryable_errors: List[str] = [
        "rate_limit_exceeded",
        "server_error", 
        "timeout",
        "connection_error"
    ]
```

### Circuit Breaker

```python
@dataclass
class CircuitBreakerConfig:
    failure_threshold: int = 5
    recovery_timeout_s: int = 60
    half_open_max_calls: int = 3
    
class CircuitBreakerState(Enum):
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, calls blocked
    HALF_OPEN = "half_open"  # Testing recovery
```

### Cost Envelope

```python
@dataclass
class CostEnvelope:
    """Cost tracking and limiting."""
    daily_budget_usd: float
    current_spend_usd: float
    alert_threshold_pct: float = 0.8
    hard_limit_pct: float = 1.0
    
    def check_budget(self, estimated_cost: float) -> bool:
        """Check if call would exceed budget."""
        pass
        
    def track_usage(self, actual_cost: float) -> None:
        """Record actual usage."""
        pass
```

## Model Routing Strategy

### Intelligent Fallback

```python
@dataclass
class RoutingRule:
    """Definiert Routing-Logik zwischen Providern."""
    primary_provider: str
    fallback_providers: List[str]
    fallback_triggers: List[str]  # ["rate_limit", "timeout", "error"]
    load_balancing: bool = False
    
class ModelRouter:
    """Router für intelligente Provider-Auswahl."""
    
    async def route_request(
        self, 
        request: ModelRequest, 
        role: ModelRole
    ) -> ChatLLM:
        """
        Wählt optimalen Provider basierend auf:
        - Aktuelle Load/Availability
        - Cost constraints
        - Quality requirements
        - Previous performance
        """
        pass
```

## Performance Monitoring

### Metrics Collection

```python
@dataclass
class ModelMetrics:
    """Performance metrics für Provider-Monitoring."""
    provider: str
    model: str
    total_requests: int
    success_rate: float
    avg_latency_ms: float
    p95_latency_ms: float
    avg_cost_per_request: float
    total_cost_usd: float
    error_breakdown: Dict[str, int]
    
class MetricsCollector:
    async def record_request(
        self,
        provider: str,
        request: ModelRequest,
        response: ModelResponse,
        error: Optional[Exception] = None
    ) -> None:
        """Records request metrics for monitoring."""
        pass
```

## Integration mit bestehenden Services

### LangGraph Integration

```python
# Minimale Änderungen in bestehenden Nodes
class PlannerNode:
    def __init__(self):
        # Neu: Model Provider statt direkter OpenAI-Calls
        self.llm_provider = ModelProviderFactory.create_chat_llm(
            provider="anthropic",  # Aus Config
            config=config.get_provider_config("anthropic")
        )
    
    async def __call__(self, state: GraphState) -> Dict[str, Any]:
        # Bestehende Logik bleibt gleich
        request = ModelRequest(
            messages=[{"role": "user", "content": f"Plan for: {state.goal}"}],
            max_tokens=1000
        )
        
        # Nur der Provider-Call ändert sich
        response = await self.llm_provider.plan(request)
        
        # Rest bleibt unverändert
        return self._parse_plan(response.content)
```

### Service Integration

```python
# Erweitert bestehende Services ohne Breaking Changes
class EmailService:
    def __init__(self, account_type: str):
        # Bestehende Initialisierung bleibt
        super().__init__(account_type)
        
        # Neu: Optional LLM für smarte Features
        if config.llm_features_enabled:
            self.llm = ModelProviderFactory.create_chat_llm(
                provider="openai", 
                config=config.get_provider_config("openai")
            )
    
    async def smart_reply(self, email_content: str) -> str:
        """Neue Funktion: LLM-basierte E-Mail-Antworten."""
        if not hasattr(self, 'llm'):
            raise NotImplementedError("LLM features not enabled")
            
        request = ModelRequest(
            messages=[
                {"role": "system", "content": "Du bist ein hilfsamer E-Mail-Assistent."},
                {"role": "user", "content": f"Antworte auf diese E-Mail: {email_content}"}
            ]
        )
        
        response = await self.llm.execute(request)
        return response.content
```

## Security & Privacy

### API Key Management

```python
class SecureKeyManager:
    """Secure handling of API keys."""
    
    @staticmethod
    def get_api_key(provider: str) -> str:
        """
        Retrieve API key from secure storage.
        Priority: Environment -> Keyring -> Config (encrypted)
        """
        pass
    
    @staticmethod
    def rotate_key(provider: str, new_key: str) -> bool:
        """Hot-swap API keys without restart."""
        pass
```

### Data Privacy

```python
@dataclass
class PrivacyConfig:
    """Privacy settings per provider."""
    log_requests: bool = False
    log_responses: bool = False
    data_retention_days: int = 0  # 0 = no retention
    anonymize_pii: bool = True
    allowed_regions: List[str] = ["EU", "US"]
```

## Testing & Validation

### Mock Provider

```python
class MockChatLLM(ChatLLM):
    """Mock implementation für Tests."""
    
    async def plan(self, request: ModelRequest) -> ModelResponse:
        return ModelResponse(
            content="Mock plan: [txt2img, upscale]",
            usage={"tokens_input": 10, "tokens_output": 20, "tokens_total": 30},
            model="mock-model",
            provider="mock",
            latency_ms=100
        )
```

### Provider Validation

```python
class ProviderValidator:
    """Validiert Provider-Implementations."""
    
    async def validate_provider(self, provider: ChatLLM) -> Dict[str, bool]:
        """
        Führt Compliance-Tests aus:
        - Interface compliance
        - Error handling
        - Performance thresholds
        - Cost tracking accuracy
        """
        pass
```

## Migration Strategy

### Backwards Compatibility

1. **Bestehende Imports bleiben funktional:**
   ```python
   # Alt (weiterhin möglich)
   from agents.meta_agent import MetaAgent
   
   # Neu (optional)
   from ai.adapters.model_provider import ModelProviderFactory
   ```

2. **Schrittweise Migration:**
   - Phase 1: Provider parallel zu bestehenden Clients
   - Phase 2: Einzelne Services migrieren
   - Phase 3: Legacy-Code entfernen (optional)

3. **Feature Flags:**
   ```yaml
   features:
     use_model_providers: true
     legacy_mode: false
     cost_tracking: true
   ```

Diese Spezifikation ermöglicht **vendor-agnostische** Model-Integration ohne Breaking Changes am bestehenden Code!