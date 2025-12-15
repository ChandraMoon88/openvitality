import logging
import os
import csv
from typing import Dict, Any, List, Optional
from functools import lru_cache

logger = logging.getLogger(__name__)

class ICD10CodeDatabase:
    """
    Manages access to ICD-10-CM (International Classification of Diseases,
    10th Revision, Clinical Modification) billing codes. It provides a
    conceptual interface for mapping common disease names to their
    corresponding ICD-10 codes, essential for billing and insurance claims.
    """
    def __init__(self, data_file_path: Optional[str] = None):
        # Data file path (conceptual, in a real scenario this would be a large CSV/database)
        self.data_file_path = data_file_path if data_file_path else "data/icd10_codes.csv"
        self._load_codes_from_file()
        self._map_common_names_to_codes()
        self._get_code_info_uncached = lru_cache(maxsize=1000)(self.__get_code_info_uncached)
        logger.info("ICD10CodeDatabase initialized.")

    def _load_codes_from_file(self):
        """
        (Conceptual) Loads ICD-10 codes from a specified text file.
        In a real scenario, this would parse a large official CMS CSV/TXT file.
        """
        self.icd10_codes: Dict[str, Dict[str, str]] = {} # code -> {description, common_names_regex}
        self.common_name_to_code: Dict[str, str] = {} # common_name_lowercase -> code

        # Mock data for demonstration
        mock_codes = [
            {"code": "I21.9", "description": "Acute myocardial infarction, unspecified", "common_names": "Heart attack, MI"},
            {"code": "J11.1", "description": "Influenza with other respiratory manifestations, influenza virus not identified", "common_names": "Flu, Influenza"},
            {"code": "R51", "description": "Headache", "common_names": "Headache, Head ache"},
            {"code": "E11.9", "description": "Type 2 diabetes mellitus without complications", "common_names": "Diabetes, Type 2 Diabetes"},
            {"code": "G43.909", "description": "Migraine, unspecified, not intractable, without status migrainosus", "common_names": "Migraine"}
        ]

        for entry in mock_codes:
            code = entry["code"]
            self.icd10_codes[code] = {"description": entry["description"], "common_names_regex": entry["common_names"]}
            
            # Populate reverse mapping for common names
            if entry["common_names"]:
                for name in entry["common_names"].split(','):
                    self.common_name_to_code[name.strip().lower()] = code
        
        # If a file existed, this would override or supplement mock data
        if os.path.exists(self.data_file_path):
            logger.info(f"Loading ICD-10 codes from {self.data_file_path} (conceptual).")
            # Example parsing of a simple CSV: Code,Description,CommonNames
            with open(self.data_file_path, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                next(reader, None) # Skip header
                for row in reader:
                    if len(row) >= 3:
                        code, description, common_names = row[0], row[1], row[2]
                        self.icd10_codes[code] = {"description": description, "common_names_regex": common_names}
                        for name in common_names.split(','):
                            self.common_name_to_code[name.strip().lower()] = code
        logger.info(f"Loaded {len(self.icd10_codes)} ICD-10 codes.")

    def _map_common_names_to_codes(self):
        """
        Builds a reverse mapping from common disease names to ICD-10 codes.
        This is typically based on pre-defined lists or using NLP techniques.
        """
        # This is already done during _load_codes_from_file for the mock.
        # For a more advanced system, this could involve training an NLP model
        # or leveraging a robust medical terminology service to map synonyms.
        pass

    async def get_code_info(self, icd10_code: str) -> Optional[Dict[str, str]]:
        """
        Retrieves information for a specific ICD-10 code. Uses caching.
        """
        return self._get_code_info_uncached(icd10_code.upper())

    def __get_code_info_uncached(self, icd10_code: str) -> Optional[Dict[str, str]]:
        """
        Internal method for retrieving ICD-10 code information without caching.
        """
        info = self.icd10_codes.get(icd10_code)
        if info:
            logger.debug(f"Retrieved info for ICD-10 code '{icd10_code}'.")
            return info
        logger.info(f"ICD-10 code '{icd10_code}' not found.")
        return None

    async def get_code_from_common_name(self, common_name: str) -> Optional[Dict[str, str]]:
        """
        Maps a common disease name to its corresponding ICD-10 code and description.

        Args:
            common_name (str): The common name of the disease (e.g., "heart attack").

        Returns:
            Optional[Dict[str, str]]: A dictionary with 'code' and 'description', or None.
        """
        common_name_lower = common_name.lower()
        code = self.common_name_to_code.get(common_name_lower)
        if code:
            info = await self.get_code_info(code)
            if info:
                logger.info(f"Mapped '{common_name}' to ICD-10 code '{code}'.")
                return {"code": code, "description": info["description"]}
        
        # Fallback to fuzzy matching or more advanced NLP if exact match fails
        logger.info(f"No direct ICD-10 code mapping found for common name: '{common_name}'.")
        return None

    async def explain_code(self, icd10_code: str) -> str:
        """
        Provides a plain English explanation of an ICD-10 code.
        """
        info = await self.get_code_info(icd10_code)
        if info:
            return f"The ICD-10 code {icd10_code} refers to: '{info['description']}'. This code is used by medical professionals for billing and statistical purposes to categorize diagnoses."
        return f"I could not find information for the ICD-10 code '{icd10_code}'. It may be invalid or not in my database."

# Example Usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    # Create a dummy CSV file for testing
    dummy_csv_path = "data/icd10_codes.csv"
    os.makedirs(os.path.dirname(dummy_csv_path), exist_ok=True)
    with open(dummy_csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(["Code", "Description", "CommonNames"])
        writer.writerow(["I10", "Essential (primary) hypertension", "High blood pressure, Hypertension"])
        writer.writerow(["J45.909", "Unspecified asthma, uncomplicated, without status asthmaticus", "Asthma"])
    logger.info(f"Dummy ICD-10 CSV '{dummy_csv_path}' created.")


    icd10_db = ICD10CodeDatabase(data_file_path=dummy_csv_path)

    async def run_icd10_tests():
        print("\n--- Test 1: Get info for 'I21.9' (Heart Attack) ---")
        heart_attack_info = await icd10_db.get_code_info("I21.9")
        if heart_attack_info:
            print(f"Code: I21.9, Description: {heart_attack_info.get('description')}")
        assert heart_attack_info is not None
        assert "myocardial infarction" in heart_attack_info.get("description").lower()

        print("\n--- Test 2: Map 'Flu' to code ---")
        flu_code_info = await icd10_db.get_code_from_common_name("Flu")
        if flu_code_info:
            print(f"Common Name 'Flu' -> Code: {flu_code_info.get('code')}, Description: {flu_code_info.get('description')}")
        assert flu_code_info is not None
        assert flu_code_info.get("code") == "J11.1"

        print("\n--- Test 3: Explain code 'E11.9' (Type 2 Diabetes) ---")
        diabetes_explanation = await icd10_db.explain_code("E11.9")
        print(f"Explanation for E11.9: {diabetes_explanation}")
        assert "Type 2 diabetes mellitus" in diabetes_explanation

        print("\n--- Test 4: Get info for 'I10' (from CSV) ---")
        hypertension_info = await icd10_db.get_code_info("I10")
        if hypertension_info:
            print(f"Code: I10, Description: {hypertension_info.get('description')}")
        assert hypertension_info is not None
        assert "hypertension" in hypertension_info.get("description").lower()

        print("\n--- Test 5: Map 'High blood pressure' to code (from CSV) ---")
        hbp_code_info = await icd10_db.get_code_from_common_name("High blood pressure")
        if hbp_code_info:
            print(f"Common Name 'High blood pressure' -> Code: {hbp_code_info.get('code')}, Description: {hbp_code_info.get('description')}")
        assert hbp_code_info is not None
        assert hbp_code_info.get("code") == "I10"

        print("\n--- Test 6: Non-existent Common Name ---")
        non_existent_code = await icd10_db.get_code_from_common_name("Zombie Apocalypse")
        print(f"Code for 'Zombie Apocalypse': {non_existent_code}")
        assert non_existent_code is None

    import asyncio
    asyncio.run(run_icd10_tests())

    # Clean up dummy CSV
    if os.path.exists(dummy_csv_path):
        os.remove(dummy_csv_path)
        logger.info(f"Cleaned up dummy ICD-10 CSV: {dummy_csv_path}")
