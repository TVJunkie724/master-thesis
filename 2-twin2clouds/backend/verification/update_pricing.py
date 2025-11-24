
import sys
import os

# Add the project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from py.calculate_up_to_date_pricing import calculate_up_to_date_pricing

if __name__ == "__main__":
    print("Updating pricing...")
    try:
        calculate_up_to_date_pricing()
        print("Pricing updated successfully!")
    except Exception as e:
        print(f"Pricing update failed: {e}")
        import traceback
        traceback.print_exc()
