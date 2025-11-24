import sys
import os

# Add the parent directory to sys.path to allow imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from py.logger import logger
import py.pricing_utils as pricing_utils
import py.constants as CONSTANTS

def verify_currency():
    print("--- Verifying Currency Conversion ---")
    try:
        # Test get_currency_rates
        rates = pricing_utils.get_currency_rates()
        print(f"Rates fetched: {rates}")
        
        if "usd_to_eur_rate" in rates and "eur_to_usd_rate" in rates:
            print("✅ Currency rates structure is correct.")
        else:
            print("❌ Currency rates structure is incorrect!")

        # Test conversion
        amount_usd = 100
        amount_eur = pricing_utils.usd_to_eur(amount_usd)
        print(f"{amount_usd} USD = {amount_eur} EUR (Rate: {rates['usd_to_eur_rate']})")
        
        expected_eur = amount_usd * rates['usd_to_eur_rate']
        if abs(amount_eur - expected_eur) < 0.01:
             print("✅ USD to EUR conversion correct.")
        else:
             print(f"❌ USD to EUR conversion incorrect! Expected {expected_eur}, got {amount_eur}")

        # Check file creation
        if os.path.exists(CONSTANTS.CURRENCY_CONVERSION_FILE_PATH):
            print(f"✅ Currency file exists at {CONSTANTS.CURRENCY_CONVERSION_FILE_PATH}")
        else:
            print(f"❌ Currency file missing at {CONSTANTS.CURRENCY_CONVERSION_FILE_PATH}")

    except Exception as e:
        print(f"❌ Currency verification failed with error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    verify_currency()
