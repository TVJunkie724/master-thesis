import pytest
import os
from unittest.mock import patch, MagicMock
import util

class TestUtil:
    def test_contains_provider(self):
        """Verify contains_provider correctly identifies provider presence."""
        providers = {"default": "aws", "secondary": "azure"}
        assert util.contains_provider(providers, "aws") is True
        assert util.contains_provider(providers, "azure") is True
        assert util.contains_provider(providers, "google") is False

    def test_validate_credentials_success(self):
        """Verify validate_credentials passes with correct fields."""
        creds = {
            "aws": {
                "aws_access_key_id": "test",
                "aws_secret_access_key": "test",
                "aws_region": "test"
            }
        }
        result = util.validate_credentials("aws", creds)
        assert result == creds["aws"]

    def test_validate_credentials_missing_provider(self):
        """Verify validate_credentials raises ValueError if provider missing."""
        with pytest.raises(ValueError, match="AWS credentials are required"):
            util.validate_credentials("aws", {})

    def test_validate_credentials_missing_fields(self):
        """Verify validate_credentials raises ValueError if fields missing."""
        creds = {"aws": {"aws_access_key_id": "test"}}
        with pytest.raises(ValueError, match="missing fields"):
            util.validate_credentials("aws", creds)

    @patch("os.path.exists")
    @patch("globals.project_path")
    def test_resolve_folder_path_relative(self, mock_project_path, mock_exists):
        """Verify resolve_folder_path resolves relative paths correctly."""
        mock_project_path.return_value = "/app"
        mock_exists.side_effect = [True]  # Relative path exists
        
        path = util.resolve_folder_path("src")
        assert path == "/app/src"

    @patch("os.path.exists")
    @patch("globals.project_path")
    def test_resolve_folder_path_absolute(self, mock_project_path, mock_exists):
        """Verify resolve_folder_path resolves absolute paths correctly."""
        mock_project_path.return_value = "/app"
        mock_exists.side_effect = [False, True]  # Relative fails, Absolute exists
        
        path = util.resolve_folder_path("/tmp/test")
        assert path == os.path.abspath("/tmp/test")

    @patch("os.path.exists")
    def test_resolve_folder_path_not_found(self, mock_exists):
        """Verify resolve_folder_path resolves raises FileNotFoundError."""
        mock_exists.return_value = False
        with pytest.raises(FileNotFoundError):
            util.resolve_folder_path("nonexistent")

    @patch("util.resolve_folder_path")
    @patch("zipfile.ZipFile")
    @patch("os.walk")
    def test_zip_directory(self, mock_walk, mock_zipfile, mock_resolve):
        """Verify zip_directory creates a zip archive."""
        mock_resolve.return_value = "/app/src"
        mock_walk.return_value = [("/app/src", [], ["file.txt"])]
        
        zip_path = util.zip_directory("src")
        
        assert zip_path == "/app/src/zipped.zip"
        mock_zipfile.assert_called()
