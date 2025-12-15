import re
import logging
from datetime import datetime
from typing import Optional, Literal, Tuple

logger = logging.getLogger(__name__)

class EnglishLocaleHandler:
    """
    Handles English-specific formatting rules, terminology, and regional variations.
    Supports US (default) and UK/AU English.
    """
    def __init__(self, region: Literal["US", "UK", "AU"] = "US"):
        self.region = region
        logger.info(f"EnglishLocaleHandler initialized for region: {self.region}")

    # --- Date Formatting ---
    def format_date(self, date_obj: datetime, include_time: bool = False) -> str:
        """
        Formats a datetime object according to the region's conventions.
        MM/DD/YYYY for US, DD/MM/YYYY for UK/AU.
        """
        if self.region == "US":
            fmt = "%m/%d/%Y"
        else: # UK, AU
            fmt = "%d/%m/%Y"
        
        if include_time:
            fmt += self._get_time_format_string()
        
        return date_obj.strftime(fmt)

    # --- Time Formatting ---
    def format_time(self, time_obj: datetime) -> str:
        """
        Formats a datetime object's time component according to the region's conventions.
        12-hour with AM/PM for US, 24-hour for UK/AU (often also 12-hour in speech, but 24-hour in formal text).
        """
        return time_obj.strftime(self._get_time_format_string())
    
    def _get_time_format_string(self) -> str:
        if self.region == "US":
            return " %I:%M %p" # 12-hour with AM/PM
        else: # UK, AU (using 24-hour as default for formal, though 12-hour is common conversationally)
            return " %H:%M" # 24-hour
    
    # --- Number Formatting ---
    def format_number(self, number: float, decimal_places: int = 2) -> str:
        """
        Formats a number with appropriate thousands separators.
        Comma for thousands separator in US/UK/AU.
        """
        return f"{number:,.{decimal_places}f}"

    # --- Currency Formatting ---
    def format_currency(self, amount: float) -> str:
        """
        Formats a currency amount with the correct symbol and position.
        """
        if self.region == "US":
            return f"${amount:,.2f}"
        elif self.region == "UK":
            return f"£{amount:,.2f}"
        elif self.region == "AU":
            return f"${amount:,.2f} AUD" # Distinguish from US dollar
        return f"{amount:,.2f}" # Fallback

    # --- Unit Conversions & Terminology ---
    def get_preferred_temperature_unit(self) -> Literal["Fahrenheit", "Celsius"]:
        """Returns the preferred temperature unit for the region."""
        return "Fahrenheit" if self.region == "US" else "Celsius"

    def convert_temperature_to_preferred(self, value: float, unit: Literal["C", "F"]) -> Tuple[float, str]:
        """Converts temperature to the preferred unit of the region."""
        if unit == "C" and self.region == "US":
            return (value * 9/5) + 32, "Fahrenheit"
        elif unit == "F" and self.region != "US":
            return (value - 32) * 5/9, "Celsius"
        return value, self.get_preferred_temperature_unit()

    def get_preferred_weight_unit(self) -> Literal["lbs", "kg"]:
        """Returns the preferred weight unit for the region."""
        return "lbs" if self.region == "US" else "kg"

    def get_preferred_height_unit(self) -> Literal["feet_inches", "cm"]:
        """Returns the preferred height unit for the region."""
        return "feet_inches" if self.region == "US" else "cm"

    def get_terminology(self, generic_term: str) -> str:
        """
        Maps generic medical terms to region-specific terminology.
        """
        term_map = {
            "emergency room": {"US": "ER", "UK": "A&E", "AU": "ED"},
            "physician": {"US": "physician", "UK": "GP", "AU": "GP"},
            "ambulance": {"US": "ambulance", "UK": "ambulance", "AU": "ambulance"},
            "pharmacy": {"US": "pharmacy", "UK": "chemist", "AU": "pharmacy"},
            "vacation": {"US": "vacation", "UK": "holiday", "AU": "holiday"},
        }
        return term_map.get(generic_term.lower(), {}).get(self.region, generic_term)

    # --- Regex Patterns for Validation/Extraction ---
    def get_phone_number_pattern(self) -> Optional[re.Pattern]:
        """Returns a regex pattern for local phone numbers."""
        if self.region == "US":
            # Example: (123) 456-7890 or 123-456-7890
            return re.compile(r"(d{3}) d{3}-d{4}")
        elif self.region == "UK":
            # Example: 020 7946 0000 or +44 20 7946 0000
            return re.compile(r"^((\\+44)|0)\\s?\\d{2}\\s?\\d{4}\\s?\\d{4}$")
        elif self.region == "AU":
            # Example: (02) 1234 5678 or 0400 123 456
            return re.compile(r"^((\\+61)|0)\\d{1}\\s?\\d{4}\\s?\\d{4}$")
        return None

    def get_zip_code_pattern(self) -> Optional[re.Pattern]:
        """Returns a regex pattern for local postal codes."""
        if self.region == "US":
            return re.compile(r"^d{5}(?:[-s]d{4})?$") # 5-digit or 5+4
        elif self.region == "UK":
            # Example: SW1A 0AA, G2 1AD
            return re.compile(r"^[A-Z]{1,2}d[A-Z\d]?\s?\\d[A-Z]{2}$", re.IGNORECASE)
        elif self.region == "AU":
            return re.compile(r"^d{4}$") # 4-digit
        return None

# Example Usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    # US Handler
    us_handler = EnglishLocaleHandler(region="US")
    print("\n--- US English Handler ---")
    print(f"Date (US): {us_handler.format_date(datetime(2025, 12, 11), include_time=True)}")
    print(f"Currency (US): {us_handler.format_currency(1234.56)}")
    print(f"Temperature (US, from C): {us_handler.convert_temperature_to_preferred(25, 'C')}")
    print(f"Terminology (US): {us_handler.get_terminology('emergency room')}")
    us_phone_match = us_handler.get_phone_number_pattern().match("555-123-4567")
    print(f"US Phone '555-123-4567' valid: {bool(us_phone_match)}")
    us_zip_match = us_handler.get_zip_code_pattern().match("90210")
    print(f"US ZIP '90210' valid: {bool(us_zip_match)}")


    # UK Handler
    uk_handler = EnglishLocaleHandler(region="UK")
    print("\n--- UK English Handler ---")
    print(f"Date (UK): {uk_handler.format_date(datetime(2025, 12, 11), include_time=True)}")
    print(f"Currency (UK): {uk_handler.format_currency(1234.56)}")
    print(f"Temperature (UK, from F): {uk_handler.convert_temperature_to_preferred(77, 'F')}")
    print(f"Terminology (UK): {uk_handler.get_terminology('emergency room')}")
    uk_phone_match = uk_handler.get_phone_number_pattern().match("020 7946 0000")
    print(f"UK Phone '020 7946 0000' valid: {bool(uk_phone_match)}")
    uk_postcode_match = uk_handler.get_zip_code_pattern().match("SW1A 0AA")
    print(f"UK Postcode 'SW1A 0AA' valid: {bool(uk_postcode_match)}")

    # AU Handler
    au_handler = EnglishLocaleHandler(region="AU")
    print("\n--- AU English Handler ---")
    print(f"Date (AU): {au_handler.format_date(datetime(2025, 12, 11), include_time=True)}")
    print(f"Currency (AU): {au_handler.format_currency(1234.56)}")
    print(f"Temperature (AU, from F): {au_handler.convert_temperature_to_preferred(77, 'F')}")
    print(f"Terminology (AU): {au_handler.get_terminology('emergency room')}")
    au_phone_match = au_handler.get_phone_number_pattern().match("0400 123 456")
    print(f"AU Phone '0400 123 456' valid: {bool(au_phone_match)}")
    au_postcode_match = au_handler.get_zip_code_pattern().match("2000")
    print(f"AU Postcode '2000' valid: {bool(au_postcode_match)}")
