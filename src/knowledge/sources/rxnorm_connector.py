import logging
import requests
import json
import os
from typing import Dict, Any, List, Optional
from functools import lru_cache

logger = logging.getLogger(__name__)

class RxNormConnector:
    """
    Connects to the NLM (National Library of Medicine) RxNorm API to
    normalize drug names and map them to RxCUI (RxNorm Concept Unique Identifier).
    This allows the system to recognize various brand and generic names for the
    same drug, facilitating consistent understanding.
    """
    def __init__(self, api_base_url: str = "https://rxnav.nlm.nih.gov/REST", cache_size: int = 1000):
        self.api_base_url = api_base_url
        self.session = requests.Session() # Use a session for connection pooling
        self._get_rxcui_by_name_uncached = lru_cache(maxsize=cache_size)(self.__get_rxcui_by_name_uncached)
        self._get_rxcui_properties_uncached = lru_cache(maxsize=cache_size)(self.__get_rxcui_properties_uncached)
        logger.info(f"RxNormConnector initialized with API base URL: {api_base_url}")

    async def get_rxcui_by_name(self, drug_name: str) -> Optional[Dict[str, Any]]:
        """
        Retrieves the RxCUI and associated details for a given drug name
        (brand or generic). Uses caching.

        Args:
            drug_name (str): The name of the drug.

        Returns:
            Optional[Dict[str, Any]]: A dictionary with RxCUI, preferred name, and synonym types, or None.
        """
        if not drug_name:
            return None
        return await self._get_rxcui_by_name_uncached(drug_name.lower())

    async def __get_rxcui_by_name_uncached(self, drug_name: str) -> Optional[Dict[str, Any]]:
        """
        Internal method to retrieve RxCUI by name from RxNorm without caching.
        """
        try:
            url = f"{self.api_base_url}/rxcui.json?name={drug_name}"
            logger.debug(f"Querying RxNorm API for RxCUI by name: {url}")
            response = await asyncio.to_thread(self.session.get, url, timeout=10)
            response.raise_for_status()
            data = response.json()

            if not data or not data.get("idGroup", {}).get("rxnormId"):
                logger.info(f"No RxCUI found for drug name: '{drug_name}'")
                return None
            
            rxcui = data["idGroup"]["rxnormId"][0]
            # Optionally fetch more properties using the RxCUI
            properties = await self.get_rxcui_properties(rxcui)

            logger.info(f"Found RxCUI '{rxcui}' for '{drug_name}'.")
            return {
                "rxcui": rxcui,
                "drug_name_query": drug_name,
                "preferred_name": properties.get("rxcui_name"),
                "synonym_types": properties.get("synonym_types"),
                "properties": properties
            }

        except requests.exceptions.Timeout:
            logger.error(f"RxNorm API request timed out for drug name: '{drug_name}'")
        except requests.exceptions.HTTPError as e:
            logger.error(f"RxNorm API HTTP error for drug name '{drug_name}': {e}")
        except requests.exceptions.RequestException as e:
            logger.error(f"RxNorm API request failed for drug name '{drug_name}': {e}")
        except Exception as e:
            logger.error(f"An unexpected error occurred while querying RxNorm for '{drug_name}': {e}")
        return None

    async def get_rxcui_properties(self, rxcui: str) -> Optional[Dict[str, Any]]:
        """
        Retrieves properties (like preferred name, synonyms, TTY) for a given RxCUI. Uses caching.
        """
        if not rxcui:
            return None
        return await self._get_rxcui_properties_uncached(rxcui)

    async def __get_rxcui_properties_uncached(self, rxcui: str) -> Optional[Dict[str, Any]]:
        """
        Internal method to retrieve RxCUI properties from RxNorm without caching.
        """
        try:
            # Get display properties for the RxCUI
            url_prop = f"{self.api_base_url}/rxcui/{rxcui}/properties.json"
            logger.debug(f"Querying RxNorm API for RxCUI properties: {url_prop}")
            response_prop = await asyncio.to_thread(self.session.get, url_prop, timeout=10)
            response_prop.raise_for_status()
            prop_data = response_prop.json()
            
            properties = {}
            if prop_data and prop_data.get("properties"):
                properties = prop_data["properties"]
            
            # Get all concepts related to the RxCUI
            url_related = f"{self.api_base_url}/rxcui/{rxcui}/allrelated.json?rela=tradename+has_tradename+has_form+has_ingredient"
            logger.debug(f"Querying RxNorm API for related concepts: {url_related}")
            response_related = await asyncio.to_thread(self.session.get, url_related, timeout=10)
            response_related.raise_for_status()
            related_data = response_related.json()

            synonym_types = set()
            if related_data and related_data.get("drugGroup", {}).get("conceptGroup"):
                for group in related_data["drugGroup"]["conceptGroup"]:
                    for concept in group.get("conceptProperties", []):
                        synonym_types.add(concept.get("tty")) # TTY is term type (e.g., SCDF, SBD, BN, GPCK) 
            
            properties["synonym_types"] = list(synonym_types)
            return properties

        except requests.exceptions.Timeout:
            logger.error(f"RxNorm API request timed out for RxCUI: '{rxcui}'")
        except requests.exceptions.HTTPError as e:
            logger.error(f"RxNorm API HTTP error for RxCUI '{rxcui}': {e}")
        except requests.exceptions.RequestException as e:
            logger.error(f"RxNorm API request failed for RxCUI '{rxcui}': {e}")
        except Exception as e:
            logger.error(f"An unexpected error occurred while querying RxNorm for RxCUI '{rxcui}': {e}")
        return None

    async def normalize_drug_name(self, drug_name: str) -> Optional[Dict[str, Any]]:
        """
        Normalizes a drug name to its preferred RxNorm name and RxCUI.
        """
        drug_info = await self.get_rxcui_by_name(drug_name)
        if drug_info and drug_info.get("rxcui"):
            logger.info(f"Normalized '{drug_name}' to RxCUI '{drug_info['rxcui']}' (Preferred: {drug_info.get('preferred_name')}).")
            return {
                "original_name": drug_name,
                "rxcui": drug_info["rxcui"],
                "preferred_name": drug_info.get("preferred_name", drug_name),
                "synonym_types": drug_info.get("synonym_types", [])
            }
        logger.info(f"Could not normalize drug name: '{drug_name}'.")
        return None

# Example Usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    rxnorm_connector = RxNormConnector()

    async def run_rxnorm_tests():
        print("\n--- Test 1: Normalize 'Tylenol' ---")
        tylenol_info = await rxnorm_connector.normalize_drug_name("Tylenol")
        if tylenol_info:
            print(f"Original: {tylenol_info['original_name']}")
            print(f"RxCUI: {tylenol_info['rxcui']}")
            print(f"Preferred Name: {tylenol_info['preferred_name']}")
            print(f"Synonym Types: {tylenol_info['synonym_types']}")
        assert tylenol_info is not None
        assert tylenol_info["preferred_name"].lower() == "acetaminophen"

        print("\n--- Test 2: Normalize 'Paracetamol' ---")
        paracetamol_info = await rxnorm_connector.normalize_drug_name("Paracetamol")
        if paracetamol_info:
            print(f"Original: {paracetamol_info['original_name']}")
            print(f"RxCUI: {paracetamol_info['rxcui']}")
            print(f"Preferred Name: {paracetamol_info['preferred_name']}")
        assert paracetamol_info is not None
        assert paracetamol_info["preferred_name"].lower() == "acetaminophen" # Should map to the same as Tylenol

        print("\n--- Test 3: Normalize 'Amoxicillin' ---")
        amoxicillin_info = await rxnorm_connector.normalize_drug_name("Amoxicillin")
        if amoxicillin_info:
            print(f"Original: {amoxicillin_info['original_name']}")
            print(f"RxCUI: {amoxicillin_info['rxcui']}")
            print(f"Preferred Name: {amoxicillin_info['preferred_name']}")
        assert amoxicillin_info is not None
        assert "amoxicillin" in amoxicillin_info["preferred_name"].lower()

        print("\n--- Test 4: Get Properties for a Known RxCUI (e.g., Acetaminophen's RxCUI) ---")
        # Assuming Acetaminophen's RxCUI is 161
        acetaminophen_rxcui_props = await rxnorm_connector.get_rxcui_properties("161")
        if acetaminophen_rxcui_props:
            print(f"Properties for RxCUI 161 (Acetaminophen): {acetaminophen_rxcui_props.get('rxcui_name')}, TTY: {acetaminophen_rxcui_props.get('tty')}")
            print(f"Synonym Types: {acetaminophen_rxcui_props.get('synonym_types')}")
        assert acetaminophen_rxcui_props is not None
        assert "acetaminophen" in acetaminophen_rxcui_props.get("rxcui_name", "").lower()

        print("\n--- Test 5: Normalize Non-existent Drug ---")
        non_existent_drug = await rxnorm_connector.normalize_drug_name("Fantastium")
        print(f"Info for Fantastium: {non_existent_drug}")
        assert non_existent_drug is None

    import asyncio
    asyncio.run(run_rxnorm_tests())
