import pytest
from unittest.mock import patch, MagicMock
import os
import sys

# We need to modify the path to import from the core modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import json
from core.config import AppSettings
from pydantic import ValidationError

@pytest.fixture
def mock_env_vars(monkeypatch):
    """Fixture to mock environment variables."""
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "fake-token")
    monkeypatch.setenv("OLLAMA_HOST", "http://localhost:11434")
    # Add other required variables with dummy values if needed
    return monkeypatch

def test_config_loading_success(mock_env_vars):
    """
    Tests that the AppSettings model loads successfully when all required
    environment variables are set.
    """
    try:
        settings = AppSettings()
        assert settings.TELEGRAM_BOT_TOKEN == "fake-token"
        assert settings.OLLAMA_HOST == "http://localhost:11434"
    except ValidationError as e:
        pytest.fail(f"Configuration loading failed unexpectedly: {e}")

def test_config_loading_missing_required_variable(monkeypatch):
    """
    Tests that AppSettings raises a ValidationError if a required
    environment variable (TELEGRAM_BOT_TOKEN) is missing.
    """
    # Ensure the required variable is not set
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)

    with pytest.raises(ValidationError) as excinfo:
        AppSettings()

    # Check that the error message contains the name of the missing variable
    assert "TELEGRAM_BOT_TOKEN" in str(excinfo.value)
    assert "Field required" in str(excinfo.value)

# --- RBAC Tests ---
from core.security import RBACService, Role

@pytest.fixture
def rbac_service():
    """Returns an instance of the RBACService."""
    return RBACService()

def test_rbac_guest_permissions(rbac_service):
    """Tests the default permissions for the GUEST role."""
    assert rbac_service.check_permission(Role.GUEST, "execute", "generate_image") is True
    assert rbac_service.check_permission(Role.GUEST, "execute", "upscale_image") is False
    assert rbac_service.check_permission(Role.GUEST, "manage", "rbac:roles") is False

def test_rbac_editor_permissions(rbac_service):
    """Tests the permissions for the EDITOR role."""
    assert rbac_service.check_permission(Role.EDITOR, "execute", "generate_image") is True
    assert rbac_service.check_permission(Role.EDITOR, "execute", "upscale_image") is True
    assert rbac_service.check_permission(Role.EDITOR, "manage", "rbac:roles") is False

def test_rbac_admin_permissions(rbac_service):
    """Tests the permissions for the ADMIN role."""
    assert rbac_service.check_permission(Role.ADMIN, "execute", "generate_image") is True
    assert rbac_service.check_permission(Role.ADMIN, "execute", "upscale_image") is True
    assert rbac_service.check_permission(Role.ADMIN, "manage", "rbac:roles") is True

# --- Audit Logger Tests ---
from core.audit import audit_tool_call

@patch('core.audit.audit_logger')
def test_audit_tool_call_denied(mock_audit_logger):
    """Tests that a DENIED tool call is audited correctly."""
    audit_tool_call(
        correlation_id="test-corr-id",
        user_id="test-user",
        tool_name="upscale_image",
        params={"scale": 4},
        status="DENIED",
        message="Permission denied for role GUEST"
    )

    mock_audit_logger.info.assert_called_once()
    call_args = mock_audit_logger.info.call_args[0][0]
    log_data = json.loads(call_args)

    assert log_data["event_type"] == "tool_call_attempt"
    assert log_data["correlation_id"] == "test-corr-id"
    assert log_data["user_id"] == "test-user"
    assert log_data["tool_name"] == "upscale_image"
    assert log_data["status"] == "DENIED"
    assert log_data["message"] == "Permission denied for role GUEST"
    assert "params_hash" in log_data
