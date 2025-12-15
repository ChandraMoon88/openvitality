import logging
import requests
import json
import os
from typing import Dict, Any, List, Optional
from functools import lru_cache

# Assuming an external PDF parsing utility if needed
# from src.knowledge.document_loader_pdf import PDFDocumentLoader

logger = logging.getLogger(__name__)

class CDSCODrugDatabase:
    """
    Interacts with CDSCO (Central Drugs Standard Control Organization) data
    to retrieve information on Indian drugs, including NLEM status and DPCO price ceilings.
    This is a conceptual implementation, acknowledging the need for web scraping and PDF parsing
    due to the nature of CDSCO data.
    """
    def __init__(self, base_url: str = "https://cdsco.gov.in", cache_size: int = 500):
        self.base_url = base_url
        self.session = requests.Session() # Use a session for connection pooling
        self._get_drug_info_uncached = lru_cache(maxsize=cache_size)(self.__get_drug_info_uncached)
        # self.pdf_loader = PDFDocumentLoader() # If PDF parsing is integrated
        logger.info(f"CDSCODrugDatabase initialized. Base URL: {base_url}")

    async def get_drug_info(self, query: str) -> Optional[Dict[str, Any]]:
        """
        Retrieves drug information from CDSCO data for a given drug name.
        This is a conceptual method simulating data extraction from CDSCO.

        Args:
            query (str): The drug name (brand or generic) to search for.

        Returns:
            Optional[Dict[str, Any]]: A dictionary containing comprehensive drug information
                                       including NLEM status and DPCO price, or None if not found/error.
        """
        if not query:
            return None
        return self._get_drug_info_uncached(query.lower())

    def __get_drug_info_uncached(self, query: str) -> Optional[Dict[str, Any]]:
        """
        Internal method to retrieve drug information without caching.
        Simulates web scraping/PDF parsing of CDSCO data.
        """
        # In a real scenario, this would involve:
        # 1. Searching the CDSCO website for drug-related documents (e.g., NLEM list, DPCO notifications).
        # 2. Downloading relevant PDFs.
        # 3. Using a PDF parser (e.g., PDFDocumentLoader) to extract text/tables.
        # 4. Applying NLP/regex to extract structured information.
        
        logger.debug(f"Conceptually searching CDSCO data for: '{query}'")

        # Mock data for demonstration
        mock_data = {
            "paracetamol": {
                "generic_name": "Paracetamol",
                "brand_names": ["Crocin", "Dolo", "Calpol"],
                "nlem_status": True,
                "dpco_price_ceiling": {"unit": "tablet", "amount": 2.50, "currency": "INR"},
                "source_doc": "CDSCO NLEM 2022, DPCO 2023 list",
                "formulations": ["Tablet 500mg", "Syrup 125mg/5ml"]
            },
            "amoxicillin": {
                "generic_name": "Amoxicillin",
                "brand_names": ["Mox", "Amoxil"],
                "nlem_status": True,
                "dpco_price_ceiling": {"unit": "capsule", "amount": 5.00, "currency": "INR"},
                "source_doc": "CDSCO NLEM 2022, DPCO 2023 list",
                "formulations": ["Capsule 250mg", "Tablet 500mg"]
            },
            "atorvastatin": {
                "generic_name": "Atorvastatin",
                "brand_names": ["Atorva", "Lipitor"],
                "nlem_status": False, # Example: not in NLEM
                "dpco_price_ceiling": None, # Price may not be regulated by DPCO if not NLEM
                "source_doc": "CDSCO Drug List",
                "formulations": ["Tablet 10mg", "Tablet 20mg"]
            }
        }
        
        # Simulate query matching
        for drug_name, info in mock_data.items():
            if query in drug_name or query in [bn.lower() for bn in info.get("brand_names", [])]:
                logger.info(f"Retrieved CDSCO drug info for '{query}'.")
                return info
        
        logger.info(f"No CDSCO drug information found for query: '{query}'")
        return None

    async def get_nlem_status(self, drug_name: str) -> Optional[bool]:
        """
        Checks if a drug is part of the National List of Essential Medicines (NLEM).

        Args:
            drug_name (str): The name of the drug.

        Returns:
            Optional[bool]: True if it's NLEM, False otherwise, None if info not found.
        """
        info = await self.get_drug_info(drug_name)
        if info:
            return info.get("nlem_status")
        return None

    async def get_dpco_price_ceiling(self, drug_name: str) -> Optional[Dict[str, Any]]:
        """
        Retrieves the maximum legal price (price ceiling) for a drug under DPCO.

        Args:
            drug_name (str): The name of the drug.

        Returns:
            Optional[Dict[str, Any]]: Price ceiling information or None if not applicable/found.
        """
        info = await self.get_drug_info(drug_name)
        if info:
            return info.get("dpco_price_ceiling")
        return None
    
    async def query_max_legal_price(self, drug_name: str) -> str:
        """
        Provides a user-friendly response about the maximum legal price for a drug in India.
        """
        info = await self.get_drug_info(drug_name)
        if not info:
            return f"I could not find specific pricing information for '{drug_name}' in the CDSCO database."
        
        nlem_status = "is" if info.get("nlem_status") else "is generally not"
        response = f"According to CDSCO data, '{info['generic_name']}' ({info['brand_names'][0] if info.get('brand_names') else 'N/A'}) {nlem_status} on the National List of Essential Medicines (NLEM)."
        
        price_ceiling = info.get("dpco_price_ceiling")
        if price_ceiling:
            response += f" Its maximum legal price per {price_ceiling['unit']} under the Drug Price Control Order (DPCO) is approximately {price_ceiling['currency']} {price_ceiling['amount']:.2f}."
        else:
            response += " This drug may not have a specific price ceiling under DPCO, or that information is not available."
        
        response += " Always verify current pricing with your pharmacist as regulations can change."
        return response

# Example Usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    cdsco_db = CDSCODrugDatabase()

    async def run_cdsco_tests():
        print("\n--- Test 1: Get Paracetamol Info ---")
        paracetamol_info = await cdsco_db.get_drug_info("Paracetamol")
        if paracetamol_info:
            print(f"Generic Name: {paracetamol_info.get('generic_name')}")
            print(f"NLEM Status: {paracetamol_info.get('nlem_status')}")
            print(f"DPCO Price Ceiling: {paracetamol_info.get('dpco_price_ceiling')}")
        assert paracetamol_info is not None
        assert paracetamol_info.get("nlem_status") == True

        print("\n--- Test 2: Query Max Legal Price for Amoxicillin ---")
        amox_price_query = await cdsco_db.query_max_legal_price("Amoxicillin")
        print(f"Amoxicillin Price: {amox_price_query}")
        assert "maximum legal price" in amox_price_query

        print("\n--- Test 3: Get Atorvastatin Info (Not NLEM) ---")
        atorvastatin_info = await cdsco_db.get_drug_info("Atorvastatin")
        if atorvastatin_info:
            print(f"Generic Name: {atorvastatin_info.get('generic_name')}")
            print(f"NLEM Status: {atorvastatin_info.get('nlem_status')}")
            print(f"DPCO Price Ceiling: {atorvastatin_info.get('dpco_price_ceiling')}")
        assert atorvastatin_info is not None
        assert atorvastatin_info.get("nlem_status") == False
        assert atorvastatin_info.get("dpco_price_ceiling") is None

        print("\n--- Test 4: Query Max Legal Price for Atorvastatin ---")
        atorva_price_query = await cdsco_db.query_max_legal_price("Atorvastatin")
        print(f"Atorvastatin Price: {atorva_price_query}")
        assert "not have a specific price ceiling" in atorva_price_query

        print("\n--- Test 5: Query for Non-existent Drug ---")
        non_existent_drug = await cdsco_db.get_drug_info("UnobtainiumDrug")
        print(f"Info for UnobtainiumDrug: {non_existent_drug}")
        assert non_existent_drug is None

    import asyncio
    asyncio.run(run_cdsco_tests())
