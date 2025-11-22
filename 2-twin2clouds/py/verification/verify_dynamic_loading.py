
import sys
import os

# Add the parent directory to sys.path to allow imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    print("--- Verifying AWS Region Loading ---")
    from py.cloud_price_fetcher_aws import AWS_REGION_NAMES
    print(f"AWS_REGION_NAMES type: {type(AWS_REGION_NAMES)}")
    print(f"AWS_REGION_NAMES count: {len(AWS_REGION_NAMES)}")
    if len(AWS_REGION_NAMES) > 0:
        print("✅ AWS regions loaded successfully.")
    else:
        print("❌ AWS regions dict is empty!")

    print("\n--- Verifying Azure Region Loading ---")
    from py.cloud_price_fetcher_azure import AZURE_REGION_NAMES
    print(f"AZURE_REGION_NAMES type: {type(AZURE_REGION_NAMES)}")
    print(f"AZURE_REGION_NAMES count: {len(AZURE_REGION_NAMES)}")
    if len(AZURE_REGION_NAMES) > 0:
        print("✅ Azure regions loaded successfully.")
    else:
        print("❌ Azure regions dict is empty!")

    print("\n--- Verifying GCP Region Loading ---")
    from py.cloud_price_fetcher_google import GCP_REGION_NAMES
    print(f"GCP_REGION_NAMES type: {type(GCP_REGION_NAMES)}")
    print(f"GCP_REGION_NAMES count: {len(GCP_REGION_NAMES)}")
    if len(GCP_REGION_NAMES) > 0:
        print("✅ GCP regions loaded successfully.")
    else:
        print("❌ GCP regions dict is empty!")

except Exception as e:
    print(f"❌ Verification failed with error: {e}")
    import traceback
    traceback.print_exc()
