"""
Unit tests for build_all_packages function.

Verifies that build_all_packages calls all required builder functions,
including build_user_packages (which was previously missing).
"""
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock


class TestBuildAllPackages:
    """Tests for the build_all_packages orchestration function."""
    
    @pytest.fixture
    def mock_providers_all_gcp(self):
        """Provider config with all layers on GCP."""
        return {
            "layer_1_provider": "google",
            "layer_2_provider": "google",
            "layer_3_hot_provider": "google",
            "layer_3_cold_provider": "google",
            "layer_3_archive_provider": "google",
        }
    
    @pytest.fixture
    def mock_providers_all_aws(self):
        """Provider config with all layers on AWS."""
        return {
            "layer_1_provider": "aws",
            "layer_2_provider": "aws",
            "layer_3_hot_provider": "aws",
            "layer_3_cold_provider": "aws",
            "layer_3_archive_provider": "aws",
        }
    
    def test_calls_all_builder_functions(self, tmp_path, mock_providers_all_gcp):
        """Verify build_all_packages calls all expected builder functions."""
        from src.providers.terraform.package_builder import build_all_packages
        
        terraform_dir = tmp_path / "terraform"
        terraform_dir.mkdir()
        project_path = tmp_path / "project"
        project_path.mkdir()
        
        with patch('src.providers.terraform.package_builder.build_aws_lambda_packages') as mock_aws, \
             patch('src.providers.terraform.package_builder.build_azure_function_packages') as mock_azure, \
             patch('src.providers.terraform.package_builder.build_gcp_cloud_function_packages') as mock_gcp, \
             patch('src.providers.terraform.package_builder.build_user_packages') as mock_user:
            
            # Configure mocks to return empty dicts
            mock_aws.return_value = {"aws_pkg": Path("/tmp/aws.zip")}
            mock_azure.return_value = {"azure_pkg": Path("/tmp/azure.zip")}
            mock_gcp.return_value = {"gcp_pkg": Path("/tmp/gcp.zip")}
            mock_user.return_value = {"user_pkg": Path("/tmp/user.zip")}
            
            result = build_all_packages(terraform_dir, project_path, mock_providers_all_gcp)
            
            # Assert all builder functions were called
            mock_aws.assert_called_once()
            mock_azure.assert_called_once()
            mock_gcp.assert_called_once()
            mock_user.assert_called_once()
            
            # Verify build_user_packages was called with correct args
            mock_user.assert_called_with(project_path, mock_providers_all_gcp)
    
    def test_merges_all_package_results(self, tmp_path, mock_providers_all_gcp):
        """Verify build_all_packages merges results from all builders."""
        from src.providers.terraform.package_builder import build_all_packages
        
        terraform_dir = tmp_path / "terraform"
        terraform_dir.mkdir()
        project_path = tmp_path / "project"
        project_path.mkdir()
        
        with patch('src.providers.terraform.package_builder.build_aws_lambda_packages') as mock_aws, \
             patch('src.providers.terraform.package_builder.build_azure_function_packages') as mock_azure, \
             patch('src.providers.terraform.package_builder.build_gcp_cloud_function_packages') as mock_gcp, \
             patch('src.providers.terraform.package_builder.build_user_packages') as mock_user:
            
            mock_aws.return_value = {"aws_dispatcher": Path("/tmp/aws_dispatcher.zip")}
            mock_azure.return_value = {"azure_l0": Path("/tmp/azure_l0.zip")}
            mock_gcp.return_value = {"gcp_persister": Path("/tmp/gcp_persister.zip")}
            mock_user.return_value = {"processor-sensor1": Path("/tmp/processor-sensor1.zip")}
            
            result = build_all_packages(terraform_dir, project_path, mock_providers_all_gcp)
            
            # Verify all packages are in the result
            assert "aws_dispatcher" in result
            assert "azure_l0" in result
            assert "gcp_persister" in result
            assert "processor-sensor1" in result
            assert len(result) == 4
    
    def test_user_packages_called_for_gcp_l2(self, tmp_path, mock_providers_all_gcp):
        """Verify build_user_packages is called when L2 is GCP (per-device processors)."""
        from src.providers.terraform.package_builder import build_all_packages
        
        terraform_dir = tmp_path / "terraform"
        terraform_dir.mkdir()
        project_path = tmp_path / "project"
        project_path.mkdir()
        
        with patch('src.providers.terraform.package_builder.build_aws_lambda_packages', return_value={}), \
             patch('src.providers.terraform.package_builder.build_azure_function_packages', return_value={}), \
             patch('src.providers.terraform.package_builder.build_gcp_cloud_function_packages', return_value={}), \
             patch('src.providers.terraform.package_builder.build_user_packages') as mock_user:
            
            mock_user.return_value = {
                "processor-temperature-sensor-1": Path("/tmp/proc1.zip"),
                "processor-pressure-sensor-1": Path("/tmp/proc2.zip"),
            }
            
            result = build_all_packages(terraform_dir, project_path, mock_providers_all_gcp)
            
            # build_user_packages should be called regardless of provider
            mock_user.assert_called_once()
            
            # User packages should be in result
            assert "processor-temperature-sensor-1" in result
            assert "processor-pressure-sensor-1" in result
    
    def test_user_packages_called_for_aws_l2(self, tmp_path, mock_providers_all_aws):
        """Verify build_user_packages is also called when L2 is AWS."""
        from src.providers.terraform.package_builder import build_all_packages
        
        terraform_dir = tmp_path / "terraform"
        terraform_dir.mkdir()
        project_path = tmp_path / "project"
        project_path.mkdir()
        
        with patch('src.providers.terraform.package_builder.build_aws_lambda_packages', return_value={}), \
             patch('src.providers.terraform.package_builder.build_azure_function_packages', return_value={}), \
             patch('src.providers.terraform.package_builder.build_gcp_cloud_function_packages', return_value={}), \
             patch('src.providers.terraform.package_builder.build_user_packages') as mock_user:
            
            mock_user.return_value = {}
            
            build_all_packages(terraform_dir, project_path, mock_providers_all_aws)
            
            # build_user_packages should always be called
            mock_user.assert_called_once()
