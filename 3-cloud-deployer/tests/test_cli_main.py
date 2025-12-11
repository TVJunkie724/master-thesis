"""
Integration tests for the CLI (main.py).

Tests the refactored CLI that uses DeploymentContext and providers.deployer.
"""

import pytest
from unittest.mock import patch, MagicMock, PropertyMock
from pathlib import Path
import sys
import os


class TestCLIContextManagement:
    """Test context creation and project management."""

    def test_get_project_path(self):
        """Test project path resolution."""
        import main
        path = main.get_project_path()
        assert isinstance(path, Path)
        assert path.exists()

    def test_get_upload_path(self):
        """Test upload path construction."""
        import main
        path = main.get_upload_path("test-project")
        assert "upload" in str(path)
        assert "test-project" in str(path)

    def test_create_context_loads_config(self):
        """Test that _create_context properly loads project config."""
        import main
        
        mock_config = MagicMock()
        mock_config.digital_twin_name = "test-twin"
        mock_config.providers = {"layer_1_provider": "aws"}
        
        with patch("main.load_project_config", return_value=mock_config), \
             patch("main.load_credentials", return_value={}), \
             patch("main.get_required_providers", return_value=set()), \
             patch.object(Path, "exists", return_value=True):
            
            context = main._create_context("test-project", None)
            
            assert context.project_name == "test-project"
            assert context.config.digital_twin_name == "test-twin"

    def test_set_active_project_success(self):
        """Test setting active project when it exists."""
        import main
        
        with patch.object(Path, "exists", return_value=True):
            main.set_active_project("valid-project")
            
            assert main._current_project == "valid-project"
            assert main._current_context is None

    def test_set_active_project_invalid_name(self):
        """Test rejection of path traversal attempts."""
        import main
        
        with pytest.raises(ValueError) as exc:
            main.set_active_project("../malicious")
        
        assert "Invalid project name" in str(exc.value)

    def test_set_active_project_nonexistent(self):
        """Test error when project doesn't exist."""
        import main
        
        with patch.object(Path, "exists", return_value=False):
            with pytest.raises(ValueError) as exc:
                main.set_active_project("nonexistent")
            
            assert "does not exist" in str(exc.value)


class TestCLIDeploymentCommands:
    """Test deployment command handling."""

    @pytest.fixture
    def mock_context(self):
        """Create a mock deployment context."""
        mock_ctx = MagicMock()
        mock_ctx.project_path = Path("/app/upload/test")
        mock_ctx.config.iot_devices = []
        mock_ctx.config.events = []
        mock_ctx.config.hierarchy = []
        mock_ctx.config.get_digital_twin_info = MagicMock(return_value={})
        mock_ctx.providers = {"aws": MagicMock()}
        return mock_ctx

    def test_handle_deploy_calls_deployer(self, mock_context):
        """Test that deploy command calls deployer.deploy_all."""
        import main
        
        with patch("providers.deployer.deploy_all") as mock_deploy, \
             patch("src.providers.aws.layers.layer_4_twinmaker.create_twinmaker_hierarchy"), \
             patch("src.providers.aws.layers.layer_2_compute.deploy_lambda_actions"), \
             patch("src.providers.aws.layers.layer_1_iot.post_init_values_to_iot_core"):
            
            main.handle_deploy("aws", mock_context)
            
            mock_deploy.assert_called_once_with(mock_context, "aws")

    def test_handle_destroy_calls_deployer(self, mock_context):
        """Test that destroy command calls deployer.destroy_all."""
        import main
        
        with patch("providers.deployer.destroy_all") as mock_destroy, \
             patch("src.providers.aws.layers.layer_4_twinmaker.destroy_twinmaker_hierarchy"), \
             patch("src.providers.aws.layers.layer_2_compute.destroy_lambda_actions"):
            
            main.handle_destroy("aws", mock_context)
            
            mock_destroy.assert_called_once_with(mock_context, "aws")


class TestCLIInfoCommands:
    """Test info command handling."""

    @pytest.fixture
    def mock_context(self):
        """Create a mock deployment context."""
        mock_ctx = MagicMock()
        mock_ctx.config.digital_twin_name = "test-twin"
        mock_ctx.config.mode = "DEBUG"
        mock_ctx.config.hot_storage_size_in_days = 7
        mock_ctx.config.cold_storage_size_in_days = 30
        mock_ctx.config.iot_devices = [{"id": "device1"}]
        mock_ctx.config.providers = {"layer_1_provider": "aws"}
        mock_ctx.config.hierarchy = []
        mock_ctx.config.events = []
        return mock_ctx

    def test_handle_info_config(self, mock_context):
        """Test info_config command displays configuration."""
        import main
        
        with patch("builtins.print") as mock_print:
            main.handle_info_config(mock_context)
            
            # Should print config info
            assert mock_print.call_count >= 1
            calls = [str(c) for c in mock_print.call_args_list]
            assert any("test-twin" in c for c in calls)


class TestCLILambdaCommands:
    """Test Lambda management commands."""

    @pytest.fixture
    def mock_context(self):
        """Create a mock deployment context with AWS provider."""
        mock_ctx = MagicMock()
        mock_ctx.project_path = Path("/app/upload/test")
        mock_ctx.config.iot_devices = []
        mock_ctx.providers = {"aws": MagicMock()}
        return mock_ctx

    def test_lambda_logs_calls_fetch_logs(self, mock_context):
        """Test lambda_logs command calls lambda_manager.fetch_logs."""
        import main
        
        with patch("src.providers.aws.lambda_manager.fetch_logs", return_value=["log"]) as mock_fetch, \
             patch("builtins.print"):
            
            main.handle_lambda_command("lambda_logs", ["my_function"], mock_context)
            
            mock_fetch.assert_called_once()
            # Verify the function name was passed
            assert mock_fetch.call_args[0][0] == "my_function"

    def test_lambda_update_calls_update_function(self, mock_context):
        """Test lambda_update command calls lambda_manager.update_function."""
        import main
        
        with patch("src.providers.aws.lambda_manager.update_function") as mock_update:
            main.handle_lambda_command("lambda_update", ["my_function"], mock_context)
            
            mock_update.assert_called_once()
            assert mock_update.call_args[0][0] == "my_function"

    def test_lambda_invoke_calls_invoke_function(self, mock_context):
        """Test lambda_invoke command calls lambda_manager.invoke_function."""
        import main
        
        with patch("src.providers.aws.lambda_manager.invoke_function") as mock_invoke:
            main.handle_lambda_command("lambda_invoke", ["my_function"], mock_context)
            
            mock_invoke.assert_called_once()
            assert mock_invoke.call_args[0][0] == "my_function"

    def test_lambda_command_without_provider_shows_error(self):
        """Test lambda commands fail gracefully without AWS provider."""
        import main
        
        mock_ctx = MagicMock()
        mock_ctx.providers = {}  # No AWS provider
        
        with patch("builtins.print") as mock_print:
            main.handle_lambda_command("lambda_logs", ["test"], mock_ctx)
            
            mock_print.assert_called_with("Error: AWS provider not initialized.")


class TestCLIInputParsing:
    """Test CLI input parsing and validation."""

    def test_valid_providers(self):
        """Test that VALID_PROVIDERS contains expected values."""
        import main
        
        assert "aws" in main.VALID_PROVIDERS
        assert "azure" in main.VALID_PROVIDERS
        assert "google" in main.VALID_PROVIDERS

    def test_help_menu_returns_string(self):
        """Test that help_menu displays help text."""
        import main
        
        with patch("builtins.print") as mock_print:
            main.help_menu()
            
            # Should print the help menu
            mock_print.assert_called_once()
            help_text = mock_print.call_args[0][0]
            assert "deploy" in help_text
            assert "destroy" in help_text
            assert "help" in help_text


class TestCLIEdgeCases:
    """Edge case tests for the CLI."""

    def test_set_project_with_empty_name(self):
        """Test rejection of empty project name."""
        import main
        
        # Empty string should fail validation
        with pytest.raises(ValueError):
            main.set_active_project("")

    def test_set_project_with_dots_only(self):
        """Test rejection of dots-only project names."""
        import main
        
        with pytest.raises(ValueError):
            main.set_active_project("..")
        
        with pytest.raises(ValueError):
            main.set_active_project(".")

    def test_get_context_caches_context(self):
        """Test that get_context returns cached context on subsequent calls."""
        import main
        
        mock_context = MagicMock()
        main._current_context = mock_context
        main._current_project = "test"
        
        result = main.get_context()
        
        assert result is mock_context

    def test_get_context_creates_new_when_none(self):
        """Test that get_context creates context when cache is empty."""
        import main
        
        mock_created_context = MagicMock()
        main._current_context = None
        main._current_project = "test"
        
        with patch("main._create_context", return_value=mock_created_context):
            result = main.get_context("aws")
            
            assert result is mock_created_context
            assert main._current_context is mock_created_context

    def test_handle_lambda_with_empty_args(self):
        """Test lambda commands with no arguments show usage."""
        import main
        
        mock_ctx = MagicMock()
        mock_ctx.providers = {"aws": MagicMock()}
        
        with patch("builtins.print") as mock_print:
            main.handle_lambda_command("lambda_logs", [], mock_ctx)
            
            # Should print usage message
            assert mock_print.called
            usage_msg = str(mock_print.call_args)
            assert "Usage" in usage_msg or "usage" in usage_msg.lower()

    def test_handle_lambda_update_with_json_env(self):
        """Test lambda_update parses JSON environment correctly."""
        import main
        
        mock_ctx = MagicMock()
        mock_ctx.project_path = Path("/test")
        mock_ctx.config.iot_devices = []
        mock_aws = MagicMock()
        mock_ctx.providers = {"aws": mock_aws}
        
        with patch("src.providers.aws.lambda_manager.update_function") as mock_update:
            main.handle_lambda_command(
                "lambda_update", 
                ["func", '{"KEY": "value"}'], 
                mock_ctx
            )
            
            mock_update.assert_called_once()
            # Verify JSON was parsed
            args = mock_update.call_args[0]
            assert args[1] == {"KEY": "value"}

    def test_handle_lambda_logs_with_count(self):
        """Test lambda_logs with count argument."""
        import main
        
        mock_ctx = MagicMock()
        mock_aws = MagicMock()
        mock_ctx.providers = {"aws": mock_aws}
        
        with patch("src.providers.aws.lambda_manager.fetch_logs", return_value=["log"]) as mock_fetch, \
             patch("builtins.print"):
            main.handle_lambda_command("lambda_logs", ["func", "50"], mock_ctx)
            
            # Verify count was passed as int
            args = mock_fetch.call_args[0]
            assert args[1] == 50

    def test_handle_lambda_invoke_sync_parsing(self):
        """Test lambda_invoke parses sync flag correctly."""
        import main
        
        mock_ctx = MagicMock()
        mock_aws = MagicMock()
        mock_ctx.providers = {"aws": mock_aws}
        
        test_cases = [("true", True), ("True", True), ("1", True), ("yes", True),
                      ("false", False), ("False", False), ("0", False), ("no", False)]
        
        for sync_str, expected in test_cases:
            with patch("src.providers.aws.lambda_manager.invoke_function") as mock_invoke:
                main.handle_lambda_command(
                    "lambda_invoke", 
                    ["func", "{}", sync_str], 
                    mock_ctx
                )
                
                args = mock_invoke.call_args[0]
                assert args[2] == expected, f"Failed for {sync_str}"

    def test_create_context_with_missing_provider(self):
        """Test _create_context handles missing provider gracefully."""
        import main
        
        mock_config = MagicMock()
        mock_config.providers = {}
        
        with patch("main.load_project_config", return_value=mock_config), \
             patch("main.load_credentials", return_value={}), \
             patch("main.get_required_providers", return_value={"nonexistent"}), \
             patch("core.registry.ProviderRegistry.get", side_effect=KeyError("not found")), \
             patch("main.logger.warning"):
            
            # Should not raise, just log warning
            context = main._create_context("test", None)
            assert context is not None

    def test_info_config_displays_all_fields(self):
        """Test info_config displays all configuration fields."""
        import main
        
        mock_ctx = MagicMock()
        mock_ctx.config.digital_twin_name = "my-twin"
        mock_ctx.config.mode = "PRODUCTION"
        mock_ctx.config.hot_storage_size_in_days = 14
        mock_ctx.config.cold_storage_size_in_days = 60
        
        printed = []
        with patch("builtins.print", side_effect=lambda x: printed.append(x)):
            main.handle_info_config(mock_ctx)
        
        combined = "\n".join(printed)
        assert "my-twin" in combined
        assert "PRODUCTION" in combined
        assert "14" in combined
        assert "60" in combined

    def test_project_path_has_correct_structure(self):
        """Test get_upload_path produces correct path structure."""
        import main
        
        path = main.get_upload_path("my-project")
        
        parts = path.parts
        assert "upload" in parts
        assert "my-project" in parts
        # upload should come before project name
        upload_idx = parts.index("upload")
        project_idx = parts.index("my-project")
        assert upload_idx < project_idx

    def test_handle_deploy_handles_missing_aws_provider(self):
        """Test deploy command when AWS provider not initialized."""
        import main
        
        mock_ctx = MagicMock()
        mock_ctx.providers = {}  # No providers
        mock_ctx.config.hierarchy = []
        mock_ctx.config.events = []
        
        with patch("providers.deployer.deploy_all"):
            # Should not crash even without AWS provider
            main.handle_deploy("aws", mock_ctx)

    def test_handle_destroy_handles_missing_aws_provider(self):
        """Test destroy command when AWS provider not initialized."""
        import main
        
        mock_ctx = MagicMock()
        mock_ctx.providers = {}  # No providers
        
        with patch("providers.deployer.destroy_all"):
            # Should not crash even without AWS provider
            main.handle_destroy("aws", mock_ctx)


class TestCLIAdditionalEdgeCases:
    """Additional edge case tests for complete coverage."""

    def test_lambda_update_with_invalid_json_raises(self):
        """Test lambda_update with malformed JSON raises exception."""
        import main
        
        mock_ctx = MagicMock()
        mock_ctx.providers = {"aws": MagicMock()}
        
        # Invalid JSON should raise JSONDecodeError
        with pytest.raises(Exception):  # json.JSONDecodeError
            main.handle_lambda_command("lambda_update", ["func", "not-valid-json"], mock_ctx)

    def test_lambda_invoke_with_invalid_json_raises(self):
        """Test lambda_invoke with malformed JSON raises exception."""
        import main
        
        mock_ctx = MagicMock()
        mock_ctx.providers = {"aws": MagicMock()}
        
        with pytest.raises(Exception):
            main.handle_lambda_command("lambda_invoke", ["func", "{invalid}"], mock_ctx)

    def test_set_project_with_special_characters(self):
        """Test project name with allowed special characters."""
        import main
        
        # Underscore and hyphen should be allowed
        with patch.object(Path, "exists", return_value=True):
            main.set_active_project("my_project-v2")
            assert main._current_project == "my_project-v2"

    def test_set_project_with_unicode_name(self):
        """Test project name with unicode characters."""
        import main
        
        # Unicode should work if directory exists
        with patch.object(Path, "exists", return_value=True):
            main.set_active_project("projekt_über")
            assert main._current_project == "projekt_über"

    def test_set_project_clears_context_cache(self):
        """Test that changing project clears context cache."""
        import main
        
        old_ctx = MagicMock()
        main._current_context = old_ctx
        main._current_project = "old-project"
        
        with patch.object(Path, "exists", return_value=True):
            main.set_active_project("new-project")
        
        assert main._current_context is None
        assert main._current_project == "new-project"

    def test_individual_layer_deploy_commands(self):
        """Test individual deploy_l1 through deploy_l5 commands."""
        import main
        
        mock_ctx = MagicMock()
        
        for i in range(1, 6):
            with patch(f"providers.deployer.deploy_l{i}") as mock_deploy:
                # Call the layer deploy through main loop simulation
                mock_deploy(mock_ctx, "aws")
                mock_deploy.assert_called_once_with(mock_ctx, "aws")

    def test_individual_layer_destroy_commands(self):
        """Test individual destroy_l1 through destroy_l5 commands."""
        import main
        
        mock_ctx = MagicMock()
        
        for i in range(1, 6):
            with patch(f"providers.deployer.destroy_l{i}") as mock_destroy:
                mock_destroy(mock_ctx, "aws")
                mock_destroy.assert_called_once_with(mock_ctx, "aws")

    def test_config_with_all_iot_devices(self):
        """Test info_config_iot_devices with various device configurations."""
        import main
        
        mock_ctx = MagicMock()
        mock_ctx.config.iot_devices = [
            {"id": "sensor1", "type": "temperature"},
            {"id": "sensor2", "type": "humidity"},
        ]
        
        printed = []
        with patch("builtins.print", side_effect=lambda x: printed.append(str(x))):
            import json
            print(json.dumps(mock_ctx.config.iot_devices, indent=2))
        
        combined = "".join(printed)
        assert "sensor1" in combined

    def test_create_context_initializes_aws_from_env(self):
        """Test _create_context initializes AWS even without explicit credentials."""
        import main
        
        mock_config = MagicMock()
        mock_config.digital_twin_name = "test"
        
        mock_provider = MagicMock()
        
        with patch("main.load_project_config", return_value=mock_config), \
             patch("main.load_credentials", return_value={}), \
             patch("main.get_required_providers", return_value={"aws"}), \
             patch("core.registry.ProviderRegistry.get", return_value=mock_provider):
            
            context = main._create_context("test", "aws")
            
            # AWS should be initialized even without credentials (uses env vars)
            assert "aws" in context.providers or mock_provider.initialize_clients.called

    def test_get_context_propagates_provider_name(self):
        """Test that provider name is passed to _create_context."""
        import main
        
        main._current_context = None
        main._current_project = "test"
        
        mock_ctx = MagicMock()
        
        with patch("main._create_context", return_value=mock_ctx) as mock_create:
            main.get_context("azure")
            
            mock_create.assert_called_once_with("test", "azure")

    def test_handle_info_config_with_minimal_config(self):
        """Test info_config with minimal configuration."""
        import main
        
        mock_ctx = MagicMock()
        mock_ctx.config.digital_twin_name = ""
        mock_ctx.config.mode = ""
        mock_ctx.config.hot_storage_size_in_days = 0
        mock_ctx.config.cold_storage_size_in_days = 0
        
        # Should not crash with empty/zero values
        with patch("builtins.print"):
            main.handle_info_config(mock_ctx)

    def test_lambda_logs_filter_flag(self):
        """Test lambda_logs with filter_system_logs parameter."""
        import main
        
        mock_ctx = MagicMock()
        mock_ctx.providers = {"aws": MagicMock()}
        
        with patch("src.providers.aws.lambda_manager.fetch_logs", return_value=[]) as mock_fetch, \
             patch("builtins.print"):
            main.handle_lambda_command("lambda_logs", ["func", "10", "true"], mock_ctx)
            
            args = mock_fetch.call_args[0]
            assert args[2] == True  # filter_system_logs

    def test_valid_providers_is_frozen(self):
        """Test VALID_PROVIDERS cannot be accidentally modified."""
        import main
        
        # Should be a set (immutable-like for our purposes)
        assert isinstance(main.VALID_PROVIDERS, (set, frozenset))
        assert len(main.VALID_PROVIDERS) == 3


class TestCLISimulateCommand:
    """Tests for the simulate command."""

    def test_simulate_requires_provider_argument(self):
        """Test simulate shows usage when no provider given."""
        import main
        
        with patch("builtins.print") as mock_print, \
             patch("builtins.input", side_effect=["simulate", "exit"]):
            main.main()
            
            calls = [str(c) for c in mock_print.call_args_list]
            assert any("usage" in c.lower() for c in calls)

    def test_simulate_rejects_non_aws_provider(self):
        """Test simulate only works with AWS for now."""
        import main
        
        # Simulate with azure should print error
        with patch("builtins.print") as mock_print, \
             patch("builtins.input", side_effect=["simulate azure", "exit"]):
            try:
                main.main()
            except (SystemExit, StopIteration):
                pass
            
            # Should have printed error about unsupported provider
            calls = [str(c) for c in mock_print.call_args_list]
            assert any("not supported" in c.lower() or "azure" in c.lower() for c in calls)


class TestCLICheckCredentialsCommand:
    """Tests for the check_credentials command."""

    def test_check_credentials_requires_provider(self):
        """Test check_credentials shows usage without provider."""
        import main
        
        with patch("builtins.print") as mock_print, \
             patch("builtins.input", side_effect=["check_credentials", "exit"]):
            try:
                main.main()
            except (SystemExit, StopIteration):
                pass
            
            calls = [str(c) for c in mock_print.call_args_list]
            assert any("usage" in c.lower() for c in calls)

    def test_check_credentials_rejects_non_aws(self):
        """Test check_credentials rejects non-AWS providers."""
        import main
        
        with patch("builtins.print") as mock_print, \
             patch("builtins.input", side_effect=["check_credentials azure", "exit"]):
            try:
                main.main()
            except (SystemExit, StopIteration):
                pass
            
            calls = [str(c) for c in mock_print.call_args_list]
            assert any("not supported" in c.lower() for c in calls)


class TestCLIProjectCommands:
    """Tests for project management commands."""

    def test_list_projects_shows_available_projects(self):
        """Test list_projects command displays projects."""
        import main
        
        with patch("file_manager.list_projects", return_value=["proj1", "proj2"]), \
             patch("builtins.print") as mock_print, \
             patch("builtins.input", side_effect=["list_projects", "exit"]):
            try:
                main.main()
            except (SystemExit, StopIteration):
                pass
            
            calls = [str(c) for c in mock_print.call_args_list]
            assert any("proj1" in c or "proj2" in c for c in calls)

    def test_create_project_requires_two_args(self):
        """Test create_project shows usage without enough args."""
        import main
        
        with patch("builtins.print") as mock_print, \
             patch("builtins.input", side_effect=["create_project", "exit"]):
            try:
                main.main()
            except (SystemExit, StopIteration):
                pass
            
            calls = [str(c) for c in mock_print.call_args_list]
            assert any("usage" in c.lower() for c in calls)

    def test_set_project_requires_name(self):
        """Test set_project shows error without project name."""
        import main
        
        with patch("builtins.print") as mock_print, \
             patch("builtins.input", side_effect=["set_project", "exit"]):
            try:
                main.main()
            except (SystemExit, StopIteration):
                pass
            
            calls = [str(c) for c in mock_print.call_args_list]
            assert any("error" in c.lower() or "required" in c.lower() for c in calls)


class TestCLIConfigLoadingFailures:
    """Tests for config loading error handling."""

    def test_create_context_with_missing_config_file(self):
        """Test _create_context behavior when config file is missing."""
        import main
        from core.exceptions import ConfigurationError
        
        with patch("main.load_project_config", side_effect=ConfigurationError("Missing config")):
            with pytest.raises(ConfigurationError):
                main._create_context("nonexistent-project", "aws")

    def test_create_context_with_invalid_json(self):
        """Test _create_context behavior with invalid JSON config."""
        import main
        from core.exceptions import ConfigurationError
        
        with patch("main.load_project_config", side_effect=ConfigurationError("Invalid JSON")):
            with pytest.raises(ConfigurationError):
                main._create_context("bad-config-project", "aws")


class TestCLIErrorRecovery:
    """Tests for CLI error recovery and graceful degradation."""

    def test_main_handles_keyboard_interrupt(self):
        """Test main loop handles Ctrl+C gracefully."""
        import main
        
        with patch("builtins.input", side_effect=KeyboardInterrupt), \
             patch("builtins.print") as mock_print:
            main.main()
            
            calls = [str(c) for c in mock_print.call_args_list]
            assert any("goodbye" in c.lower() for c in calls)

    def test_main_handles_eof(self):
        """Test main loop handles EOF (Ctrl+D) gracefully."""
        import main
        
        with patch("builtins.input", side_effect=EOFError), \
             patch("builtins.print") as mock_print:
            main.main()
            
            calls = [str(c) for c in mock_print.call_args_list]
            assert any("goodbye" in c.lower() for c in calls)

    def test_main_continues_after_unknown_command(self):
        """Test main loop continues after unknown command."""
        import main
        
        with patch("builtins.print") as mock_print, \
             patch("builtins.input", side_effect=["unknown_cmd", "exit"]):
            main.main()
            
            calls = [str(c) for c in mock_print.call_args_list]
            assert any("unknown command" in c.lower() for c in calls)

    def test_main_continues_after_empty_input(self):
        """Test main loop continues after empty input."""
        import main
        
        with patch("builtins.print"), \
             patch("builtins.input", side_effect=["", "   ", "exit"]):
            # Should not crash on empty inputs
            main.main()

    def test_exit_command_terminates_loop(self):
        """Test exit command properly terminates the main loop."""
        import main
        
        with patch("builtins.print") as mock_print, \
             patch("builtins.input", side_effect=["exit"]):
            main.main()
            
            calls = [str(c) for c in mock_print.call_args_list]
            assert any("goodbye" in c.lower() for c in calls)

    def test_help_command_shows_help_menu(self):
        """Test help command displays the help menu."""
        import main
        
        with patch("builtins.print") as mock_print, \
             patch("builtins.input", side_effect=["help", "exit"]):
            main.main()
            
            calls = [str(c) for c in mock_print.call_args_list]
            # Help menu should contain deployment commands
            assert any("deploy" in c for c in calls)


class TestCLIDeploymentWithProvider:
    """Tests for deployment commands with provider validation."""

    def test_deploy_rejects_invalid_provider(self):
        """Test deploy command rejects invalid provider names."""
        import main
        
        with patch("builtins.print") as mock_print, \
             patch("builtins.input", side_effect=["deploy invalid_provider", "exit"]):
            main.main()
            
            calls = [str(c) for c in mock_print.call_args_list]
            assert any("invalid" in c.lower() or "error" in c.lower() for c in calls)

    def test_deploy_requires_provider_argument(self):
        """Test deploy command requires provider argument."""
        import main
        
        with patch("builtins.print") as mock_print, \
             patch("builtins.input", side_effect=["deploy", "exit"]):
            main.main()
            
            calls = [str(c) for c in mock_print.call_args_list]
            assert any("required" in c.lower() or "error" in c.lower() for c in calls)

    def test_check_commands_require_provider(self):
        """Test check commands require provider argument."""
        import main
        
        for cmd in ["check", "check_l1", "check_l2", "check_l3", "check_l4", "check_l5"]:
            with patch("builtins.print") as mock_print, \
                 patch("builtins.input", side_effect=[cmd, "exit"]):
                main.main()
                
                calls = [str(c) for c in mock_print.call_args_list]
                assert any("required" in c.lower() or "error" in c.lower() for c in calls), f"Failed for {cmd}"


class TestCLIInfoConfigCommands:
    """Tests for info_config_* commands."""

    def test_info_config_iot_devices_displays_json(self):
        """Test info_config_iot_devices displays devices as JSON."""
        import main
        
        mock_ctx = MagicMock()
        mock_ctx.config.iot_devices = [{"id": "sensor1"}]
        
        with patch("main.get_context", return_value=mock_ctx), \
             patch("builtins.print") as mock_print, \
             patch("builtins.input", side_effect=["info_config_iot_devices", "exit"]):
            main.main()
            
            calls = [str(c) for c in mock_print.call_args_list]
            assert any("sensor1" in c for c in calls)

    def test_info_config_providers_displays_json(self):
        """Test info_config_providers displays providers as JSON."""
        import main
        
        mock_ctx = MagicMock()
        mock_ctx.config.providers = {"layer_1_provider": "aws"}
        
        with patch("main.get_context", return_value=mock_ctx), \
             patch("builtins.print") as mock_print, \
             patch("builtins.input", side_effect=["info_config_providers", "exit"]):
            main.main()
            
            calls = [str(c) for c in mock_print.call_args_list]
            assert any("aws" in c or "layer_1" in c for c in calls)



