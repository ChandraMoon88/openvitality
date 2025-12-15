# src/intelligence/pii_scrubber.py

import re
from typing import List, Dict, Any

class PIIScrubber:
    """
    Detects and redacts Personal Identifiable Information (PII) from text.
    
    This class centralizes PII patterns and provides methods for scrubbing
    text to ensure privacy and compliance.
    """
    def __init__(self, pii_patterns: Dict[str, str] = None):
        """
        Initializes the PIIScrubber.
        
        :param pii_patterns: A dictionary where keys are PII types (e.g., 'email', 'phone')
                             and values are their corresponding regex patterns.
        """
        # Default PII patterns. In a real system, these would be loaded from
        # a configuration file (e.g., logging_config.yaml or a dedicated PII config).
        self.pii_patterns = pii_patterns or {
            "email": r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
            "phone_us": r"\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}",
            "ssn_us": r"\b\d{3}-\d{2}-\d{4}\b",
            "date_of_birth": r"\b(0?[1-9]|1[0-2])/(0?[1-9]|[12]\d|3[01])/(19|20)\d{2}\b", # MM/DD/YYYY
            "address": r"\b\d+\s+([A-Za-z]+\s*){1,2}(Street|St|Road|Rd|Avenue|Ave|Boulevard|Blvd|Lane|Ln|Drive|Dr|Court|Ct|Place|Pl|Square|Sq|Terrace|Ter)\b",
            "name": r"\b[A-Z][a-z]+\s+[A-Z][a-z]+\b", # Simple First Last Name
            # More complex patterns can be added, potentially using external libraries like Presidio
        }
        self.default_redaction_strategy = "replace" # Can be 'replace', 'hash', 'remove'
        print("✅ PIIScrubber initialized.")

    def detect_pii(self, text: str) -> Dict[str, List[str]]:
        """
        Detects PII in the given text and returns a dictionary of detected PII.
        
        :param text: The input string to scan for PII.
        :return: A dictionary where keys are PII types and values are lists of
                 the detected PII strings for that type.
        """
        detected = {}
        for pii_type, pattern in self.pii_patterns.items():
            matches = re.findall(pattern, text)
            if matches:
                detected[pii_type] = list(set(matches)) # Use set to get unique matches
        return detected

    def scrub_text(self, text: str, pii_types_to_scrub: List[str] = None, strategy: str = None) -> str:
        """
        Redacts PII from the given text based on specified PII types and strategy.
        
        :param text: The input string from which to scrub PII.
        :param pii_types_to_scrub: A list of PII types to scrub. If None, all configured types are scrubbed.
        :param strategy: The redaction strategy ('replace', 'hash', 'remove').
                         Defaults to `self.default_redaction_strategy`.
        :return: The text with detected PII scrubbed.
        """
        if strategy is None:
            strategy = self.default_redaction_strategy

        scrubbed_text = text
        types_to_process = pii_types_to_scrub if pii_types_to_scrub is not None else self.pii_patterns.keys()

        for pii_type in types_to_process:
            pattern = self.pii_patterns.get(pii_type)
            if pattern:
                matches = re.finditer(pattern, scrubbed_text)
                # Iterate over matches and replace them based on strategy
                # Need to be careful with iterative replacements to avoid messing up indices.
                # It's safer to build a new string or replace from right to left.
                # For simplicity here, we'll re-apply regex for each type.
                
                if strategy == "replace":
                    scrubbed_text = re.sub(pattern, f"[REDACTED_{pii_type.upper()}]", scrubbed_text)
                elif strategy == "remove":
                    scrubbed_text = re.sub(pattern, "", scrubbed_text)
                elif strategy == "hash":
                    # Hashing PII is more complex as it depends on context (e.g., consistent hashing)
                    # For a simple regex match, just replace with a generic hash placeholder.
                    scrubbed_text = re.sub(pattern, f"[HASHED_{pii_type.upper()}]", scrubbed_text)
                else:
                    print(f"⚠️ Warning: Unknown redaction strategy '{strategy}'. No scrubbing performed for {pii_type}.")

        return scrubbed_text

# Example Usage
if __name__ == "__main__":
    scrubber = PIIScrubber()

    # --- Test 1: Detect PII ---
    text_with_pii = "My name is John Doe, and my email is john.doe@example.com. You can reach me at (123) 456-7890. My SSN is 111-22-3333. I live at 123 Main Street. My DOB is 01/01/1990."
    print("\n--- Test 1: Detect PII ---")
    detected_pii = scrubber.detect_pii(text_with_pii)
    for pii_type, values in detected_pii.items():
        print(f"Detected {pii_type}: {', '.join(values)}")

    # --- Test 2: Scrub all PII (default strategy: replace) ---
    print("\n--- Test 2: Scrub all PII (default strategy) ---")
    scrubbed_all = scrubber.scrub_text(text_with_pii)
    print(f"Original: {text_with_pii}")
    print(f"Scrubbed: {scrubbed_all}")

    # --- Test 3: Scrub specific PII types ---
    print("\n--- Test 3: Scrub specific PII types (email, phone) ---")
    scrubbed_specific = scrubber.scrub_text(text_with_pii, pii_types_to_scrub=["email", "phone_us"])
    print(f"Original: {text_with_pii}")
    print(f"Scrubbed: {scrubbed_specific}")

    # --- Test 4: Scrub using 'remove' strategy ---
    print("\n--- Test 4: Scrub using 'remove' strategy ---")
    scrubbed_removed = scrubber.scrub_text(text_with_pii, strategy="remove")
    print(f"Original: {text_with_pii}")
    print(f"Scrubbed: {scrubbed_removed}")

    # --- Test 5: Scrub using 'hash' strategy ---
    print("\n--- Test 5: Scrub using 'hash' strategy ---")
    scrubbed_hashed = scrubber.scrub_text(text_with_pii, strategy="hash")
    print(f"Original: {text_with_pii}")
    print(f"Scrubbed: {scrubbed_hashed}")
