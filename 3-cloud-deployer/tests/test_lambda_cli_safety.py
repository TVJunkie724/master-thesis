import pytest
from unittest.mock import patch, MagicMock
import sys
import os
import json

# Ensure src is in path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

import main
import globals

@pytest.fixture
def mock_dependencies():
    # We need to mock file_manager which is imported locally. 
    # Best way is to mock it in sys.modules or patch 'file_manager' if it can be imported.
    # Since we appended src to path, we can import it here.
    import file_manager
    
    with patch("main.lambda_manager") as mock_lambda, \
         patch("file_manager.list_projects") as mock_list_projects, \
         patch("main.logger") as mock_logger:
        
        # Setup default mock behaviors
        mock_list_projects.return_value = ["template", "test_proj", "other_proj"]
        
        yield {
            "lambda": mock_lambda,
            "fm": MagicMock(list_projects=mock_list_projects), # Usage wrapper
            "logger": mock_logger
        }

def run_cli_command(command_str, mock_deps):
    """Runs a single CLI command by mocking input and exiting immediately."""
    with patch("builtins.input", side_effect=[command_str, "exit"]):
        try:
            main.main()
        except SystemExit:
            pass

def test_lambda_update_safety_check_pass(mock_dependencies):
    globals.CURRENT_PROJECT = "test_proj"
    
    # Command: update func1 {} test_proj
    # Should pass because project matches
    run_cli_command('lambda_update func1 {} test_proj', mock_dependencies)
    
    mock_dependencies["lambda"].update_function.assert_called_with("func1", {})
    mock_dependencies["logger"].error.assert_not_called()

def test_lambda_update_safety_check_fail(mock_dependencies):
    globals.CURRENT_PROJECT = "test_proj"
    
    # Command: update func1 {} other_proj
    # Should fail because mismatch
    run_cli_command('lambda_update func1 {} other_proj', mock_dependencies)
    
    mock_dependencies["lambda"].update_function.assert_not_called()
    mock_dependencies["logger"].error.assert_any_call("SAFETY ERROR: Requested project 'other_proj' does not match active project 'test_proj'.")

def test_lambda_invoke_safety_check_pass(mock_dependencies):
    globals.CURRENT_PROJECT = "test_proj"
    
    # Command: invoke func1 {} true test_proj
    run_cli_command('lambda_invoke func1 {} true test_proj', mock_dependencies)
    
    mock_dependencies["lambda"].invoke_function.assert_called_with("func1", {}, True)

def test_lambda_invoke_safety_check_fail(mock_dependencies):
    globals.CURRENT_PROJECT = "test_proj"
    
    # Command: invoke func1 {} true other_proj
    run_cli_command('lambda_invoke func1 {} true other_proj', mock_dependencies)
    
    mock_dependencies["lambda"].invoke_function.assert_not_called()
    mock_dependencies["logger"].error.assert_any_call("SAFETY ERROR: Requested project 'other_proj' does not match active project 'test_proj'.")

def test_lambda_implicit_project(mock_dependencies):
    globals.CURRENT_PROJECT = "test_proj"
    
    # Command: invoke func1 {}
    # Should work on current project implicitly
    run_cli_command('lambda_invoke func1 {}', mock_dependencies)
    
    mock_dependencies["lambda"].invoke_function.assert_called_with("func1", {})

def test_lambda_ambiguity_handling(mock_dependencies):
    globals.CURRENT_PROJECT = "test_proj"
    # Project named "sync" equivalent handling? 
    # If we have a project named "true" and we call `lambda_invoke func {} true`
    # Does it treat "true" as sync arg or project?
    # Logic: if args[-1] in projects -> project.
    
    mock_dependencies["fm"].list_projects.return_value = ["test_proj", "true"]
    
    # Case 1: "true" IS a project.
    # command: lambda_invoke func1 {} true
    # "true" is in projects, so it is treated as project.
    # It matches? No, current is test_proj. Should fail safety check.
    
    run_cli_command('lambda_invoke func1 {} true', mock_dependencies)
    
    mock_dependencies["logger"].error.assert_any_call("SAFETY ERROR: Requested project 'true' does not match active project 'test_proj'.")
    mock_dependencies["lambda"].invoke_function.assert_not_called()
