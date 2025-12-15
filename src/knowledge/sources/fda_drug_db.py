import logging
import requests
import json
import os
from typing import Dict, Any, List, Optional
from functools import lru_cache

logger = logging.getLogger(__name__)

class FDADrugDatabase:
    """
    Interacts with the openFDA API to retrieve US drug safety data.
    Provides information on brand names, generic names, black box warnings,
    recalls, and side effects. Includes local caching for efficiency.
    """
    def __init__(self, api_base_url: str = "https://api.fda.gov", cache_size: int = 500):
        self.api_base_url = api_base_url
        self.session = requests.Session() # Use a session for connection pooling
        self._get_drug_info_uncached = lru_cache(maxsize=cache_size)(self.__get_drug_info_uncached)
        logger.info(f"FDADrugDatabase initialized with API base URL: {api_base_url}")

    async def get_drug_info(self, query: str, limit: int = 1) -> Optional[Dict[str, Any]]:
        """
        Retrieves drug information (brand/generic name, warnings, recalls, side effects)
        for a given query (drug name). Uses caching.

        Args:
            query (str): The drug name (brand or generic) to search for.
            limit (int): Maximum number of results to return.

        Returns:
            Optional[Dict[str, Any]]: A dictionary containing comprehensive drug information
                                       or None if not found/error.
        """
        if not query:
            return None
        # Cache key includes query and limit
        return self._get_drug_info_uncached(query.lower(), limit)

    def __get_drug_info_uncached(self, query: str, limit: int = 1) -> Optional[Dict[str, Any]]:
        """
        Internal method to retrieve drug information from openFDA without caching.
        """
        try:
            # Search drug labels for brand name or generic name
            # For comprehensive search, one might combine multiple endpoints or refine queries.
            # E.g., for drug events, /drug/event.json; for drug labels, /drug/label.json
            search_query = f'openfda.brand_name:"{query}"+OR+openfda.generic_name:"{query}"'
            url = f"{self.api_base_url}/drug/label.json?search={search_query}&limit={limit}" 
            
            logger.debug(f"Querying openFDA API: {url}")
            response = self.session.get(url, timeout=10)
            response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
            data = response.json()

            if not data or not data.get("results"):
                logger.info(f"No drug information found for query: '{query}'")
                return None

            # For simplicity, take the first result and extract key information
            first_result = data["results"][0]
            openfda_data = first_result.get("openfda", {})

            drug_info = {
                "query": query,
                "brand_name": openfda_data.get("brand_name", []),
                "generic_name": openfda_data.get("generic_name", []),
                "substance_name": openfda_data.get("substance_name", []),
                "pharmacologic_class": openfda_data.get("pharmacologic_class", []),
                "indications_and_usage": first_result.get("indications_and_usage", []),
                "warnings": first_result.get("warnings", []),
                "black_box_warning": first_result.get("black_box_warning", []),
                "adverse_reactions": first_result.get("adverse_reactions", []),
                "contraindications": first_result.get("contraindications", []),
                "drug_interactions": first_result.get("drug_interactions", []),
                "effective_time": first_result.get("effective_time"),
                "source_url": f"https://www.accessdata.fda.gov/drugsatFDA_docs/label/{openfda_data.get('spl_id', [''])[0]}.pdf" if openfda_data.get('spl_id') else None
            }
            logger.info(f"Retrieved drug info for '{query}' from openFDA.")
            return drug_info

        except requests.exceptions.Timeout:
            logger.error(f"openFDA API request timed out for query: '{query}'")
        except requests.exceptions.HTTPError as e:
            logger.error(f"openFDA API HTTP error for query '{query}': {e}")
        except requests.exceptions.RequestException as e:
            logger.error(f"openFDA API request failed for query '{query}': {e}")
        except Exception as e:
            logger.error(f"An unexpected error occurred while querying openFDA for '{query}': {e}")
        return None

    async def check_for_recalls(self, drug_name: str) -> List[Dict[str, Any]]:
        """
        Checks openFDA's enforcement reports for recalls related to a drug.

        Args:
            drug_name (str): The name of the drug to check for recalls.

        Returns:
            List[Dict[str, Any]]: A list of dictionaries, each representing a recall event.
        """
        try:
            # Search for drug recalls
            # More complex logic might be needed to map drug_name to exact terms in recall data
            search_query = f'product_description:"{drug_name}"+OR+reason_for_recall:"{drug_name}"'
            url = f"{self.api_base_url}/food/enforcement.json?search={search_query}&limit=5" # Using food enforcement as a general example, drug enforcement is specific
            
            # For actual drug recalls: /drug/enforcement.json
            url = f"{self.api_base_url}/drug/enforcement.json?search={search_query}&limit=5"

            logger.debug(f"Querying openFDA for recalls: {url}")
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()

            if not data or not data.get("results"):
                logger.info(f"No recalls found for '{drug_name}'.")
                return []
            
            recalls = []
            for result in data["results"]:
                recalls.append({
                    "recall_number": result.get("recall_number"),
                    "product_description": result.get("product_description"),
                    "reason_for_recall": result.get("reason_for_recall"),
                    "classification": result.get("classification"), # Class I (dangerous) to Class III (least serious)
                    "report_date": result.get("report_date")
                })
            logger.info(f"Found {len(recalls)} recall(s) for '{drug_name}'.")
            return recalls

        except requests.exceptions.RequestException as e:
            logger.error(f"openFDA API request failed for recalls '{drug_name}': {e}")
        except Exception as e:
            logger.error(f"An unexpected error occurred while checking recalls for '{drug_name}': {e}")
        return []

    async def get_side_effects(self, drug_name: str, limit: int = 5) -> List[str]:
        """
        Retrieves common adverse reactions (side effects) for a given drug.
        """
        drug_info = await self.get_drug_info(drug_name, limit=1)
        if drug_info and drug_info.get("adverse_reactions"):
            # Adverse reactions from drug label are usually text blobs.
            # More sophisticated parsing or another openFDA endpoint (e.g., drug/event) 
            # would be needed for structured side effects.
            
            # For simplicity, extract first few sentences/paragraphs or common terms
            full_text = " ".join(drug_info["adverse_reactions"])
            # Naive extraction of possible side effects from free text
            # This needs NLU/entity extraction to be reliable
            common_side_effects = re.findall(r'\b(nausea|vomiting|diarrhea|dizziness|headache|rash|fatigue)\b', full_text, re.IGNORECASE)
            
            if common_side_effects:
                # Remove duplicates and return a few examples
                return list(dict.fromkeys([s.lower() for s in common_side_effects]))[:limit]
            
            # Fallback if no specific common ones are found, return the raw text
            return drug_info["adverse_reactions"][:limit]
        return []

# Example Usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    fda_db = FDADrugDatabase()

    async def run_fda_tests():
        print("\n--- Test 1: Get Amoxicillin Info ---")
        amox_info = await fda_db.get_drug_info("Amoxicillin")
        if amox_info:
            print(f"Brand Name: {amox_info.get('brand_name')}")
            print(f"Generic Name: {amox_info.get('generic_name')}")
            print(f"Warnings (first): {amox_info.get('warnings', ['N/A'])[0][:100]}...")
            print(f"Black Box Warning: {amox_info.get('black_box_warning', 'N/A')}")
            print(f"Indications: {amox_info.get('indications_and_usage', ['N/A'])[0][:100]}...")
        assert amox_info is not None
        assert "amoxicillin" in amox_info.get("generic_name", [''])[0].lower()

        print("\n--- Test 2: Get Ibuprofen Info (Cached) ---")
        ibuprofen_info = await fda_db.get_drug_info("Ibuprofen")
        if ibuprofen_info:
            print(f"Generic Name: {ibuprofen_info.get('generic_name')}")
            print(f"Side Effects (first few): {ibuprofen_info.get('adverse_reactions', ['N/A'])[0][:100]}...")
        assert ibuprofen_info is not None

        print("\n--- Test 3: Check for Amoxicillin Recalls ---")
        amox_recalls = await fda_db.check_for_recalls("Amoxicillin")
        if amox_recalls:
            print(f"Recalls for Amoxicillin: {len(amox_recalls)}")
            for recall in amox_recalls:
                print(f"  - {recall.get('recall_number')}: {recall.get('reason_for_recall')[:50]}...")
        else:
            print("No recent recalls found for Amoxicillin (or mock).")

        print("\n--- Test 4: Get Side Effects for Aspirin ---")
        aspirin_side_effects = await fda_db.get_side_effects("Aspirin")
        if aspirin_side_effects:
            print(f"Aspirin Side Effects: {aspirin_side_effects}")
        else:
            print("No specific side effects extracted for Aspirin.")

        print("\n--- Test 5: Query for Non-existent Drug ---")
        non_existent_drug = await fda_db.get_drug_info("Unobtainium")
        print(f"Info for Unobtainium: {non_existent_drug}")
        assert non_existent_drug is None

    import asyncio
    asyncio.run(run_fda_tests())
