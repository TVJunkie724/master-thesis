import sys
import os

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

print("🧪 Testing rest_api import...")
try:
    import rest_api
    print("✅ rest_api imported successfully!")
except Exception as e:
    print(f"❌ Failed to import rest_api: {e}")
    sys.exit(1)
