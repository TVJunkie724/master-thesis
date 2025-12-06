import pytest
from unittest.mock import MagicMock, patch
import globals
import deployers.core_deployer as core_deployer
import aws.core_deployer_aws as core_aws

@pytest.fixture
def mock_core_aws():
    """Mock all core_aws functions to prevent actual AWS calls."""
    with patch("deployers.core_deployer.core_aws") as mock_aws:
        yield mock_aws

def test_deploy_l2_full_features(mock_core_aws):
    """Verify all L2 features deployed when flags are True."""
    # Setup Config
    globals.config_optimization = {
        "result": {
            "inputParamsUsed": {
                "useEventChecking": True,
                "triggerNotificationWorkflow": True,
                "returnFeedbackToDevice": True
            }
        }
    }
    
    # Execute
    core_deployer.deploy_l2("aws")
    
    # Verify
    assert mock_core_aws.create_persister_lambda_function.called
    assert mock_core_aws.create_event_checker_lambda_function.called
    assert mock_core_aws.create_lambda_chain_step_function.called
    assert mock_core_aws.create_event_feedback_lambda_function.called

def test_deploy_l2_minimal_features(mock_core_aws):
    """Verify ONLY Persister deployed when Event Checking is False."""
    # Setup Config
    globals.config_optimization = {
        "result": {
            "inputParamsUsed": {
                "useEventChecking": False,
                # These should be ignored because useEventChecking is False
                "triggerNotificationWorkflow": True, 
                "returnFeedbackToDevice": True
            }
        }
    }
    
    # Execute
    core_deployer.deploy_l2("aws")
    
    # Verify
    assert mock_core_aws.create_persister_lambda_function.called
    assert not mock_core_aws.create_event_checker_lambda_function.called
    assert not mock_core_aws.create_lambda_chain_step_function.called
    assert not mock_core_aws.create_event_feedback_lambda_function.called

def test_deploy_l3_api_gateway_needed(mock_core_aws):
    """Verify API Gateway deployed when providers mismatch."""
    # Setup Config: L3 Hot (AWS) != L5 (GCP)
    globals.config_providers = {
        "layer_3_hot_provider": "aws",
        "layer_4_provider": "aws",
        "layer_5_provider": "google"
    }
    
    # Execute
    core_deployer.deploy_l3_hot("aws")
    
    # Verify
    assert mock_core_aws.create_hot_dynamodb_table.called
    assert mock_core_aws.create_api.called
    assert mock_core_aws.create_api_hot_reader_integration.called

def test_deploy_l3_api_gateway_not_needed(mock_core_aws):
    """Verify API Gateway NOT deployed when providers match."""
    # Setup Config: L3 Hot (AWS) == L4 (AWS) == L5 (AWS)
    globals.config_providers = {
        "layer_3_hot_provider": "aws",
        "layer_4_provider": "aws",
        "layer_5_provider": "aws"
    }
    
    # Execute
    core_deployer.deploy_l3_hot("aws")
    
    # Verify
    assert mock_core_aws.create_hot_dynamodb_table.called
    assert not mock_core_aws.create_api.called
    assert not mock_core_aws.create_api_hot_reader_integration.called

def test_deploy_l3_wrong_provider(mock_core_aws):
    """Verify API Gateway logic skipped if not deploying L3 Hot provider."""
    # Setup Config: L3 Hot is GCP. We are deploying AWS.
    globals.config_providers = {
        "layer_3_hot_provider": "google",
        "layer_4_provider": "aws",
        "layer_5_provider": "aws"
    }
    
    # Execute
    core_deployer.deploy_l3_hot("aws") 
    # NOTE: deploy_l3_hot for AWS creates AWS resources. 
    # But if L3 Hot is set to Google, conceptually we shouldn't be deploying L3 Hot on AWS?
    # However, create_api logic checks `should_deploy_api_gateway("aws")`.
    # logic: if current("aws") != l3_hot("google") -> False.
    
    # Verify
    assert not mock_core_aws.create_api.called
