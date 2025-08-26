# Tool Execution Policies

## Overview

Definiert Sicherheits-, Ressourcen- und Governance-Policies für alle Kern-Tools. Gewährleistet sicheren, auditbaren und performanten Tool-Einsatz.

## Global Security Policies

### Content Security

```yaml
content_filtering:
  enabled: true
  
  # Forbidden content categories
  blocked_categories:
    - "nsfw"
    - "violence" 
    - "hate_speech"
    - "illegal_content"
    - "copyrighted_material"
    - "personal_data"
  
  # Text content scanning
  text_scanning:
    enabled: true
    scan_prompts: true
    scan_descriptions: true
    scan_user_input: true
    
  # Image content scanning
  image_scanning:
    enabled: false  # Requires external service
    confidence_threshold: 0.8
    
  # Action on violation
  violation_response: "block_request"  # "block_request", "sanitize", "flag_and_continue"
```

### File Security

```yaml
file_security:
  # Allowed file types per tool
  allowed_extensions:
    sd_txt2img: []  # No input files
    sd_img2img: [".jpg", ".jpeg", ".png", ".bmp", ".tiff"]
    upscale: [".jpg", ".jpeg", ".png", ".bmp"]
    upload: [".jpg", ".jpeg", ".png", ".mp4", ".mov", ".wav", ".mp3"]
    asr: [".wav", ".mp3", ".m4a", ".flac", ".ogg"]
    tts: []  # No input files
  
  # File size limits (bytes)
  max_file_sizes:
    sd_img2img: 52428800      # 50MB
    upscale: 104857600        # 100MB  
    upload: 52428800          # 50MB (default)
    upload_youtube: 2147483648 # 2GB
    upload_tiktok: 524288000   # 500MB
    asr: 104857600            # 100MB
  
  # Virus scanning
  virus_scanning:
    enabled: false  # Requires ClamAV or similar
    quarantine_on_detection: true
    
  # Path restrictions
  path_restrictions:
    allowed_directories: ["/artifacts", "/uploads", "/tmp"]
    forbidden_directories: ["/etc", "/home", "/root", "/var"]
    path_traversal_detection: true
```

## Tool-Specific Policies

### SD Text2Img Policies

```yaml
sd_txt2img:
  resource_limits:
    # GPU limits
    max_gpu_memory_mb: 8192
    max_inference_time_s: 120
    gpu_lock_timeout_s: 300
    
    # Resolution limits
    max_total_pixels: 1048576  # 1024x1024 max
    min_resolution: 256
    max_resolution: 1024
    required_multiple: 64      # SD requirement
    
    # Generation limits
    max_steps: 50
    min_steps: 10
    max_cfg_scale: 20.0
    min_cfg_scale: 1.0
    
  safe_defaults:
    steps: 20
    cfg_scale: 7.0
    width: 512
    height: 512
    model: "sd15"
    
  rate_limits:
    requests_per_hour: 100
    requests_per_day: 500
    concurrent_requests: 1     # GPU limitation
    
  content_policies:
    prompt_max_length: 500
    negative_prompt_max_length: 200
    forbidden_keywords: ["nsfw", "nude", "explicit", "gore"]
    
  audit_requirements:
    log_prompts: true
    log_generation_params: true
    log_execution_time: true
    log_gpu_usage: true
    retention_days: 90
```

### SD Img2Img Policies

```yaml
sd_img2img:
  resource_limits:
    max_gpu_memory_mb: 8192
    max_inference_time_s: 180
    max_input_file_size_mb: 50
    
  safe_defaults:
    strength: 0.8
    steps: 20
    cfg_scale: 7.0
    model: "sd15"
    
  rate_limits:
    requests_per_hour: 50
    requests_per_day: 200
    concurrent_requests: 1
    
  security_policies:
    scan_input_images: false   # Requires external service
    validate_image_format: true
    check_image_dimensions: true
    max_image_width: 2048
    max_image_height: 2048
    
  audit_requirements:
    log_input_image_path: true
    log_transformation_params: true
    log_output_artifacts: true
    retention_days: 90
```

### Upscale Policies

```yaml
upscale:
  resource_limits:
    max_gpu_memory_mb: 12288   # Upscaling requires more memory
    max_inference_time_s: 300
    max_input_file_size_mb: 100
    
  safe_defaults:
    scale: 2
    model: "RealESRGAN_x2plus"
    
  rate_limits:
    requests_per_hour: 30
    requests_per_day: 100
    concurrent_requests: 1
    
  scale_policies:
    allowed_scales: [2, 4]
    scale_model_compatibility:
      "RealESRGAN_x2plus": [2]
      "RealESRGAN_x4plus": [4]
      "ESRGAN_x4": [4]
    max_output_dimensions: 4096  # 4K max
    
  audit_requirements:
    log_input_dimensions: true
    log_scale_factor: true
    log_model_used: true
    log_output_file_size: true
    retention_days: 30
```

### Upload Policies

```yaml
upload:
  resource_limits:
    max_concurrent_uploads: 5
    upload_timeout_s: 600      # 10 minutes
    retry_attempts: 3
    
  safe_defaults:
    target: "disk"
    
  rate_limits:
    # Per target limits
    telegram:
      requests_per_hour: 100
      requests_per_day: 500
      max_file_size_mb: 50
      
    youtube:
      requests_per_hour: 10
      requests_per_day: 50
      max_file_size_mb: 2048
      required_fields: ["title"]
      
    tiktok:
      requests_per_hour: 20
      requests_per_day: 100
      max_file_size_mb: 500
      
    instagram:
      requests_per_hour: 30
      requests_per_day: 150
      max_file_size_mb: 100
      
    disk:
      requests_per_hour: 200
      requests_per_day: 1000
      max_file_size_mb: 500
  
  security_policies:
    validate_file_exists: true
    check_file_permissions: true
    scan_file_content: false   # Optional virus scanning
    validate_mime_type: true
    
  content_policies:
    title_max_length: 100
    description_max_length: 5000
    tags_max_count: 50
    tag_max_length: 50
    tag_format_regex: "^[a-zA-Z0-9_-]+$"
    
  audit_requirements:
    log_upload_target: true
    log_file_path: true
    log_file_size: true
    log_upload_status: true
    log_external_ids: true     # YouTube video ID, etc.
    retention_days: 365        # Longer retention for uploads
```

### ASR (Speech Recognition) Policies

```yaml
asr:
  resource_limits:
    max_audio_duration_s: 3600  # 1 hour
    max_file_size_mb: 100
    max_processing_time_s: 600  # 10 minutes
    
  safe_defaults:
    language: "auto"
    model: "whisper-base"
    temperature: 0.0
    
  rate_limits:
    requests_per_hour: 50
    requests_per_day: 200
    concurrent_requests: 3     # CPU-based, can parallelize
    
  audio_policies:
    supported_formats: ["wav", "mp3", "m4a", "flac", "ogg"]
    max_sample_rate: 48000
    max_bitrate: 320           # kbps
    auto_normalize: true
    
  privacy_policies:
    log_transcriptions: false  # Privacy-sensitive
    auto_delete_audio: true
    retention_days: 1          # Minimal retention
    
  audit_requirements:
    log_audio_duration: true
    log_language_detected: true
    log_model_used: true
    log_processing_time: true
    retention_days: 30
```

### TTS (Text-to-Speech) Policies

```yaml
tts:
  resource_limits:
    max_text_length: 1000
    max_synthesis_time_s: 60
    max_output_duration_s: 300  # 5 minutes max audio
    
  safe_defaults:
    voice: "de-speaker"
    speed: 1.0
    pitch: 1.0
    emotion: "neutral"
    
  rate_limits:
    requests_per_hour: 100
    requests_per_day: 500
    concurrent_requests: 3
    
  voice_policies:
    available_voices: ["de-speaker", "en-speaker", "female", "male", "neutral"]
    speed_range: [0.5, 2.0]
    pitch_range: [0.5, 2.0]
    supported_emotions: ["neutral", "happy", "sad", "angry", "excited", "calm"]
    
  content_policies:
    text_min_length: 1
    text_max_length: 1000
    forbidden_content: ["personal_data", "phone_numbers", "addresses"]
    language_detection: true
    
  audit_requirements:
    log_text_input: false      # Privacy consideration
    log_text_length: true
    log_voice_used: true
    log_synthesis_params: true
    log_output_duration: true
    retention_days: 7
```

## Role-Based Access Policies

### Guest Users

```yaml
guest_policies:
  allowed_tools: ["sd_txt2img", "asr", "tts"]
  
  reduced_limits:
    sd_txt2img:
      requests_per_hour: 10
      max_steps: 20
      max_resolution: 512
      
    asr:
      requests_per_hour: 5
      max_duration_s: 300      # 5 minutes
      
    tts:
      requests_per_hour: 20
      max_text_length: 200
      
  disabled_features:
    - "upscale"
    - "upload_youtube"
    - "upload_tiktok"
    - "upload_instagram"
    - "sd_img2img"
```

### Regular Users

```yaml
user_policies:
  allowed_tools: ["sd_txt2img", "sd_img2img", "upscale", "asr", "tts", "upload"]
  
  standard_limits:
    # Use default limits from tool-specific policies
    
  upload_restrictions:
    allowed_targets: ["telegram", "disk", "youtube", "tiktok"]
    prohibited_targets: ["instagram"]  # Requires special permission
```

### Admin Users

```yaml
admin_policies:
  allowed_tools: "*"  # All tools
  
  enhanced_limits:
    # 2x standard limits for most tools
    multiplier: 2.0
    
  special_permissions:
    - "bypass_content_filter"
    - "high_resolution_generation"
    - "extended_processing_time"
    - "bulk_operations"
    
  audit_override:
    extended_retention_days: 365
    detailed_logging: true
```

## Resource Management Policies

### GPU Resource Management

```yaml
gpu_management:
  allocation_strategy: "first_come_first_served"
  
  resource_pools:
    high_priority: 
      tools: ["sd_txt2img", "sd_img2img", "upscale"]
      max_concurrent: 1
      timeout_s: 300
      
    low_priority:
      tools: ["batch_operations"]
      max_concurrent: 1
      timeout_s: 600
      
  memory_management:
    gpu_memory_threshold: 0.9  # 90% usage threshold
    auto_cleanup: true
    force_cleanup_threshold: 0.95
    
  scheduling_policies:
    queue_max_size: 50
    queue_timeout_s: 1800      # 30 minutes
    priority_boost_after_s: 600 # Boost priority after 10 minutes
```

### Storage Management

```yaml
storage_management:
  artifact_lifecycle:
    auto_cleanup_enabled: true
    default_retention_days: 30
    
  cleanup_policies:
    temp_files_retention_hours: 24
    failed_artifacts_retention_days: 7
    large_files_priority_cleanup: true  # >100MB cleaned first
    
  storage_quotas:
    guest_quota_gb: 1
    user_quota_gb: 10
    admin_quota_gb: 100
    
  disk_space_management:
    min_free_space_gb: 10
    cleanup_threshold_pct: 85
    emergency_cleanup_threshold_pct: 95
```

## Monitoring & Alerting Policies

### Performance Monitoring

```yaml
performance_monitoring:
  metrics_collection:
    enabled: true
    granularity: "per_request"
    
  thresholds:
    max_response_time_s: 300
    max_queue_wait_time_s: 600
    min_success_rate_pct: 95
    max_error_rate_pct: 5
    
  alerting:
    alert_on_threshold_breach: true
    alert_channels: ["slack", "email"]
    alert_cooldown_minutes: 15
```

### Security Monitoring

```yaml
security_monitoring:
  anomaly_detection:
    enabled: true
    unusual_usage_multiplier: 3.0  # 3x normal usage triggers alert
    
  suspicious_activity:
    rapid_requests: 
      threshold_per_minute: 20
      action: "rate_limit"
      
    content_violations:
      threshold_per_hour: 5
      action: "temporary_ban"
      
    resource_abuse:
      cpu_usage_threshold_pct: 90
      memory_usage_threshold_pct: 90
      action: "throttle"
```

## Audit & Compliance Policies

### Audit Logging

```yaml
audit_logging:
  required_fields:
    - "timestamp"
    - "user_id" 
    - "tool_name"
    - "request_params"
    - "execution_time_ms"
    - "success_status"
    - "resource_usage"
    
  optional_fields:
    - "user_agent"
    - "ip_address"
    - "session_id"
    - "artifacts_produced"
    
  log_formats:
    structured: true           # JSON format
    include_stack_traces: true # For errors
    
  retention_policies:
    audit_logs_retention_days: 365
    error_logs_retention_days: 90
    performance_logs_retention_days: 30
```

### Compliance Requirements

```yaml
compliance:
  data_protection:
    gdpr_compliance: true
    data_minimization: true
    user_consent_required: true
    right_to_deletion: true
    
  content_regulations:
    age_appropriate_content: true
    copyright_compliance: true
    platform_terms_compliance: true
    
  audit_trails:
    immutable_logs: true
    log_integrity_checks: true
    audit_log_backup: true
    
  reporting:
    monthly_usage_reports: true
    security_incident_reports: true
    compliance_status_reports: true
```

## Emergency Procedures

### Circuit Breaker Policies

```yaml
circuit_breaker:
  failure_thresholds:
    consecutive_failures: 5
    error_rate_pct: 20
    response_time_multiplier: 3.0
    
  recovery_procedures:
    recovery_timeout_s: 300
    health_check_interval_s: 30
    gradual_traffic_restoration: true
    
  escalation:
    auto_disable_after_failures: 10
    admin_notification: true
    fallback_to_degraded_mode: true
```

### Incident Response

```yaml
incident_response:
  severity_levels:
    critical: "System-wide outage"
    high: "Service degradation" 
    medium: "Individual tool failure"
    low: "Performance issues"
    
  response_procedures:
    critical:
      response_time_minutes: 5
      auto_failover: true
      immediate_notification: true
      
    high:
      response_time_minutes: 15
      degraded_mode: true
      stakeholder_notification: true
      
  recovery_validation:
    automated_health_checks: true
    manual_verification_required: true
    user_acceptance_testing: true
```

Diese Policies gewährleisten **sicheren, auditbaren und performanten** Tool-Einsatz mit **klaren Limits und Governance-Regeln**!