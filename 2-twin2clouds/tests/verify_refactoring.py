import json
import os
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import backend.constants as CONSTANTS
from backend.fetch_data.calculate_up_to_date_pricing import calculate_up_to_date_pricing
from backend.config_loader import load_combined_pricing
# Import fetchers to check for syntax errors and import issues
from backend.fetch_data.cloud_price_fetcher_aws import fetch_aws_price
from backend.fetch_data.cloud_price_fetcher_azure import fetch_azure_price
from backend.fetch_data.cloud_price_fetcher_google import fetch_google_price
# Import rest_api to check for import issues
try:
    import rest_api
    print("✅ rest_api imported successfully.")
except Exception as e:
    print(f"❌ Failed to import rest_api: {e}")
    sys.exit(1)

def test_refactoring():
    print("🧪 Starting Verification...")

    # 1. Mock Fetch Functions to avoid real API calls
    with patch("backend.fetch_data.calculate_up_to_date_pricing.fetch_aws_data") as mock_aws, \
         patch("backend.fetch_data.calculate_up_to_date_pricing.fetch_azure_data") as mock_azure, \
         patch("backend.fetch_data.calculate_up_to_date_pricing.fetch_google_data") as mock_gcp, \
         patch("backend.config_loader.load_credentials_file") as mock_creds, \
         patch("backend.config_loader.load_json_file") as mock_load_json:

        # Setup Mocks
        mock_aws.return_value = {"service": "aws_data"}
        mock_azure.return_value = {"service": "azure_data"}
        mock_gcp.return_value = {"service": "gcp_data"}
        mock_creds.return_value = {"aws": {}, "azure": {}, "gcp": {}}
        mock_load_json.return_value = {} # Mock region map loading

        # 2. Test Partial Fetch (AWS)
        print("   Testing AWS Fetch...")
        calculate_up_to_date_pricing("aws")
        
        if not CONSTANTS.AWS_PRICING_FILE_PATH.exists():
            print("❌ AWS pricing file not created!")
            return
        
        aws_content = json.loads(CONSTANTS.AWS_PRICING_FILE_PATH.read_text())
        if aws_content.get("service") != "aws_data":
            print(f"❌ AWS content incorrect: {aws_content}")
            return
        print("   ✅ AWS Fetch & Write successful.")

        # 3. Test Partial Fetch (Azure)
        print("   Testing Azure Fetch...")
        calculate_up_to_date_pricing("azure")
        if not CONSTANTS.AZURE_PRICING_FILE_PATH.exists():
            print("❌ Azure pricing file not created!")
            return
        print("   ✅ Azure Fetch & Write successful.")

    # 4. Test Combined Loading (Outside of mocks so it reads real files)
    print("   Testing Combined Loading...")
    # We need to ensure the files created above are readable by load_combined_pricing
    # load_combined_pricing uses load_json_file, which we want to be REAL now.
    
    combined = load_combined_pricing()
    
    if combined.get("aws", {}).get("service") != "aws_data":
            print(f"❌ Combined loading failed for AWS. Got: {combined.get('aws')}")
            return
    if combined.get("azure", {}).get("service") != "azure_data":
            print(f"❌ Combined loading failed for Azure. Got: {combined.get('azure')}")
            return
    
    print("   ✅ Combined Loading successful.")
        
    print("🎉 Verification Complete: All checks passed!")

if __name__ == "__main__":
    # Ensure directory exists
    CONSTANTS.BASE_FETCHED_DATA_PATH.mkdir(parents=True, exist_ok=True)
    test_refactoring()
