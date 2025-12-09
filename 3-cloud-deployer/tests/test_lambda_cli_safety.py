"""
Tests for Lambda CLI safety checks.

These tests verify that Lambda operations in the CLI properly validate
project context before executing.
"""

import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path


@pytest.fixture
def mock_cli_context():
    """Mock the context creation for CLI tests."""
    mock_context = MagicMock()
    mock_context.project_path = Path("/app/upload/test_proj")
    mock_context.config.iot_devices = []
    
    mock_aws_provider = MagicMock()
    mock_context.providers = {"aws": mock_aws_provider}
    
    return mock_context, mock_aws_provider


def test_get_context_creates_context_for_project(mock_cli_context):
    """Test that get_context properly creates a context."""
    mock_context, _ = mock_cli_context
    
    with patch("main._create_context", return_value=mock_context):
        import main
        main._current_project = "test_proj"
        main._current_context = None
        
        result = main.get_context("aws")
        
        assert result is mock_context


def test_set_active_project_validates_directory():
    """Test that set_active_project validates the project directory exists."""
    import main
    
    with patch.object(Path, 'exists', return_value=False):
        with pytest.raises(ValueError) as exc:
            main.set_active_project("nonexistent_project")
        
        assert "does not exist" in str(exc.value)


def test_set_active_project_rejects_path_traversal():
    """Test that set_active_project rejects path traversal attempts."""
    import main
    
    with pytest.raises(ValueError) as exc:
        main.set_active_project("../malicious")
    
    assert "Invalid project name" in str(exc.value)


def test_set_active_project_clears_cached_context():
    """Test that switching projects clears the cached context."""
    import main
    
    # Set up initial state
    main._current_project = "old_project"
    main._current_context = MagicMock()
    
    with patch.object(Path, 'exists', return_value=True):
        main.set_active_project("new_project")
    
    assert main._current_project == "new_project"
    assert main._current_context is None


def test_handle_lambda_command_requires_aws_provider(mock_cli_context):
    """Test that lambda commands fail gracefully without AWS provider."""
    import main
    
    mock_context, _ = mock_cli_context
    mock_context.providers = {}  # No providers
    
    # Should print error message, not raise
    with patch("builtins.print") as mock_print:
        main.handle_lambda_command("lambda_logs", ["test_func"], mock_context)
        mock_print.assert_called_with("Error: AWS provider not initialized.")


def test_handle_lambda_command_passes_provider_to_lambda_manager(mock_cli_context):
    """Test that lambda commands pass provider to lambda_manager."""
    import main
    mock_context, mock_aws_provider = mock_cli_context
    
    with patch("src.providers.aws.lambda_manager.fetch_logs") as mock_fetch:
        mock_fetch.return_value = ["log line"]
        
        with patch("builtins.print"):
            main.handle_lambda_command("lambda_logs", ["test_func"], mock_context)
        
        mock_fetch.assert_called_once()
        # Verify provider was passed
        call_kwargs = mock_fetch.call_args.kwargs
        assert call_kwargs.get("provider") is mock_aws_provider
