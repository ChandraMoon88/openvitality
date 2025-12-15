import logging
import json
from typing import Dict, Any, List, Optional
from functools import lru_cache

logger = logging.getLogger(__name__)

class SNOMEDCTDatabase:
    """
    A conceptual interface to SNOMED CT (Systematized Nomenclature of Medicine—Clinical Terms).
    It simulates querying SNOMED CT for term definitions and synonym mapping,
    emphasizing its role in standardizing medical terminology.
    Acknowledges that full SNOMED CT access often requires specific tools and licenses.
    """
    def __init__(self, cache_size: int = 1000):
        # In a real implementation, this would connect to a local SNOMED CT database
        # (e.g., using a relational database with SNOMED CT release files imported)
        # or an external SNOMED CT browser/API.
        self._get_snomed_concept_uncached = lru_cache(maxsize=cache_size)(self.__get_snomed_concept_uncached)
        self.term_to_sctid_mapping: Dict[str, str] = {} # Lowercase term to SCTID
        self._load_mock_snomed_data()
        logger.info("SNOMEDCTDatabase initialized.")

    def _load_mock_snomed_data(self):
        """
        Loads mock SNOMED CT data for demonstration.
        In a real system, this would involve parsing SNOMED CT release files
        (e.g., RF2 format) into a queryable structure.
        """
        # Mock concepts with synonyms
        mock_concepts = {
            "22298006": { # Myocardial infarction
                "description": "Myocardial infarction",
                "synonyms": ["Heart attack", "MI", "Myocardial infarct"],
                "definition": "Necrosis of myocardial tissue resulting from insufficient blood supply to the heart muscle."
            },
            "38341003": { # Hypertension
                "description": "Essential hypertension",
                "synonyms": ["High blood pressure"],
                "definition": "A chronic medical condition in which the blood pressure in the arteries is persistently elevated."
            },
            "233604007": { # Fever
                "description": "Fever",
                "synonyms": ["Pyrexia", "Febrile response"],
                "definition": "An elevation of the body's core temperature above normal limits."
            },
            "250644002": { # Pain in chest
                "description": "Pain in chest",
                "synonyms": ["Chest discomfort", "Thoracic pain"],
                "definition": "Unpleasant sensation in the chest area."
            },
             "266918002": { # Asthma
                "description": "Asthma",
                "synonyms": ["Asthma disorder"],
                "definition": "A common chronic inflammatory disease of the airways characterized by variable and recurring symptoms."
            }
        }

        self.snomed_concepts: Dict[str, Dict[str, Any]] = {} # SCTID -> concept details
        for sctid, details in mock_concepts.items():
            self.snomed_concepts[sctid] = details
            self.term_to_sctid_mapping[details["description"].lower()] = sctid
            for syn in details["synonyms"]:
                self.term_to_sctid_mapping[syn.lower()] = sctid
        
        logger.info(f"Loaded {len(self.snomed_concepts)} mock SNOMED CT concepts.")

    async def get_snomed_concept(self, sctid: str) -> Optional[Dict[str, Any]]:
        """
        Retrieves details for a specific SNOMED CT concept by its SCTID.
        Uses caching.
        """
        return self._get_snomed_concept_uncached(sctid)

    def __get_snomed_concept_uncached(self, sctid: str) -> Optional[Dict[str, Any]]:
        """
        Internal method for retrieving SNOMED CT concept information without caching.
        """
        concept = self.snomed_concepts.get(sctid)
        if concept:
            logger.debug(f"Retrieved info for SNOMED CT concept '{sctid}'.")
            return concept
        logger.info(f"SNOMED CT concept '{sctid}' not found.")
        return None

    async def map_term_to_sctid(self, term: str) -> Optional[Dict[str, str]]:
        """
        Maps a natural language term (e.g., "heart attack") to its SNOMED CT Concept ID (SCTID).

        Args:
            term (str): The term to map.

        Returns:
            Optional[Dict[str, str]]: A dictionary with 'sctid' and 'description', or None.
        """
        term_lower = term.lower()
        sctid = self.term_to_sctid_mapping.get(term_lower)
        if sctid:
            concept = await self.get_snomed_concept(sctid)
            if concept:
                logger.info(f"Mapped '{term}' to SCTID '{sctid}'.")
                return {"sctid": sctid, "description": concept["description"]}
        
        # In a real system, this would involve NLP techniques (fuzzy matching, entity linking)
        # to handle variations not explicitly in synonyms.
        logger.info(f"No direct SNOMED CT mapping found for term: '{term}'.")
        return None

    async def get_synonyms(self, sctid: str) -> List[str]:
        """
        Retrieves all known synonyms for a given SNOMED CT concept ID.
        """
        concept = await self.get_snomed_concept(sctid)
        if concept:
            return concept.get("synonyms", [])
        return []

    async def explain_term(self, term_or_sctid: str) -> str:
        """
        Provides a plain English explanation for a SNOMED CT term or SCTID.
        """
        concept_info = None
        # First, check if it's an SCTID
        if term_or_sctid.isdigit():
            concept_info = await self.get_snomed_concept(term_or_sctid)
        
        # If not an SCTID or not found, try mapping as a term
        if not concept_info:
            mapped = await self.map_term_to_sctid(term_or_sctid)
            if mapped and mapped["sctid"]:
                concept_info = await self.get_snomed_concept(mapped["sctid"])
        
        if concept_info:
            return f"The medical term '{concept_info['description']}' (SNOMED CT ID: {concept_info.get('sctid', term_or_sctid)}) refers to: {concept_info['definition']}."
        return f"I could not find information for the medical term or SNOMED CT ID '{term_or_sctid}' in my database."


# Example Usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    snomed_db = SNOMEDCTDatabase()

    async def run_snomed_tests():
        print("\n--- Test 1: Get info for '22298006' (Myocardial infarction) ---")
        mi_concept = await snomed_db.get_snomed_concept("22298006")
        if mi_concept:
            print(f"SCTID: 22298006, Description: {mi_concept.get('description')}")
            print(f"Synonyms: {mi_concept.get('synonyms')}")
        assert mi_concept is not None
        assert "Heart attack" in mi_concept.get("synonyms")

        print("\n--- Test 2: Map 'Heart attack' to SCTID ---")
        mapped_mi = await snomed_db.map_term_to_sctid("Heart attack")
        if mapped_mi:
            print(f"Term 'Heart attack' -> SCTID: {mapped_mi.get('sctid')}, Description: {mapped_mi.get('description')}")
        assert mapped_mi is not None
        assert mapped_mi.get("sctid") == "22298006"

        print("\n--- Test 3: Get Synonyms for '38341003' (Hypertension) ---")
        hypertension_syns = await snomed_db.get_synonyms("38341003")
        print(f"Synonyms for Hypertension: {hypertension_syns}")
        assert "High blood pressure" in hypertension_syns

        print("\n--- Test 4: Explain term 'Asthma' ---")
        asthma_explanation = await snomed_db.explain_term("Asthma")
        print(f"Explanation for 'Asthma': {asthma_explanation}")
        assert "chronic inflammatory disease" in asthma_explanation

        print("\n--- Test 5: Explain SCTID '233604007' (Fever) ---")
        fever_explanation = await snomed_db.explain_term("233604007")
        print(f"Explanation for '233604007': {fever_explanation}")
        assert "elevation of the body's core temperature" in fever_explanation

        print("\n--- Test 6: Non-existent Term ---")
        non_existent_explanation = await snomed_db.explain_term("NonExistentCondition")
        print(f"Explanation for 'NonExistentCondition': {non_existent_explanation}")
        assert "could not find information" in non_existent_explanation

    import asyncio
    asyncio.run(run_snomed_tests())
